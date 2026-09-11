// PyBind11 bindings for the Kabsch/RMSD HPC C++ core.
// numpy-buffer-only (no torch dependency), so the extension never fights torch's ABI.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/pytypes.h>

#include <string>

#include "kabsch.h"

namespace py = pybind11;
using hpc::AlignResult;

namespace {

py::dict align_to_dict(const AlignResult& r, const std::string& engine) {
  py::dict out;
  out["rmsd"] = r.rmsd;
  out["tm_score"] = r.tm_score;
  out["R"] = py::array_t<double>({3, 3}, r.R);
  out["t"] = py::array_t<double>({3}, r.t);
  out["n"] = n;
  out["engine"] = engine;
  return out;
}

}  // namespace

PYBIND11_MODULE(hpc_core_native, m) {
  m.doc() = "Kabsch/RMSD HPC core (C++17 + CUDA 12.4, sm_86)";

  m.def(
      "kabsch_rmsd_cpu",
      [](py::array_t<double, py::array::c_style | py::array::forcecast> p,
         py::array_t<double, py::array::c_style | py::array:: compile_placeholder> q) {