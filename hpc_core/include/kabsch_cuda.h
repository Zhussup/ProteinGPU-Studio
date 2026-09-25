// Точки входа CUDA для ядра Kabsch/RMSD. Компилируются только через `make gpu`
// (nvcc, -arch=sm_86), линкуются вместе с kabsch_cpu.cpp, чтобы модуль
// открывал оба движка и Python-слой мог откатываться на CPU.
// Kabsch/RMSD 核心的 CUDA 入口。仅由 `make gpu` 编译
//（nvcc，-arch=sm_86），并与 kabsch_cpu.cpp 一起链接，使模块同时
// 暴露两套引擎，Python 层可回退到 CPU。
#pragma once

#include "kabsch.h"

namespace hpc_cuda {

// Полное совмещение Кабша P на Q на GPU (одна пара, один блок потоков).
// P, Q: плоские row-major double-массивы n*3 в памяти хоста. При любой
// CUDA-ошибке бросает std::runtime_error (Python-обёртка тогда откатывается
// на CPU-движок).
// 在 GPU 上把 P 对齐到 Q 的完整 Kabsch 算法（单对，单线程块）。
// P、Q：主机内存中长度 n*3 的行主序 double 数组。任何 CUDA 失败都会
// 抛出 std::runtime_error（Python 包装层随后回退到 CPU 引擎）。
hpc::AlignResult kabsch_full_cuda(const double* P, const double* Q, int n, int device);

// То же, но P/Q — уже указатели УСТРОЙСТВА (без PCIe-копий) — используется,
// когда координаты приходят прямо от резидентной модели фолдинга на GPU.
// 同上，但 P/Q 已是设备指针（无 PCIe 拷贝）——当坐标直接来自
// GPU 上的常驻折叠模型时使用。
hpc::AlignResult kabsch_full_cuda_dev(const double* dP, const double* dQ, int n, int device);

// Батчевый парный RMSD: один блок потоков на пару. out[b] получает rmsd(b).
// Варианты с хост-массивами включают копии H2D; варианты _dev принимают
// указатели устройства и копируют обратно только результат [B].
// 批量成对 RMSD：每对一个线程块。out[b] 接收 rmsd(b)。
// 宿主数组版本包含 H2D 拷贝；_dev 版本接受设备指针，
// 只把 [B] 结果拷回。
void batched_rmsd_cuda(const double* P, const double* Q, int B, int n,
                       double* out, int device);
void batched_rmsd_cuda_dev(const double* dP, const double* dQ, int B, int n,
                           double* out, int device);

}  // namespace hpc_cuda | namespace hpc_cuda 结束