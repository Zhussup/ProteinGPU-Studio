// CUDA-реализация ядра Kabsch/RMSD (sm_86 / RTX 3050 laptop).
// CUDA 版 Kabsch/RMSD 核心实现（sm_86 / RTX 3050 laptop）。
//
// Замысел (честная история масштабирования для отчёта): один WARP на пару —
// только shuffle-редукции, без __syncthreads, 8 пар на блок из 256 потоков.
// Одиночная пара упирается в латентность, доминируют копирования — там GPU
// НЕ способен обогнать CPU; батчевый кернел — вот где GPU выигрывает (B >= ~1024).
// 设计较量（为报告保留诚实的扩展性叙事）：每对一个 WARP——
// 只用 shuffle 归约，不用 __syncthreads，每个 256 线程块处理 8 对。
// 单对受限于延迟且数据拷贝占主导——这种场景 GPU 无法胜过 CPU；
// 批量核函数才是 GPU 取胜之处（B >= ~1024）。
// Для каждой функции два хост-пути:
//   *_cuda(...)     — хостовые массивы, копии H2D/D2H включены (стоимость PCIe реальна);
//   *_cuda_dev(...) — указатели устройства, ноль копий: координаты, полученные от
//                     резидентной модели фолдинга, вообще не должны покидать GPU.
// 每个函数提供两条主机路径：
//   *_cuda(...)     —— 主机数组，含 H2D/D2H 拷贝（PCIe 成本真实存在）；
//   *_cuda_dev(...) —— 设备指针，零拷贝：常驻折叠模型产出的坐标无需离开 GPU。
// Математика 1:1 повторяет kabsch_cpu.cpp: C = Σ p'q'^T, Якоби-разложение C^T C,
// R = W D U^T с коррекцией отражения, затем прямой проход RMSD.
// 数学与 kabsch_cpu.cpp 完全一致：C = Σ p'q'^T，对 C^T C 作 Jacobi 分解，
// R = W D U^T 并修正反射，随后直接计算 RMSD。
#include "kabsch_cuda.h"

#include <cuda_runtime.h>

#include <cmath>
#include <mutex>
#include <stdexcept>
#include <string>

namespace {

constexpr int kWarpsPerBlock = 8;  // пар на блок из 256 потоков | 每 256 线程块 8 对

#define CUDA_CHECK(call)                                                     \
  do {                                                                       \
    cudaError_t err_ = (call);                                               \
    if (err_ != cudaSuccess) {                                               \
      throw std::runtime_error(std::string("CUDA error: ") +                 \
                               cudaGetErrorString(err_));                    \
    }                                                                        \
  } while (0)

// ---------------------------------------------------------------------------
// Математика на устройстве: Якоби-разложение + SVD ковариации,
// перенесено 1:1 из kabsch_cpu.cpp (последовательный код, выполняет lane 0).
// 设备端数学：Jacobi 特征分解 + 协方差的 SVD，
// 从 kabsch_cpu.cpp 1:1 移植（串行代码，由 lane 0 执行）。
// ---------------------------------------------------------------------------

__device__ void jacobi3x3_dev(const double A[9], double V[9], double w[3]) {
  double a[3][3] = {{A[0], A[1], A[2]}, {A[3], A[4], A[5]}, {A[6], A[7], A[8]}};
  double v[3][3] = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};

  for (int sweep = 0; sweep < 12; ++sweep) {
    double off = fabs(a[0][1]) + fabs(a[0][2]) + fabs(a[1][2]);
    if (off < 1e-15) break;
    for (int pass = 0; pass < 3; ++pass) {
      int p, q;
      if (pass == 0) { p = 0; q = 1; }
      else if (pass == 1) { p = 0; q = 2; }
      else { p = 1; q = 2; }
      if (fabs(a[p][q]) < 1e-30) continue;
      double theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q]);
      double sgn = (theta >= 0.0) ? 1.0 : -1.0;
      double t = sgn / (fabs(theta) + sqrt(theta * theta + 1.0));
      double c = 1.0 / sqrt(t * t + 1.0);
      double s = t * c;
      for (int k = 0; k < 3; ++k) {
        double akp = a[k][p], akq = a[k][q];
        a[k][p] = c * akp - s * akq;
        a[k][q] = s * akp + c * akq;
      }
      for (int k = 0; k < 3; ++k) {
        double apk = a[p][k], aqk = a[q][k];
        a[p][k] = c * apk - s * aqk;
        a[q][k] = s * apk + c * aqk;
      }
      for (int k = 0; k < 3; ++k) {
        double vkp = v[k][p], vkq = v[k][q];
        v[k][p] = c * vkp - s * vkq;
        v[k][q] = s * vkp + c * vkq;
      }
    }
  }
  for (int i = 0; i < 3; ++i) {
    w[i] = a[i][i];
    for (int j = 0; j < 3; ++j) V[i * 3 + j] = v[i][j];
  }
}

__device__ inline double det3m_dev(const double* m) {
  return m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) +
         m[2] * (m[3] * m[7] - m[4] * m[6]);
}

// SVD ковариации C через разложение C^T C (контракт тот же, что у CPU-версии).
// 通过 C^T C 的特征分解求 C 的 SVD（契约与 CPU 版本相同）。
__device__ void svd3x3_dev(const double C[9], double wc[3][3], double uc[3][3],
                           double s[3], double& d) {
  double CtC[9];
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      double acc = 0.0;
      for (int k = 0; k < 3; ++k) acc += C[k * 3 + i] * C[k * 3 + j];
      CtC[i * 3 + j] = acc;
    }
  double V[9], w[3];
  jacobi3x3_dev(CtC, V, w);

  // сортировка вставкой трёх собственных значений по убыванию
  // 用插入排序将三个特征值降序排列
  int idx[3] = {0, 1, 2};
  for (int i = 1; i < 3; ++i) {
    int key = idx[i];
    int j = i - 1;
    while (j >= 0 && w[idx[j]] < w[key]) { idx[j + 1] = idx[j]; --j; }
    idx[j + 1] = key;
  }
  for (int k = 0; k < 3; ++k) {
    s[k] = sqrt(max(w[idx[k]], 0.0));
    for (int r = 0; r < 3; ++r) wc[k][r] = V[r * 3 + idx[k]];
  }
  for (int k = 0; k < 3; ++k) {
    for (int r = 0; r < 3; ++r)
      uc[k][r] = C[r * 3] * wc[k][0] + C[r * 3 + 1] * wc[k][1] + C[r * 3 + 2] * wc[k][2];
    if (s[k] > 1e-10) {
      double norm = sqrt(uc[k][0] * uc[k][0] + uc[k][1] * uc[k][1] + uc[k][2] * uc[k][2]);
      for (int r = 0; r < 3; ++r) uc[k][r] /= norm;
    } else {
      uc[k][0] = wc[k][0];
      uc[k][1] = wc[k][1];
      uc[k][2] = wc[k][2];
    }
  }
  d = det3m_dev(&wc[0][0]) * det3m_dev(&uc[0][0]);
}

__device__ inline void rotation_from_svd_dev(const double wc[3][3],
                                             const double uc[3][3], double d,
                                             double R[9]) {
  double D[3] = {1.0, 1.0, d};
  for (int r = 0; r < 3; ++r)
    for (int j = 0; j < 3; ++j) {
      double acc = 0.0;
      for (int k = 0; k < 3; ++k) acc += wc[k][r] * D[k] * uc[k][j];
      R[r * 3 + j] = acc;
    }
}

// ---------------------------------------------------------------------------
// Один warp = одна пара. Загрузки когерентны по warp: lane L обходит атомы
// L, L+32, L+64, …, поэтому соседние LANE касаются соседних атомов — одна
// непрерывная область 768B на инструкцию загрузки warp. (Нарезка атомов по
// блокам на lane, наоборот, разнесла бы lane на ~768B внутри одной
// инструкции: 32 отдельных сектора по 32B.) Связь между lane — только __shfl_*:
// без shared memory, без барьеров.
// 一个 warp = 一对。加载按 warp 合并：lane L 遍历原子
// L、L+32、L+64、…，因此相邻 lane 访问相邻原子——每条 warp 加载指令
// 对应一段连续的 768B 连续区域。（若改为按 lane 分块遍历原子，同一条
// 指令内的 lane 将相距约 768B：32 个独立的 32B 扇区。）所有跨 lane
// 通信均用 __shfl_*：不用共享内存，不用栅栏。
// ---------------------------------------------------------------------------

__device__ inline double warp_sum(double v) {
  for (int off = 16; off > 0; off >>= 1)
    v += __shfl_down_sync(0xffffffffu, v, off);
  return __shfl_sync(0xffffffffu, v, 0);  // broadcast результата всем lane | 将结果广播给所有 lane
}

// Слитная однопроходная статистика: центроиды + центрированные нормы +
// ковариация за ОДНО чтение P и Q. Затем RMSD по замкнутой формуле (как в
// батчевом CPU-движке kabsch_rmsd): rmsd² = (e0 + e1 − 2 Σ d_k s_k) / n.
// 融合的单遍统计：质心 + 居中范数 + 协方差，只读一遍 P 和 Q。
// 随后按闭式公式计算 RMSD（与 CPU 批量引擎 kabsch_rmsd 相同）：
// rmsd² = (e0 + e1 − 2 Σ d_k s_k) / n。
__device__ void align_pair_warp(const double* P, const double* Q, int n,
                                bool with_tm, double& rmsd_out, double R_out[9],
                                double t_out[3], double& tm_out) {
  const int lane = threadIdx.x & 31;

  // Один слитный проход: суммы для центроидов, центрированные нормы, «сырая»
  // ковариация Σpq^T — одно чтение P и Q. Центрирование восстанавливается
  // алгебраически:
  //   C = Σ p'q'^T = Σ pq^T − (Σp)(Σq)^T / n
  // 单次融合遍历：质心累加、居中范数、原始协方差 Σpq^T —— 只读一遍 P 和 Q。
  // 居中通过代数关系还原：
  //   C = Σ p'q'^T = Σ pq^T − (Σp)(Σq)^T / n
  double sp[3] = {0, 0, 0}, sq[3] = {0, 0, 0}, e0 = 0.0, e1 = 0.0, raw[9] = {0};
  for (int i = lane; i < n; i += 32) {
    double p[3] = {P[i * 3], P[i * 3 + 1], P[i * 3 + 2]};
    double q[3] = {Q[i * 3], Q[i * 3 + 1], Q[i * 3 + 2]};
    for (int k = 0; k < 3; ++k) { sp[k] += p[k]; sq[k] += q[k]; }
    e0 += p[0] * p[0] + p[1] * p[1] + p[2] * p[2];
    e1 += q[0] * q[0] + q[1] * q[1] + q[2] * q[2];
    for (int r = 0; r < 3; ++r)
      for (int k = 0; k < 3; ++k) raw[r * 3 + k] += p[r] * q[k];
  }
  #pragma unroll
  for (int k = 0; k < 3; ++k) { sp[k] = warp_sum(sp[k]); sq[k] = warp_sum(sq[k]); }
  e0 = warp_sum(e0);
  e1 = warp_sum(e1);
  double rawC[9];
  #pragma unroll
  for (int k = 0; k < 9; ++k) rawC[k] = warp_sum(raw[k]);
  double pm[3], qm[3], C[9];
  #pragma unroll
  for (int k = 0; k < 3; ++k) { pm[k] = sp[k] / n; qm[k] = sq[k] / n; }
  #pragma unroll
  for (int r = 0; r < 3; ++r)
    for (int k = 0; k < 3; ++k) C[r * 3 + k] = rawC[r * 3 + k] - sp[r] * sq[k] / n;
  // Центрированные нормы: ||p'||² = ||p||² − (Σp)²/n (то же для q).
  // 居中范数：||p'||² = ||p||² − (Σp)²/n（q 同理）。
  e0 -= (sp[0] * sp[0] + sp[1] * sp[1] + sp[2] * sp[2]) / n;
  e1 -= (sq[0] * sq[0] + sq[1] * sq[1] + sq[2] * sq[2]) / n;

  // Lane 0: SVD → R, t, RMSD по замкнутой формуле; broadcast всему warp.
  // Lane 0：SVD → R、t、闭式 RMSD；广播给整个 warp。
  double R[9] = {0}, t[3] = {0};
  if (lane == 0) {
    double wc[3][3], uc[3][3], s[3], d;
    svd3x3_dev(C, wc, uc, s, d);
    rotation_from_svd_dev(wc, uc, d, R);
    for (int k = 0; k < 3; ++k) {
      t[k] = qm[k];
      for (int j = 0; j < 3; ++j) t[k] -= R[k * 3 + j] * pm[j];
    }
  }
  #pragma unroll
  for (int j = 0; j < 9; ++j) R[j] = __shfl_sync(0xffffffffu, R[j], 0);
  #pragma unroll
  for (int j = 0; j < 3; ++j) t[j] = __shfl_sync(0xffffffffu, t[j], 0);

  if (with_tm) {
    // Путь одиночной пары: RMSD считается НАПРЯМУЮ по совмещённым парам
    // (без риска сокращения), плюс последовательный TM-score на lane 0.
    // 单对路径：直接对叠合后的配对计算 RMSD（无相消风险），
    // 并在 lane 0 上串行计算 TM-score。
    double ssq = 0.0;
    for (int i = lane; i < n; i += 32) {
      double dx = R[0] * P[i * 3] + R[1] * P[i * 3 + 1] + R[2] * P[i * 3 + 2] + t[0] - Q[i * 3];
      double dy = R[3] * P[i * 3] + R[4] * P[i * 3 + 1] + R[5] * P[i * 3 + 2] + t[1] - Q[i * 3 + 1];
      double dz = R[6] * P[i * 3] + R[7] * P[i * 3 + 1] + R[8] * P[i * 3 + 2] + t[2] - Q[i * 3 + 2];
      ssq += dx * dx + dy * dy + dz * dz;
    }
    rmsd_out = sqrt(warp_sum(ssq) / n);
    if (n <= 15) {
      tm_out = 0.0;
    } else if (lane == 0) {
      double d0 = 1.24 * cbrt(double(n) - 15.0) - 1.8;
      if (d0 < 0.5) d0 = 0.5;
      double tm = 0.0;
      for (int i = 0; i < n; ++i) {
        double dx = R[0] * P[i * 3] + R[1] * P[i * 3 + 1] + R[2] * P[i * 3 + 2] + t[0] - Q[i * 3];
        double dy = R[3] * P[i * 3] + R[4] * P[i * 3 + 1] + R[5] * P[i * 3 + 2] + t[1] - Q[i * 3 + 1];
        double dz = R[6] * P[i * 3] + R[7] * P[i * 3 + 1] + R[8] * P[i * 3 + 2] + t[2] - Q[i * 3 + 2];
        double dist2 = dx * dx + dy * dy + dz * dz;
        tm += 1.0 / (1.0 + dist2 / (d0 * d0));
      }
      tm_out = tm / n;
    } else {
      tm_out = 0.0;
    }
  } else {
    // Батчевый путь: RMSD по замкнутой формуле, без повторного чтения (как CPU kabsch_rmsd).
    // 批量路径：闭式 RMSD，无需再次读取（与 CPU kabsch_rmsd 一致）。
    double s0 = 0.0, s1 = 0.0, s2 = 0.0;
    if (lane == 0) {
      double wc[3][3], uc[3][3], s[3], d;
      svd3x3_dev(C, wc, uc, s, d);
      s0 = s[0]; s1 = s[1]; s2 = (d < 0.0 ? -1.0 : 1.0) * s[2];
    }
    double inner = e0 + e1 - 2.0 * (s0 + s1 + s2);
    if (inner < 0.0) inner = 0.0;  // защита от ошибок округления | 防止舍入为负
    rmsd_out = sqrt(inner / n);
    tm_out = 0.0;
  }
  for (int j = 0; j < 9; ++j) R_out[j] = R[j];
  for (int j = 0; j < 3; ++j) t_out[j] = t[j];
}

// out: [14] = rmsd, tm, R[9], t[3]
__global__ void kabsch_full_kernel(const double* P, const double* Q, int n,
                                   double* out) {
  double rmsd, tm, R[9], t[3];
  align_pair_warp(P, Q, n, /*with_tm=*/true, rmsd, R, t, tm);
  if ((threadIdx.x & 31) == 0) {
    out[0] = rmsd;
    out[1] = tm;
    for (int i = 0; i < 9; ++i) out[2 + i] = R[i];
    for (int i = 0; i < 3; ++i) out[11 + i] = t[i];
  }
}

// Один warp на пару, 8 пар на блок. out[B] = rmsd.
// 每对一个 warp，每块 8 对。out[B] = rmsd。
__global__ void batched_rmsd_kernel(const double* P, const double* Q, int B,
                                    int n, double* out) {
  const int pair = blockIdx.x * kWarpsPerBlock + (threadIdx.x >> 5);
  if (pair >= B) return;
  double rmsd, tm, R[9], t[3];
  align_pair_warp(P + size_t(pair) * n * 3, Q + size_t(pair) * n * 3, n,
                  /*with_tm=*/false, rmsd, R, t, tm);
  if ((threadIdx.x & 31) == 0) out[pair] = rmsd;
}

}  // namespace | namespace 结束

namespace hpc_cuda {

namespace {
// cudaMalloc/cudaFree — операции уровня драйвера, синхронизирующие устройство,
// и стоят ~мс на крупных блоках — повторное выделение 2x25MB на каждый вызов
// затмило бы сам кернел. Буферы кэшируются на время жизни процесса (только
// растут); сценарий один GPU + один поток соответствует дизайну сервера.
// cudaMalloc/cudaFree 是驱动级操作，会同步设备，大块分配耗时约毫秒——
// 每次调用重新分配 2×25MB 会盖过核函数本身的开销。缓冲按进程生命周期
// 缓存（只增不减）；单 GPU、单流的使用方式与服务器设计一致。
std::mutex g_buf_mutex;

struct DeviceBuffer {
  void* p = nullptr;
  size_t cap = 0;
  double* get(size_t bytes) {
    if (cap < bytes) {
      if (p) cudaFree(p);
      CUDA_CHECK(cudaMalloc(&p, bytes));
      cap = bytes;
    }
    return static_cast<double*>(p);
  }
};

DeviceBuffer& scratch_a() { static DeviceBuffer b; return b; }
DeviceBuffer& scratch_b() { static DeviceBuffer b; return b; }
DeviceBuffer& scratch_out() { static DeviceBuffer b; return b; }
}  // namespace | namespace 结束

hpc::AlignResult kabsch_full_cuda(const double* P, const double* Q, int n, int device) {
  hpc::AlignResult res{};
  res.n = n;
  if (n < 1) return res;

  CUDA_CHECK(cudaSetDevice(device));
  size_t bytes = size_t(n) * 3 * sizeof(double);
  double hOut[14];
  {
    std::lock_guard<std::mutex> lock(g_buf_mutex);
    double* dP = scratch_a().get(bytes);
    double* dQ = scratch_b().get(bytes);
    double* dOut = scratch_out().get(sizeof(hOut));
    CUDA_CHECK(cudaMemcpy(dP, P, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dQ, Q, bytes, cudaMemcpyHostToDevice));
    kabsch_full_kernel<<<1, 32>>>(dP, dQ, n, dOut);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(hOut, dOut, sizeof(hOut), cudaMemcpyDeviceToHost));
  }

  res.rmsd = hOut[0];
  res.tm_score = hOut[1];
  for (int i = 0; i < 9; ++i) res.R[i] = hOut[2 + i];
  for (int i = 0; i < 3; ++i) res.t[i] = hOut[11 + i];
  return res;
}

hpc::AlignResult kabsch_full_cuda_dev(const double* dP, const double* dQ,
                                      int n, int device) {
  hpc::AlignResult res{};
  res.n = n;
  if (n < 1) return res;

  CUDA_CHECK(cudaSetDevice(device));
  double hOut[14];
  {
    std::lock_guard<std::mutex> lock(g_buf_mutex);
    double* dOut = scratch_out().get(sizeof(hOut));
    kabsch_full_kernel<<<1, 32>>>(dP, dQ, n, dOut);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(hOut, dOut, sizeof(hOut), cudaMemcpyDeviceToHost));
  }

  res.rmsd = hOut[0];
  res.tm_score = hOut[1];
  for (int i = 0; i < 9; ++i) res.R[i] = hOut[2 + i];
  for (int i = 0; i < 3; ++i) res.t[i] = hOut[11 + i];
  return res;
}

// Запуск батчевого кернела на указателях УСТРОЙСТВА (без копий); результат [B]
// копируется обратно на хост в out. Вызывающий должен держать g_buf_mutex.
// 在设备指针上启动批量核函数（无拷贝）；结果 [B] 拷回主机的 out。
// 调用方必须持有 g_buf_mutex。
static void batched_launch_dev_locked(const double* dP, const double* dQ, int B,
                                      int n, double* out, int device) {
  if (B < 1 || n < 1) return;
  CUDA_CHECK(cudaSetDevice(device));
  double* dOut = scratch_out().get(size_t(B) * sizeof(double));
  const int blocks = (B + kWarpsPerBlock - 1) / kWarpsPerBlock;
  batched_rmsd_kernel<<<blocks, kWarpsPerBlock * 32>>>(dP, dQ, B, n, dOut);
  CUDA_CHECK(cudaGetLastError());
  CUDA_CHECK(cudaDeviceSynchronize());
  CUDA_CHECK(cudaMemcpy(out, dOut, size_t(B) * sizeof(double), cudaMemcpyDeviceToHost));
}

void batched_rmsd_cuda(const double* P, const double* Q, int B, int n,
                       double* out, int device) {
  if (B < 1 || n < 1) return;
  CUDA_CHECK(cudaSetDevice(device));
  size_t bytes = size_t(B) * n * 3 * sizeof(double);
  std::lock_guard<std::mutex> lock(g_buf_mutex);
  double* dP = scratch_a().get(bytes);
  double* dQ = scratch_b().get(bytes);
  CUDA_CHECK(cudaMemcpy(dP, P, bytes, cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(dQ, Q, bytes, cudaMemcpyHostToDevice));
  batched_launch_dev_locked(dP, dQ, B, n, out, device);
}

void batched_rmsd_cuda_dev(const double* dP, const double* dQ, int B, int n,
                           double* out, int device) {
  // Входы уже резидентны на устройстве; обратно возвращается только результат [B].
  // 输入已常驻设备；只有结果 [B] 拷回主机。
  if (B < 1 || n < 1) return;
  std::lock_guard<std::mutex> lock(g_buf_mutex);
  batched_launch_dev_locked(dP, dQ, B, n, out, device);
}

}  // namespace hpc_cuda | namespace hpc_cuda 结束