// Standalone C++ smoke test for the CPU Kabsch core (no Python, no deps — just g++).
// Validates: identity -> 0, rigid transform recovery, reflection handling,
// noise tolerance, batched vs single agreement, TM-score bounds.
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

// Random rotation via Gram-Schmidt on a random 3x3 (rows orthonormal, det=+1).
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

  // --- Test 1: identity -> RMSD exactly 0, TM-score = 1
  {
    const int n = 64;
    std::vector<double> P(n * 3);
    for (auto& x : P) x = U(rng);
    AlignResult r = kabsch_full(P.data(), P.data(), n);
    expect_near("identity_rmsd", r.rmsd, 0.0, 1e-12);
    expect_near("identity_tm", r.tm_score, 1.0, 1e-9);
  }

  // --- Test 2: known rigid transform is recovered, RMSD -> 0
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
    // DEBUG: data consistency check — Q must equal R0*P + t0 exactly
    // (kept: guards against a non-orthogonal test rotation again)
    {
      double detR0 = R0[0] * (R0[4] * R0[8] - R0[5] * R0[7]) -
                     R0[1] * (R0[3] * R0[8] - R0[5] * R0[6]) +
                     R0[2] * (R0[3] * R0[7] - R0[4] * R0[6]);
      expect_near("test_rotation_det", detR0, 1.0, 1e-9);
    }
    AlignResult r = kabsch_full(P.data(), Q.data(), n);
    expect_near("rigid_rmsd", r.rmsd, 0.0, 1e-10);
    // Recovered rotation must match R0 exactly.
    double max_err = 0.0;
    for (int i = 0; i < 9; ++i) max_err = std::max(max_err, std::fabs(r.R[i] - R0[i]));
    expect_near("rigid_R_recovery", max_err, 0.0, 1e-8);
    double max_t_err = 0.0;
    for (int k = 0; k < 3; ++k) max_t_err = std::max(max_t_err, std::fabs(r.t[k] - t0[k]));
    expect_near("rigid_t_recovery", max_t_err, 0.0, 1e-7);
    expect_near("rigid_tm", r.tm_score, 1.0, 1e-6);
  }

  // --- Test 3: reflection (Q = mirrored P) must NOT collapse to 0 via improper rotation
  {
    const int n = 128;
    std::vector<double> P(n * 3), Q(n * 3);
    for (int i = 0; i < n; ++i) {
      P[i * 3] = U(rng); P[i * 3 + 1] = U(rng); P[i * 3 + 2] = U(rng);
      Q[i * 3] = -P[i * 3]; Q[i * 3 + 1] = P[i * 3 + 1]; Q[i * 3 + 2] = P[i * 3 + 2];
    }
    AlignResult r = kabsch_full(P.data(), Q.data(), n);
    // With proper-rotation constraint the best RMSD is NOT 0.
    if (r.rmsd < 0.5) {
      std::printf("FAIL reflection_rmsd: collapsed to %.6f (improper rotation used)\n", r.rmsd);
      ++failures;
    } else {
      std::printf("ok   reflection_rmsd: %.6f (no improper collapse)\n", r.rmsd);
    }
    // R must be a proper rotation: det ≈ +1, orthonormal.
    double det = r.R[0] * (r.R[4] * r.R[8] - r.R[5] * r.R[7]) -
                 r.R[1] * (r.R[3] * r.R[8] - r.R[5] * r.R[6]) +
                 r.R[2] * (r.R[3] * r.R[7] - r.R[4] * r.R[6]);
    expect_near("reflection_det_R", det, 1.0, 1e-9);
  }

  // --- Test 4: noise → RMSD ≈ sqrt(3)*sigma
  {
    const int n = 512;
    std::vector<double> P(n * 3), Q(n * 3);
    for (int i = 0; i < n * 3; ++i) P[i] = U(rng) * 5.0;
    std::normal_distribution<double> N(0.0, 0.1);
    for (int i = 0; i < n * 3; ++i) Q[i] = P[i] + N(rng);
    double rmsd = kabsch_rmsd(P.data(), Q.data(), n);
    expect_near("noise_rmsd", rmsd, 0.1 * std::sqrt(3.0), 0.01);
  }

  // --- Test 5: batched == single
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