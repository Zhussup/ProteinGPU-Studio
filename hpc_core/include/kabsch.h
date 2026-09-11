// Kabsch alignment + RMSD core: shared declarations for CPU and CUDA paths.
// Column-vector convention: q_i ≈ R p_i + t,  RMSD = sqrt(mean ||R p_i + t − q_i||²).
#pragma once

namespace hpc {

// Full result of one pairwise alignment. Matrices are row-major 3x3.
struct AlignResult {
  double rmsd;
  double tm_score;
  double R[9];
  double t[3];
  int n;
};

// Cyclic Jacobi eigendecomposition of a symmetric 3x3 matrix A (row-major).
// On exit: eigenvalues in w (ascending, as produced), orthonormal eigenvectors in V
// (row i of V is the eigenvector for w[i]). ~6 sweeps suffice to machine precision.
void jacobi3x3(const double A[9], double V[9], double w[3]);

// Fused Kabsch: optimal rigid alignment of P onto Q, returns RMSD + transform.
// P, Q: n*3 row-major double arrays. n >= 3.
AlignResult kabsch_full(const double* P, const double* Q, int n);

// Fused path without building the transform (used by batched benchmarks).
double kabsch_rmsd(const double* P, const double* Q, int n);

// Batched RMSD over B independent pairs of n atoms each. out[B] = rmsd(pair b).
void batched_rmsd(const double* P, const double* Q, int B, int n, double* out);

// TM-score for two same-length chains using the Kabsch superposition of kabsch_full.
// d0 = 1.24*(L-15)^(1/3) - 1.8, standardized to L = n.
double tm_score_from_transform(const double* P, const double* Q, int n,
                               const double R[9], const double t[3]);

}  // namespace hpc