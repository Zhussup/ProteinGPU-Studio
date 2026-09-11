# Build for the Kabsch/RMSD HPC core.
#   make cpu   — pure C++17 + OpenMP (no CUDA needed)
#   make gpu   — adds CUDA kernels (requires nvcc, sm_86 for RTX 3050)
#   make test  — standalone C++ tests
#   make pytest — Python bindings tests
PYTHON ?= $(shell ls ../.venv/bin/python 2>/dev/null || which python3)
PY_EXT     := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
PB_INCLUDES := $(shell $(PYTHON) -m pybind11 --includes 2>/dev/null)

CXX      ?= g++
NVCC     ?= nvcc
ARCH     ?= sm_86
CXXFLAGS := -std=c++17 -O3 -fPIC -fopenmp -march=native -Iinclude $(PB_INCLUDES)
LDFLAGS  := -shared

OUTDIR := python/hpc_core

.PHONY: cpu gpu test pytest clean

cpu: $(OUTDIR)/hpc_core_native$(PY_EXT)

$(OUTDIR)/hpc_core_native$(PY_EXT): src/kabsch_cpu.cpp src/bindings.cpp include/kabsch.h
	mkdir -p $(OUTDIR)
	$(CXX) $(CXXFLAGS) src/kabsch_cpu.cpp src/bindings.cpp $(LDFLAGS) -o $@

gpu: $(OUTDIR)/hpc_core_native_cuda$(PY_EXT)

$(OUTDIR)/hpc_core_native_cuda$(PY_EXT): src/kabsch_cpu.cpp src/kabsch_cuda.cu src/bindings_cuda.cpp include/kabsch.h include/kabsch_cuda.h
	mkdir -p $(OUTDIR)
	$(NVCC) -arch=$(ARCH) -O3 -Xcompiler -fPIC,-fopenmp -Iinclude \
		-Xcompiler "-std=c++17" $(PB_INCLUDES) \
		-DUSE_CUDA -DCUDA_MODULE_NAME=hpc_core_native_cuda \
		src/kabsch_cuda.cu src/kabsch_cpu.cpp src/bindings_cuda.cpp \
		$(LDFLAGS) -lcudart -o $@

test: tests/test_main.cpp src/kabsch_cpu.cpp
	$(CXX) -std=c++17 -O2 -Iinclude -fopenmp tests/test_main.cpp src/kabsch_cpu.cpp -o /tmp/kabsch_test
	/tmp/kabsch_test

pytest: cpu
	cd .. && $(PYTHON) -m pytest hpc_core/tests/test_kabsch.py -v

clean:
	rm -f $(OUTDIR)/*.so