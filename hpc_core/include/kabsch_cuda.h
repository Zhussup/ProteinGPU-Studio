// CUDA entry points for the Kabsch/RMSD core. Compiled only by `make gpu`
// (nvcc, -arch=sm_86), linked together with kabsch_cpu.cpp so the module
// exposes both engines and the Python layer can fall back CPU-side.
#pragma once

#include "kabsch.h"

namespace hpc_cuda {

// Full Kabsch alignment of P onto Q on the GPU (single pair, one thread block).
// P, Q: n*3 row-major double arrays in host memory. Throws std::runtime_error
// on any CUDA failure (the Python wrapper downgrades to the CPU engine then).
hpc::AlignResult kabsch_full_cuda(const double* P, const double* Q, int n, int device);

// Same, but P/Q are already DEVICE pointers (no PCIe copies) — used when the
// coordinates come straight from a resident folding model on the GPU.
hpc::AlignResult kabsch_full_cuda_dev(const double* dP, const double* dQ, int n, int device);

// Batched pairwise RMSD: one thread block per pair. out[B] receives rmsd(b).
// Host-array variants include H2D copies; the _dev variants take device
// pointers and only copy the [B] result back.
void batched_rmsd_cuda(const double* P, const double* Q, int B, int n,
                       double* out, int device);
void batched_rmsd_cuda_dev(const double* dP, const double* dQ, int B, int n,
                           double* out, int device);

}  // namespace hpc_cuda