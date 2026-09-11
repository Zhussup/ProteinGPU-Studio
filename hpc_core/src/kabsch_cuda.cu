// CUDA implementation of the Kabsch/RMSD core (sm_86 / RTX 3050 laptop).
//
// Design (honest-scaling story for the report): one WARP per pair — shuffle
// reductions only, no __syncthreads, 8 pairs per 256-thread block. A single
// pair is latency-bound and copies dominate — the GPU can NOT beat the CPU
// there; the batched kernel is where the GPU wins (B >= ~1024).
// Two host paths per function:
//   *_cuda(...)     — host arrays, H2D/D2H copies included (PCIe cost is real);
//   *_cuda_dev(...) — device pointers, zero copies: coordinates produced by a
//                     resident folding model never need to leave the GPU.
// The math mirrors kabsch_cpu.cpp exactly: C = Σ p'q'^T, Jacobi eig of C^T C,
// R = W D U^T with reflection correction, then a direct RMSD pass.
#include "kabsch_cuda.h"

#include <cuda_runtime.h>

#include <cmath>
#include <mutex>
#include <stdexcept>
#include <string>

namespace {

constexpr int kWarpsPerBlock = 8;  // pairs per 256-thread block

#define CUDA_CHECK(call)                                                     \
  do {                                                                       \
    cudaError_t err_ = (call);                                               \
    if (err_ != cudaSuccess) {                                               \
      throw std::runtime_error(std::string("CUDA error: ") +                 \
                               cudaGetErrorString(err_));                    \
    }                                                                        \
  } while (0)

// ---------------------------------------------------------------------------
// Device-side math: Jacobi eigendecomposition + SVD of the covariance,
// ported 1:1 from kabsch_cpu.cpp (serial code, executed by lane 0).
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

// SVD of C via eigendecomposition of C^T C (same contract as the CPU version).
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

  // insertion sort of 3 eigenvalues, descending
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
// One warp = one pair. Loads are warp-coalesced: lane L walks atoms
// L, L+32, L+64, … so consecutive LANES touch consecutive atoms — one
// 768B contiguous region per warp load instruction. (Chunking the atoms per
// lane instead would put lanes ~768B apart inside one instruction: 32
// separate 32B sectors.) All cross-lane communication is __shfl_* — no
// shared memory, no barriers.
// ---------------------------------------------------------------------------

__device__ inline double warp_sum(double v) {
  for (int off = 16; off > 0; off >>= 1)
    v += __shfl_down_sync(0xffffffffu, v, off);
  return __shfl_sync(0xffffffffu, v, 0);  // broadcast result to all lanes
}

// Fused single-pass statistics: centroids + centered norms + covariance in ONE
// read of P and Q. Then RMSD via the closed form (same as the CPU batched
// engine kabsch_rmsd): rmsd² = (e0 + e1 − 2 Σ d_k s_k) / n.
__device__ void align_pair_warp(const double* P, const double* Q, int n,
                                bool with_tm, double& rmsd_out, double R_out[9],
                                double t_out[3], double& tm_out) {
  const int lane = threadIdx.x & 31;

  // Single fused pass: centroid sums, centered norms, RAW covariance Σpq^T —
  // one read of P and Q. Centering is recovered algebraically:
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
  // Centered norms: ||p'||² = ||p||² − (Σp)²/n (same for q).
  e0 -= (sp[0] * sp[0] + sp[1] * sp[1] + sp[2] * sp[2]) / n;
  e1 -= (sq[0] * sq[0] + sq[1] * sq[1] + sq[2] * sq[2]) / n;

  // Lane 0: SVD → R, t, closed-form RMSD; broadcast to the warp.
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
    // Single-pair path: RMSD computed DIRECTLY over aligned pairs (no
    // cancellation risk), plus serial TM-score on lane 0.
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
    // Batched path: closed-form RMSD, no extra read (matches CPU kabsch_rmsd).
    double s0 = 0.0, s1 = 0.0, s2 = 0.0;
    if (lane == 0) {
      double wc[3][3], uc[3][3], s[3], d;
      svd3x3_dev(C, wc, uc, s, d);
      s0 = s[0]; s1 = s[1]; s2 = (d < 0.0 ? -1.0 : 1.0) * s[2];
    }
    double inner = e0 + e1 - 2.0 * (s0 + s1 + s2);
    if (inner < 0.0) inner = 0.0;  // roundoff guard
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

// One warp per pair, 8 pairs per block. out[B] = rmsd.
__global__ void batched_rmsd_kernel(const double* P, const double* Q, int B,
                                    int n, double* out) {
  const int pair = blockIdx.x * kWarpsPerBlock + (threadIdx.x >> 5);
  if (pair >= B) return;
  double rmsd, tm, R[9], t[3];
  align_pair_warp(P + size_t(pair) * n * 3, Q + size_t(pair) * n * 3, n,
                  /*with_tm=*/false, rmsd, R, t, tm);
  if ((threadIdx.x & 31) == 0) out[pair] = rmsd;
}

}  // namespace

namespace hpc_cuda {

namespace {
// cudaMalloc/cudaFree are driver-level operations that synchronize the device
// and cost ~ms for large blocks — re-allocating 2x25MB per call would dwarf
// the kernel itself. Buffers are cached for the process lifetime (growing
// only), single-GPU single-stream usage matches the server design.
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
}  // namespace

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

// Launch batched kernel on DEVICE pointers (no copies); result [B] copied
// back to host `out`. Caller must hold g_buf_mutex.
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
  // Inputs already resident on the device; only the [B] result comes back.
  if (B < 1 || n < 1) return;
  std::lock_guard<std::mutex> lock(g_buf_mutex);
  batched_launch_dev_locked(dP, dQ, B, n, out, device);
}

}  // namespace hpc_cuda