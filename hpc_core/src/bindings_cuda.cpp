// PyBind11 bindings for the CUDA build of the Kabsch/RMSD core.
// Module name is fixed (hpc_core_native_cuda) — the Python wrapper tries this
// module first and falls back to hpc_core_native when it is absent.
//
// Input policy: numpy buffers (forcecast) OR any object exposing
// __cuda_array_interface__ (torch/cupy device tensors) — no torch headers,
// so the extension never fights torch's ABI. Device-resident inputs are
// passed to the GPU by pointer with zero PCIe copies.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/pytypes.h>

#include <string>
#include <vector>

#include "kabsch.h"
#include "kabsch_cuda.h"

namespace py = pybind11;
using hpc::AlignResult;

namespace {

using D2 = py::array_t<double, py::array::c_style | py::array::forcecast>;
using D3 = py::array_t<double, py::array::c_style | py::array::forcecast>;

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

// A validated view over either a host numpy array or a device tensor.
// `keep` owns a converted numpy buffer when host-side: forcecast may materialize
// a fresh array, and the raw pointer must outlive the binding call.
struct Coords {
  const double* ptr = nullptr;
  std::vector<ssize_t> shape;
  bool on_device = false;
  py::object keep;
};

Coords take_coords(const py::handle& h, int want_ndim) {
  Coords c;
  if (py::hasattr(h, "__cuda_array_interface__")) {
    py::dict info = h.attr("__cuda_array_interface__");
    std::string typestr = info["typestr"].cast<std::string>();
    if (typestr != "<f8")
      throw py::value_error("device tensor must be float64, got " + typestr);
    for (auto item : info["shape"]) c.shape.push_back(item.cast<ssize_t>());
    c.ptr = reinterpret_cast<const double*>(info["data"].cast<std::pair<size_t, bool>>().first);
    c.on_device = true;
  } else {
    D2 tmp = D2::ensure(h);  // forcecast; a no-op reference when already suitable
    if (tmp.ndim() != want_ndim)
      throw py::value_error("expected " + std::to_string(want_ndim) + "D array");
    c.shape.assign(tmp.shape(), tmp.shape() + tmp.ndim());
    c.ptr = tmp.data();
    c.keep = std::move(tmp);
    c.on_device = false;
  }
  if ((int)c.shape.size() != want_ndim || c.shape[want_ndim - 1] != 3)
    throw py::value_error("last dimension must be 3 (x,y,z)");
  if (want_ndim == 2 && c.shape[0] < 1) throw py::value_error("need at least 1 atom");
  return c;
}

}  // namespace

PYBIND11_MODULE(hpc_core_native_cuda, m) {
  m.doc() = "Kabsch/RMSD HPC core — CUDA build (sm_86), CPU engines included as fallback.";

  // ---------------- CPU engines (host numpy only) ----------------
  m.def("kabsch_rmsd_cpu",
        [](const D2& p, const D2& q) {
          if (p.ndim() != 2 || q.ndim() != 2 || p.shape(1) != 3 || q.shape(1) != 3)
            throw py::value_error("P and Q must be of shape [N,3]");
          if (p.shape(0) != q.shape(0)) throw py::value_error("P and Q must have the same length");
          return align_to_dict(hpc::kabsch_full(p.data(), q.data(), (int)p.shape(0)), "cpp");
        },
        py::arg("P"), py::arg("Q"),
        "Full Kabsch alignment (RMSD + R/t + TM-score), C++ engine.");

  m.def("batched_rmsd_cpu",
        [](const D3& p, const D3& q) {
          if (p.ndim() != 3 || q.ndim() != 3 || p.shape(2) != 3 || q.shape(2) != 3)
            throw py::value_error("P and Q must be of shape [B,N,3]");
          if (p.shape(0) != q.shape(0) || p.shape(1) != q.shape(1))
            throw py::value_error("P and Q must have the same B and N");
          ssize_t B = p.shape(0);
          py::array_t<double> out(B);
          hpc::batched_rmsd(p.data(), q.data(), (int)B, (int)p.shape(1), out.mutable_data());
          return out;
        },
        py::arg("P"), py::arg("Q"),
        "Batched pairwise RMSD, OpenMP C++ engine. Returns [B] float64.");

  // ---------------- CUDA engines (host numpy OR device tensors) ----------------
  m.def("kabsch_rmsd_cuda",
        [](const py::object& po, const py::object& qo, int device) {
          Coords p = take_coords(po, 2), q = take_coords(qo, 2);
          if (p.shape[0] != q.shape[0]) throw py::value_error("P and Q must have the same length");
          if (p.on_device != q.on_device)
            throw py::value_error("P and Q must both live on the host or both on the device");
          AlignResult r = p.on_device
              ? hpc_cuda::kabsch_full_cuda_dev(p.ptr, q.ptr, (int)p.shape[0], device)
              : hpc_cuda::kabsch_full_cuda(p.ptr, q.ptr, (int)p.shape[0], device);
          return align_to_dict(r, "cuda");
        },
        py::arg("P"), py::arg("Q"), py::arg("device") = 0,
        "Full Kabsch alignment on GPU (CUDA). Accepts numpy arrays or "
        "float64 device tensors (via __cuda_array_interface__).");

  m.def("batched_rmsd_cuda",
        [](const py::object& po, const py::object& qo, int device) {
          Coords p = take_coords(po, 3), q = take_coords(qo, 3);
          if (p.shape[0] != q.shape[0] || p.shape[1] != q.shape[1])
            throw py::value_error("P and Q must have the same B and N");
          ssize_t B = p.shape[0];
          py::array_t<double> out(B);
          if (p.on_device) {
            hpc_cuda::batched_rmsd_cuda_dev(p.ptr, q.ptr, (int)B, (int)p.shape[1],
                                            out.mutable_data(), device);
          } else {
            hpc_cuda::batched_rmsd_cuda(p.ptr, q.ptr, (int)B, (int)p.shape[1],
                                        out.mutable_data(), device);
          }
          return out;
        },
        py::arg("P"), py::arg("Q"), py::arg("device") = 0,
        "Batched pairwise RMSD on GPU (one block per pair). Returns [B] float64.");

  m.attr("HAS_CUDA") = true;
}