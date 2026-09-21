# ProteinGPU-Studio

[English](README.md) | [Русский](README_RU.md) | **中文**

<div align="center">

**基于真实结构预测的定点突变分析 —— 附一份诚实的 CPU vs GPU 基准测试。**

输入蛋白序列，突变一个残基，观察野生型（WT）与突变体如何折叠 ——
并确切看到这一步在 CPU 与 GPU 上分别付出了什么代价。不粉饰，不掺水。

![演示：KRAS G12D —— 3D 叠合、指标、pLDDT 曲线](docs/assets/demo.gif)

![Python](https://img.shields.io/badge/python-3.13-black?style=flat-square&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.6-black?style=flat-square&logo=pytorch&logoColor=white)
![CUDA](https://img.shields.io/badge/CUDA-12.4-black?style=flat-square&logo=nvidia&logoColor=white)
![React](https://img.shields.io/badge/React%20%2B%20Vite-black?style=flat-square&logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-black?style=flat-square&logo=fastapi&logoColor=white)

</div>

## 这是什么

一个网页平台：对蛋白序列引入点突变，用真实的结构预测模型（OmegaFold，备选
ESMFold）分别折叠 WT 与突变体，将两个结构叠合，并回答一个具体的问题 —— 这次
突变究竟在多大程度上改变了折叠。手段包括：基于 Kabsch 对齐的全局/局部 RMSD、
TM-score，以及每条链的 pLDDT。推理栈（CPU / fp32-GPU / fp16-GPU）在一块 60 W
功耗墙的笔记本 GPU 上做基准测试，统计方式为中位数 + 四分位距（IQR）；比对核
心有三种实现（NumPy、C++17 OpenMP、CUDA），让你看清时间到底花在了哪里。

在单一突变体的图景之外，**突变强度旋钮**围绕一个位点生成变体组合，并以**结构响应
的分布**来度量位点的敏感性——用统计量与直方图说话，而不是两张图的目视比较。

屏幕上的一切都是真实的：没有伪造的进度条，没有占位模型 —— UI 显示的是后端
流水线的真实阶段，上面的演示 GIF 就是一次完整的真实运行。

## 功能特性

- **真实折叠模型** —— OmegaFold 为主，ESMFold 兜底；CPU / fp32-GPU / fp16-GPU 三种配置可在 UI 中切换
- **WT 与突变体对比分析** —— Kabsch 对齐的 RMSD（全局 + 局部窗口）、TM-score、pLDDT WT/mut/Δ、比对结论
- **C++17 / CUDA 高性能核心** —— 经 PyBind11 暴露的批量 Kabsch + RMSD 核函数；PCIe 拷贝路径与数据驻留设备路径分开计时
- **饱和突变扫描** —— 同一位点的全部 19 种替换，排序表格 + 图表
- **突变强度旋钮** —— 围绕一个锚定位点生成 K 个变体的组合：每个变体含 μ 个同步替换（锚点 + 背景位点），替换按 **Grantham 矩阵**以温度 τ（保守 ↔ 激进）抽取。敏感性 = 组合内**响应的分布**：中位数 + IQR、local RMSD 与窗口 ΔpLDDT 的直方图、等级/离散度徽章——不用任何虚构的 0–100 评分。「全部 19 种替换」exhaustive 模式精确复现饱和扫描——相同目标、相同产物
- **蛋白浏览器** —— 沿序列的 2D 轨道视图：逐残基 pLDDT、突变位点、扫描结果以及组合敏感性热图条（每残基平均 |ΔpLDDT|）；±50 残基窗口模式、缩略导航图、逐残基悬停提示
- **逐残基 pLDDT 曲线** —— WT 与突变体对比，支持悬停查看
- **跨运行对比** —— 基于同一蛋白任务历史的两张表：突变按 local RMSD 排序；位点之间按比较集合内的百分位比较——每个窗口都有各自的模型噪声底
- **科研预设** —— KRAS G12D、p53 R82H、HbB E6V、溶菌酶 I56T、Trp-cage W6F、Aβ42 E22G、α-突触核蛋白 A53T、GFP S65T
- **DNA FASTA 输入** —— 上传基因序列，展示密码子→氨基酸翻译窗口
- **诚实的任务流水线** —— 进度条反映后端真实阶段（包括"等待 GPU 时隙"），任务历史存于 SQLite
- **RU / EN / 中文界面** —— 切换同样覆盖后端生成的文本（汇总、预设、阶段消息）

## 基准测试

测量平台就是本项目的开发机：**RTX 3050 Laptop 6 GB，功耗墙 60 W**，
torch 2.6.0+cu124。所有数字均为多次重复的**中位数 + IQR**，并丢弃 2 次预热运行
—— 60 W 笔记本会降频，单次测量会撒谎。

OmegaFold 推理，76 个残基（KRAS）：

| 配置 | 墙钟时间（中位数） | 显存峰值 |
|---|---|---|
| CPU | 143.5 s | — |
| fp32-GPU | 11.6 s | 3.27 GB |
| fp16-GPU | **8.7 s**（较 CPU 快 16×） | 4.86 GB |

请注意这张表格揭示的一个反直觉取舍：fp16 更快，但显存占用反而**更高**。

Kabsch RMSD 核函数，1024 个结构对 × 256 个原子：

| 引擎 | 墙钟时间（中位数） |
|---|---|
| NumPy | 31.8 ms |
| C++17 OpenMP | **0.36 ms**（较 NumPy 快 88×） |
| CUDA（PCIe 拷贝） | 3.2 ms |
| CUDA（数据驻留设备） | 1.8 ms |

CUDA 核函数只有在数据留在显存里时才能取胜 —— 跨越 PCIe 的搬运成本比核函数
本身还高。复现方式：`python scripts/10_bench_inference.py`、
`python scripts/11_bench_kernels.py`。

## 快速开始

```bash
./scripts/00_setup_env.sh             # venv + 依赖
source .venv/bin/activate
make -C hpc_core cpu                  # C++ 核心（可选 CUDA：make cuda）

uvicorn backend.app.main:app --port 8077
cd frontend && npm install && npm run dev
```

打开前端，选择预设或粘贴 FASTA，然后运行 WT + 突变体、位点扫描或强度旋钮组合。
完整流水线自检：`python scripts/e2e_smoke.py`（泛素 + I44A/I3L/P19G）。

## 架构

```
[Web Client: React / 3Dmol.js / Plotly]
                 │ REST (polling)
                 ▼
[Backend Gateway: FastAPI]
        │                    │
        ▼                    ▼
[ML Inference Engine]   [C++/CUDA HPC Core]
(OmegaFold / PyTorch)   (Kabsch / RMSD, PyBind11)
```

- `backend/` —— FastAPI：任务队列（SQLite）、输入校验、遥测
- `ml/` —— 折叠模型封装 + CPU/GPU-fp32/fp16 配置
- `hpc_core/` —— C++17 + CUDA 核心：Kabsch、RMSD、PyBind11 绑定
- `frontend/` —— Vite + React + TypeScript，3Dmol.js + Plotly.js
- `scripts/` —— 环境安装、spike 测试、基准测试、报告图表与演示文稿生成、演示录制

演示 GIF 由 Playwright 脚本录制：脚本驱动真实 UI 在真实 GPU 上完整跑通一次
（`scripts/20_demo_video.py`）——其中还包含一项校验，确保录制的任务运行的是
真实模型而非占位模型。

## 致谢

- [OmegaFold](https://github.com/HeliXonProtein/OmegaFold)（[Wu et al., 2022](https://doi.org/10.1101/2022.07.21.500999)，Apache-2.0）与 [ESMFold](https://github.com/facebookresearch/esm) —— 结构预测
- [3Dmol.js](https://3dmol.csb.pitt.edu/) —— 分子可视化 · [Plotly.js](https://plotly.com/javascript/) —— 图表
- [PyBind11](https://github.com/pybind/pybind11) —— C++/Python 绑定