// Автономный smoke-тест CPU-ядра Kabsch (без Python, без зависимостей — только g++).
// Проверяет: тождественность -> 0, восстановление жёсткого преобразования,
// обработку отражений, устойчивость к шуму, согласие батчевого и одиночного путей,
// границы TM-score.
// 独立的 CPU Kabsch 核心 smoke 测试（无 Python、无依赖——只需 g++）。
// 验证：恒等变换 → 0、刚体变换的复原、反射处理、噪声容限、
// 批量与单次结果的一致性、TM-score 边界。
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

#include "kabsch.h"

using hpc::AlignResult;
using hpc::kabsch_full;
using hpc::kabsch_rmsd;
using hpc::batched_rmsd;

static int failures = 0;

void expect_near(const char* name, double got, double want, double tol) {
  if (std::fabs(got - want) > tol) {
    std::printf("FAIL %s: got %.12f want %.12f\n", name, got, want);
    ++failures;
  } else {
    std::printf("ok   %s: %.10f\n", name, got);
  }
}

// Случайный поворот через Gram-Schmidt на случайной 3x3 (строки ортонормированы, det=+1).
// 在随机 3x3 上用 Gram-Schmidt 构造随机旋转（行正交归一，det=+1）。

// Важное замечание о «равномерности» (математический нюанс)
// Хотя функция действительно возвращает корректную матрицу поворота, распределение поворотов не будет идеально равномерным (в смысле меры Хаара на 
// S
// O
// (
// 3
// )
// SO(3)
// ):
// Выборка случайных чисел из std::uniform_real_distribution генерирует точки внутри куба, а не на сфере. У куба есть диагонали и углы, поэтому некоторые направления будут генерироваться чаще, чем другие.
// Как сделать строго равномерным: Вместо равномерного распределения для исходных координат матрицы лучше использовать нормальное распределение std::normal_distribution<double>(0.0, 1.0), так как гауссово многомерное распределение сферически симметрично (изотропно). Либо использовать алгоритм генерации через случайные кватернионы (алгоритм Шумейка / Ken Shoemake).
// 关于“均匀性”的重要说明（数学细节）
// 该函数确实返回正确的旋转矩阵，但旋转分布并非严格均匀（按 SO(3) 上的 Haar 测度）：
// 从 std::uniform_real_distribution 抽取的随机数落在立方体内部而非球面上；
// 立方体存在对角线与顶角，因此某些方向会被更频繁地生成。
// 若要严格均匀：与其对矩阵原始坐标使用均匀分布，不如改用正态分布
// std::normal_distribution<double>(0.0, 1.0)——多维高斯分布球面对称（各向同性）；
// 也可以改用随机四元数生成法（Shoemake 算法 / Ken Shoemake）。
void random_rotation(std::mt19937& rng, std::uniform_real_distribution<double>& U, double R[9]) {
  double a[3][3];
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) a[i][j] = U(rng);
  double n0 = std::sqrt(a[0][0] * a[0][0] + a[0][1] * a[0][1] + a[0][2] * a[0][2]);
  for (int j = 0; j < 3; ++j) a[0][j] /= n0;
  double d = a[1][0] * a[0][0] + a[1][1] * a[0][1] + a[1][2] * a[0][2];
  for (int j = 0; j < 3; ++j) a[1][j] -= d * a[0][j];
  double n1 = std::sqrt(a[1][0] * a[1][0] + a[1][1] * a[1][1] + a[1][2] * a[1][2]);
  for (int j = 0; j < 3; ++j) a[1][j] /= n1;
  a[2][0] = a[0][1] * a[1][2] - a[0][2] * a[1][1];
  a[2][1] = a[0][2] * a[1][0] - a[0][0] * a[1][2];
  a[2][2] = a[0][0] * a[1][1] - a[0][1] * a[1][0];
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) R[i * 3 + j] = a[i][j];
}

int main() {
  std::mt19937 rng(42);
  std::uniform_real_distribution<double> U(-1.0, 1.0);

  // --- Тест 1: тождественность -> RMSD ровно 0, TM-score = 1
  // --- 测试 1：恒等变换 → RMSD 恰为 0，TM-score = 1
  {
    const int n = 64;
    std::vector<double> P(n * 3);
    for (auto& x : P) x = U(rng);
    AlignResult r = kabsch_full(P.data(), P.data(), n);
    expect_near("identity_rmsd", r.rmsd, 0.0, 1e-12);
    expect_near("identity_tm", r.tm_score, 1.0, 1e-9);
  }

  // --- Тест 2: известное жёсткое преобразование восстанавливается, RMSD -> 0
  // --- 测试 2：已知刚体变换被复原，RMSD → 0
  {
    const int n = 256;
    std::vector<double> P(n * 3), Q(n * 3);
    for (int i = 0; i < n * 3; ++i) P[i] = U(rng);
    double R0[9], t0[3];
    random_rotation(rng, U, R0);
    for (int k = 0; k < 3; ++k) t0[k] = U(rng) * 10.0;
    for (int i = 0; i < n; ++i)
      for (int k = 0; k < 3; ++k)
        Q[i * 3 + k] = R0[k * 3] * P[i * 3] + R0[k * 3 + 1] * P[i * 3 + 1] +
                       R0[k * 3 + 2] * P[i * 3 + 2] + t0[k];
    // DEBUG: проверка согласованности данных — Q должно в точности равняться R0*P + t0
    // (оставлено: снова защищает от неортогональной тестовой ротации)
    // DEBUG：数据一致性检查——Q 必须精确等于 R0*P + t0
    // （保留：再次防范测试旋转非正交的情况）
    {
      double detR0 = R0[0] * (R0[4] * R0[8] - R0[5] * R0[7]) -
                     R0[1] * (R0[3] * R0[8] - R0[5] * R0[6]) +
                     R0[2] * (R0[3] * R0[7] - R0[4] * R0[6]);
      expect_near("test_rotation_det", detR0, 1.0, 1e-9);
    }
    AlignResult r = kabsch_full(P.data(), Q.data(), n);
    expect_near("rigid_rmsd", r.rmsd, 0.0, 1e-10);
    // Восстановленный поворот должен совпадать с R0 точно.
    // 恢复出的旋转必须与 R0 完全一致。
    double max_err = 0.0;
    for (int i = 0; i < 9; ++i) max_err = std::max(max_err, std::fabs(r.R[i] - R0[i]));
    expect_near("rigid_R_recovery", max_err, 0.0, 1e-8);
    double max_t_err = 0.0;
    for (int k = 0; k < 3; ++k) max_t_err = std::max(max_t_err, std::fabs(r.t[k] - t0[k]));
    expect_near("rigid_t_recovery", max_t_err, 0.0, 1e-7);
    expect_near("rigid_tm", r.tm_score, 1.0, 1e-6);
  }

  // --- Тест 3: отражение (Q = зеркальный P) НЕ должно схлопываться в 0 через несобственный поворот
  // --- 测试 3：反射（Q = 镜像 P）不得借助非正常旋转坍缩到 0
  {
    const int n = 128;
    std::vector<double> P(n * 3), Q(n * 3);
    for (int i = 0; i < n; ++i) {
      P[i * 3] = U(rng); P[i * 3 + 1] = U(rng); P[i * 3 + 2] = U(rng);
      Q[i * 3] = -P[i * 3]; Q[i * 3 + 1] = P[i * 3 + 1]; Q[i * 3 + 2] = P[i * 3 + 2];
    }
    AlignResult r = kabsch_full(P.data(), Q.data(), n);
    // При ограничении «только собственные повороты» оптимальный RMSD НЕ равен 0.
    // 在仅允许正常旋转的约束下，最优 RMSD 不为 0。
    if (r.rmsd < 0.5) {
      std::printf("FAIL reflection_rmsd: collapsed to %.6f (improper rotation used)\n", r.rmsd);
      ++failures;
    } else {
      std::printf("ok   reflection_rmsd: %.6f (no improper collapse)\n", r.rmsd);
    }
    // R должна быть собственным поворотом: det ≈ +1, ортонормированность.
    // R 必须是正常旋转：det ≈ +1，且正交归一。
    double det = r.R[0] * (r.R[4] * r.R[8] - r.R[5] * r.R[7]) -
                 r.R[1] * (r.R[3] * r.R[8] - r.R[5] * r.R[6]) +
                 r.R[2] * (r.R[3] * r.R[7] - r.R[4] * r.R[6]);
    expect_near("reflection_det_R", det, 1.0, 1e-9);
  }

  // --- Тест 4: шум -> RMSD ≈ sqrt(3)*sigma
  // --- 测试 4：噪声 → RMSD ≈ sqrt(3)*sigma
  {
    const int n = 512;
    std::vector<double> P(n * 3), Q(n * 3);
    for (int i = 0; i < n * 3; ++i) P[i] = U(rng) * 5.0;
    std::normal_distribution<double> N(0.0, 0.1);
    for (int i = 0; i < n * 3; ++i) Q[i] = P[i] + N(rng);
    double rmsd = kabsch_rmsd(P.data(), Q.data(), n);
    expect_near("noise_rmsd", rmsd, 0.1 * std::sqrt(3.0), 0.01);
  }

  // --- Тест 5: батчевый путь == одиночный
  // --- 测试 5：批量 == 单次
  {
    const int B = 16, n = 100;
    std::vector<double> P(B * n * 3), Q(B * n * 3), out(B);
    for (int b = 0; b < B; ++b) {
      for (int i = 0; i < n * 3; ++i) {
        P[b * n * 3 + i] = U(rng);
        Q[b * n * 3 + i] = P[b * n * 3 + i] + 0.05 * U(rng);
      }
    }
    batched_rmsd(P.data(), Q.data(), B, n, out.data());
    double max_diff = 0.0;
    for (int b = 0; b < B; ++b)
      max_diff = std::max(max_diff, std::fabs(out[b] - kabsch_rmsd(P.data() + b * n * 3,
                                                                   Q.data() + b * n * 3, n)));
    expect_near("batched_vs_single", max_diff, 0.0, 1e-12);
  }

  if (failures == 0) {
    std::printf("\nALL CPU TESTS PASSED\n");
    return 0;
  }
  std::printf("\n%d FAILURES\n", failures);
  return 1;
}