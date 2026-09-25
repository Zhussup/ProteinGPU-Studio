// PyBind11-биндинги C++-ядра HPC для Kabsch/RMSD.
// Только numpy-буферы (без зависимости от torch), чтобы расширение никогда
// не конфликтовало с ABI torch.
// Сборка: make cpu   (или make gpu для CUDA-вариантов, под флагом USE_CUDA)
// Kabsch/RMSD HPC C++ 核心的 PyBind11 绑定。
// 仅接受 numpy 缓冲（不依赖 torch），扩展因此不会与 torch 的 ABI 冲突。
// 构建：make cpu（或 make gpu 构建 CUDA 版本，由 USE_CUDA 控制）
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/pytypes.h>

#include <string>

#include "kabsch.h"

namespace py = pybind11;
using hpc::AlignResult;

namespace {

using D2 = py::array_t<double, py::array::c_style | py::array::forcecast>;

py::dict align_to_dict(const AlignResult& r, const std::string& engine) {
  py::dict out;
  out["rmsd"] = r.rmsd;
  out["tm_score"] = r.tm_score;
  out["R"] = py::array_t<double>({3, 3}, r.R);
  out["t"] = py::array_t<double>({3}, r.t);
  out["n"] = r.n;
  out["engine"] = engine;
  return out;
}

void check_pair(const D2& p, const D2& q) {
  if (p.ndim() != 2 || p.shape(1) != 3) throw py::value_error("P must be of shape [N,3]");
  if (q.ndim() != 2 || q.shape(1) != 3) throw py::value_error("Q must be of shape [N,3]");
  if (p.shape(0) != q.shape(0)) throw py::value_error("P and Q must have the same length");
  if (p.shape(0) < 1) throw py::value_error("need at least 1 atom");
}

D2 check_batch(const D2& p, const D2& q) {
  if (p.ndim() != 3 || p.shape(2) != 3) throw py::value_error("P must be of shape [B,N,3]");
  if (q.ndim() != 3 || q.shape(2) != 3) throw py::value_error("Q must be of shape [B,N,3]");
  if (p.shape(0) != q.shape(0) || p.shape(1) != q.shape(1))
    throw py::value_error("P and Q must have the same B and N");
  return p;
}

}  // namespace | namespace 结束

PYBIND11_MODULE(hpc_core_native, m) {
  m.doc() = "Kabsch/RMSD HPC core (C++17, optional CUDA sm_86)";

  m.def("kabsch_rmsd_cpu",
        [](const D2& p, const D2& q) {
          check_pair(p, q);
          return align_to_dict(hpc::kabsch_full(p.data(), q.data(), (int)p.shape(0)), "cpp");
        },
        py::arg("P"), py::arg("Q"),
        "Full Kabsch alignment (RMSD + R/t + TM-score), C++ engine.");

  m.def("batched_rmsd_cpu",
        [](const D2& p, const D2& q) {
          check_batch(p, q);
          ssize_t B = p.shape(0);
          py::array_t<double> out(B);
          hpc::batched_rmsd(p.data(), q.data(), (int)B, (int)p.shape(1), out.mutable_data());
          return out;
        },
        py::arg("P"), py::arg("Q"),
        "Batched pairwise RMSD over B pairs of N atoms, OpenMP C++ engine. Returns [B] float64.");

#ifdef USE_CUDA
  m.def("kabsch_rmsd_cuda",
        [](const D2& p, const D2& q, int device) {
          check_pair(p, q);
          return align_to_dict(hpc_cuda::kabsch_full_cuda(p.data(), q.data(),
                                                          (int)p.shape(0), device), "cuda");
        },
        py::arg("P"), py::arg("Q"), py::arg("device") = 0,
        "Full Kabsch alignment on GPU (CUDA).");

  m.def("batched_rmsd_cuda",
        [](const D2& p, const D2& q, int device) {
          check_batch(p, q);
          ssize_t B = p.shape(0);
          py::array_t<double> out(B);
          hpc_cuda::batched_rmsd_cuda(p.data(), q.data(), (int)B, (int)p.shape(1),
                                      out.mutable_data(), device);
          return out;
        },
        py::arg("P"), py::arg("Q"), py::arg("device") = 0,
        "Batched pairwise RMSD on GPU (CUDA). Returns [B] float64.");
  m.attr("HAS_CUDA") = true;
#else
  m.attr("HAS_CUDA") = false;
#endif
}