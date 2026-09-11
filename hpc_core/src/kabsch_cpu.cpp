// Kabsch algorithm (optimal rigid alignment) — CPU implementation, C++17.
// No external dependencies: cyclic Jacobi replaces LAPACK, OpenMP parallelizes the batched path.
//
// Convention (verified algebraically and by tests):
//   minimize sum_i ||R p_i + t − q_i||^2,  R applied to column vectors.
//   C = sum_i p'_i q'^T_i (centered);  SVD C = U S W^T;  R = W D U^T,
//   D = diag(1, 1, sign(det(W U^T))) — reflection-safe.
//   RMSD^2 = (||P_c||^2 + ||Q_c||^2 − 2 Σ d_k s_k) / n, or computed directly.
#include "kabsch.h"

#include <algorithm>
#include <cmath>

namespace hpc {

// Cyclic Jacobi eigendecomposition of a symmetric 3x3 matrix A (row-major).
// On exit: eigenvalues in w (unordered), orthonormal eigenvectors as COLUMNS of V
// (row-major: column k of V = eigenvector for w[k]).
void jacobi3x3(const double A[9], double V[9], double w[3]) {
  double a[3][3] = {{A[0], A[1], A[2]}, {A[3], A[4], A[5]}, {A[6], A[7], A[8]}};
  double v[3][3] = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};

  for (int sweep = 0; sweep < 12; ++sweep) {
    double off = std::fabs(a[0][1]) + std::fabs(a[0][2]) + std::fabs(a[1][2]);
    if (off < 1e-15) break;
    for (int pass = 0; pass < 3; ++pass) {
      int p, q;
      if (pass == 0) { p = 0; q = 1; }      // pair (0,1)
      else if (pass == 1) { p = 0; q = 2; } // pair (0,2)
      else { p = 1; q = 2; }                // pair (1,2)
      if (std::fabs(a[p][q]) < 1e-30) continue;
      double theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q]);
      double sgn = (theta >= 0.0) ? 1.0 : -1.0;
      double t = sgn / (std::fabs(theta) + std::sqrt(theta * theta + 1.0));
      double c = 1.0 / std::sqrt(t * t + 1.0);
      double s = t * c;  // sin of the rotation angle
      // a <- J^T a J, where J is the Givens rotation in the (p,q) plane:
      // J[p][p]=c, J[p][q]=s, J[q][p]=-s, J[q][q]=c.
      for (int k = 0; k < 3; ++k) {  // right: columns (p,q)
        double akp = a[k][p], akq = a[k][q];
        a[k][p] = c * akp - s * akq;
        a[k][q] = s * akp + c * akq;
      }
      for (int k = 0; k < 3; ++k) {  // left: rows (p,q)
        double apk = a[p][k], aqk = a[q][k];
        a[p][k] = c * apk - s * aqk;
        a[q][k] = s * apk + c * aqk;
      }
      for (int k = 0; k < 3; ++k) {  // v <- v J (accumulate eigenvector columns)
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

namespace {

inline double det3m(const double* m) {
  return m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) +
         m[2] * (m[3] * m[7] - m[4] * m[6]);
}

// SVD of the 3x3 covariance C = U S W^T via eigendecomposition of C^T C.
// Output: wc[k][3] = k-th RIGHT singular vector (column of W),
//         uc[k][3] = k-th LEFT singular vector, s[3] = singular values (descending),
//         d = sign(det(W) * det(U)) for the reflection correction.
void svd3x3(const double C[9], double wc[3][3], double uc[3][3], double s[3], double& d) {
  double CtC[9];
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      double acc = 0.0;
      for (int k = 0; k < 3; ++k) acc += C[k * 3 + i] * C[k * 3 + j];
      CtC[i * 3 + j] = acc;
    }
  double V[9], w[3];
  jacobi3x3(CtC, V, w);

  // Sort eigenpairs descending; column idx[k] of V is the k-th right singular vector.
  int idx[3] = {0, 1, 2};
  std::sort(idx, idx + 3, [&](int a, int b) { return w[a] > w[b]; });
  for (int k = 0; k < 3; ++k) {
    s[k] = std::sqrt(std::max(w[idx[k]], 0.0));
    for (int r = 0; r < 3; ++r) wc[k][r] = V[r * 3 + idx[k]];
  }
  // Left vectors: uc_k = C wc_k / s_k (guard degenerate singular values).
  for (int k = 0; k < 3; ++k) {
    for (int r = 0; r < 3; ++r)
      uc[k][r] = C[r * 3] * wc[k][0] + C[r * 3 + 1] * wc[k][1] + C[r * 3 + 2] * wc[k][2];
    if (s[k] > 1e-10) {
      double norm = std::sqrt(uc[k][0] * uc[k][0] + uc[k][1] * uc[k][1] + uc[k][2] * uc[k][2]);
      for (int r = 0; r < 3; ++r) uc[k][r] /= norm;
    } else {
      uc[k][0] = wc[k][0];
      uc[k][1] = wc[k][1];
      uc[k][2] = wc[k][2];
    }
  }
  // det(columns of X) == det(rows of X), so row-stored vectors give the same determinant.
  d = det3m(&wc[0][0]) * det3m(&uc[0][0]);
}

// Build R = W D U^T from singular vectors.
inline void rotation_from_svd(const double wc[3][3], const double uc[3][3], double d, double R[9]) {
  double D[3] = {1.0, 1.0, d};
  for (int r = 0; r < 3; ++r)
    for (int j = 0; j < 3; ++j) {
      double acc = 0.0;
      for (int k = 0; k < 3; ++k) acc += wc[k][r] * D[k] * uc[k][j];
      R[r * 3 + j] = acc;
    }
}

}  // namespace

AlignResult kabsch_full(const double* P, const double* Q, int n) {
  AlignResult res{};
  res.n = n;
  if (n < 1) return res;

  double pm[3] = {0, 0, 0}, qm[3] = {0, 0, 0};
  for (int i = 0; i < n; ++i)
    for (int k = 0; k < 3; ++k) {
      pm[k] += P[i * 3 + k];
      qm[k] += Q[i * 3 + k];
    }
  for (int k = 0; k < 3; ++k) { pm[k] /= n; qm[k] /= n; }

  // Covariance C = sum_i p'_i q'^T_i, plus centered norms.
  double C[9] = {0};
  for (int i = 0; i < n; ++i) {
    double p[3] = {P[i * 3] - pm[0], P[i * 3 + 1] - pm[1], P[i * 3 + 2] - pm[2]};
    double q[3] = {Q[i * 3] - qm[0], Q[i * 3 + 1] - qm[1], Q[i * 3 + 2] - qm[2]};
    for (int r = 0; r < 3; ++r)
      for (int c = 0; c < 3; ++c) C[r * 3 + c] += p[r] * q[c];
  }

  double wc[3][3], uc[3][3], s[3], d;
  svd3x3(C, wc, uc, s, d);
  double R[9];
  rotation_from_svd(wc, uc, d, R);

  double t[3];
  for (int k = 0; k < 3; ++k) {
    t[k] = qm[k];
    for (int j = 0; j < 3; ++j) t[k] -= R[k * 3 + j] * pm[j];
  }

  // Direct RMSD over aligned pairs.
  double ssq = 0.0;
  for (int i = 0; i < n; ++i) {
    double dx = R[0] * P[i * 3] + R[1] * P[i * 3 + 1] + R[2] * P[i * 3 + 2] + t[0] - Q[i * 3];
    double dy = R[3] * P[i * 3] + R[4] * P[i * 3 + 1] + R[5] * P[i * 3 + 2] + t[1] - Q[i * 3 + 1];
    double dz = R[6] * P[i * 3] + R[7] * P[i * 3 + 1] + R[8] * P[i * 3 + 2] + t[2] - Q[i * 3 + 2];
    ssq += dx * dx + dy * dy + dz * dz;
  }
  res.rmsd = std::sqrt(ssq / n);
  for (int i = 0; i < 9; ++i) res.R[i] = R[i];
  for (int k = 0; k < 3; ++k) res.t[k] = t[k];
  res.tm_score = tm_score_from_transform(P, Q, n, R, t);
  return res;
}

double kabsch_rmsd(const double* P, const double* Q, int n) {
  if (n < 1) return 0.0;
  double pm[3] = {0, 0, 0}, qm[3] = {0, 0, 0};
  for (int i = 0; i < n; ++i)
    for (int k = 0; k < 3; ++k) {
      pm[k] += P[i * 3 + k];
      qm[k] += Q[i * 3 + k];
    }
  for (int k = 0; k < 3; ++k) { pm[k] /= n; qm[k] /= n; }
  double C[9] = {0};
  double e0 = 0.0, e1 = 0.0;
  for (int i = 0; i < n; ++i) {
    double p[3] = {P[i * 3] - pm[0], P[i * 3 + 1] - pm[1], P[i * 3 + 2] - pm[2]};
    double q[3] = {Q[i * 3] - qm[0], Q[i * 3 + 1] - qm[1], Q[i * 3 + 2] - qm[2]};
    e0 += p[0] * p[0] + p[1] * p[1] + p[2] * p[2];
    e1 += q[0] * q[0] + q[1] * q[1] + q[2] * q[2];
    for (int r = 0; r < 3; ++r)
      for (int c = 0; c < 3; ++c) C[r * 3 + c] += p[r] * q[c];
  }
  double wc[3][3], uc[3][3], s[3], d;
  svd3x3(C, wc, uc, s, d);
  double inner = e0 + e1 - 2.0 * (s[0] + s[1] + (d < 0.0 ? -1.0 : 1.0) * s[2]);
  if (inner < 0.0) inner = 0.0;  // roundoff guard
  return std::sqrt(inner / n);
}

void batched_rmsd(const double* P, const double* Q, int B, int n, double* out) {
#pragma omp parallel for schedule(static)
  for (int b = 0; b < B; ++b)
    out[b] = kabsch_rmsd(P + size_t(b) * n * 3, Q + size_t(b) * n * 3, n);
}

double tm_score_from_transform(const double* P, const double* Q, int n,
                               const double R[9], const double t[3]) {
  if (n <= 15) return 0.0;
  double d0 = 1.24 * std::cbrt(double(n) - 15.0) - 1.8;
  if (d0 < 0.5) d0 = 0.5;
  double tm = 0.0;
  for (int i = 0; i < n; ++i) {
    double dx = R[0] * P[i * 3] + R[1] * P[i * 3 + 1] + R[2] * P[i * 3 + 2] + t[0] - Q[i * 3];
    double dy = R[3] * P[i * 3] + R[4] * P[i * 3 + 1] + R[5] * P[i * 3 + 2] + t[1] - Q[i * 3 + 1];
    double dz = R[6] * P[i * 3] + R[7] * P[i * 3 + 1] + R[8] * P[i * 3 + 2] + t[2] - Q[i * 3 + 2];
    double dist2 = dx * dx + dy * dy + dz * dz;
    tm += 1.0 / (1.0 + dist2 / (d0 * d0));
  }
  return tm / n;
}

}  // namespace hpc