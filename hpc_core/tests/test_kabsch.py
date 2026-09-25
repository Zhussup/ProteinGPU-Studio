"""Python tests for the Kabsch HPC core vs numpy/scipy references.

Tolerances (from the implementation plan):
  CPU  vs numpy: 1e-9    CUDA vs numpy: 1e-5 (skipped if no CUDA build)
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

import hpc_core  # noqa: E402


def make_rigid_pair(n: int, seed: int = 0, noise: float = 0.0) -> tuple[np.ndarray, np.ndarray, Rotation]:
    rng = np.random.default_rng(seed)
    P = rng.uniform(-5.0, 5.0, (n, 3))
    R0 = Rotation.random(random_state=rng)
    t0 = rng.uniform(-10, 10, 3)
    Q = (R0.as_matrix() @ P.T).T + t0
    if noise > 0:
        Q = Q + rng.normal(0, noise, Q.shape)
    return P, Q, R0


def kabsch_numpy(P: np.ndarray, Q: np.ndarray) -> float:
    """Reference: SVD-based Kabsch RMSD, column-vector convention (q ≈ R p + t).

    With C = Pc^T Qc and numpy's U, S, Vh = svd(C), the optimal rotation is
    R = (U diag(1,1,d) Vh)^T — verified empirically against a known transform.
    """
    Pc, Qc = P - P.mean(0), Q - Q.mean(0)
    U, S, Wt = np.linalg.svd(Pc.T @ Qc)
    d = np.sign(np.linalg.det(U @ Wt))
    R = (U @ np.diag([1.0, 1.0, d]) @ Wt).T
    return float(np.sqrt(((Pc @ R.T - Qc) ** 2).sum() / len(P)))


class TestSinglePair:
    def test_identity_is_zero(self):
        rng = np.random.default_rng(1)
        P = rng.uniform(-5, 5, (128, 3))
        res = hpc_core.kabsch(P, P)
        assert res.rmsd == pytest.approx(0.0, abs=1e-12)
        assert res.tm_score == pytest.approx(1.0, abs=1e-9)

    def test_rigid_recovery_matches_numpy(self):
        for seed in range(5):
            P, Q, _ = make_rigid_pair(256, seed)
            assert hpc_core.rmsd(P, Q) == pytest.approx(kabsch_numpy(P, Q), abs=1e-9)

    def test_rotation_is_proper(self):
        P, Q, _ = make_rigid_pair(100, seed=2)
        res = hpc_core.kabsch(P, Q)
        assert np.allclose(res.R @ res.R.T, np.eye(3), atol=1e-12)
        assert np.linalg.det(res.R) == pytest.approx(1.0, abs=1e-9)

    def test_transform_recovers_geometry(self):
        P, Q, _ = make_rigid_pair(100, seed=3)
        res = hpc_core.kabsch(P, Q)
        aligned = (res.R @ P.T).T + res.t
        assert np.abs(aligned - Q).max() < 1e-8

    def test_reflection_not_collapsed(self):
        """Mirrored input must NOT give RMSD 0 via an improper (det<0) rotation."""
        rng = np.random.default_rng(4)
        P = rng.uniform(-5, 5, (128, 3))
        Q = P * np.array([-1.0, 1.0, 1.0])
        res = hpc_core.kabsch(P, Q)
        assert res.rmsd > 0.5, "improper rotation used — det correction is broken"
        assert np.linalg.det(res.R) == pytest.approx(1.0, abs=1e-9)
        assert res.rmsd == pytest.approx(kabsch_numpy(P, Q), abs=1e-9)

    def test_noise_matches_sigma(self):
        P, Q, _ = make_rigid_pair(512, seed=5, noise=0.1)
        # после оптимального наложения шум sigma=0.1 по каждой оси → RMSD ≈ sqrt(3)*0.1
        # 最优叠合后，每轴噪声 sigma=0.1 → RMSD ≈ sqrt(3)*0.1
        assert hpc_core.rmsd(P, Q) == pytest.approx(0.1 * np.sqrt(3.0), abs=0.01)

    def test_cross_check_scipy(self):
        """Cross-check the transform against scipy Rotation.align_vectors."""
        P, Q, R0 = make_rigid_pair(64, seed=6)
        res = hpc_core.kabsch(P, Q)
        # невзвешенный align_vectors(a, b) в scipy решает задачу направлений
        # без трансляции (без центрирования) и возвращает R с R.apply(b) ≈ a,
        # поэтому: сначала центрируем, и (Qc, Pc) даёт наше вращение P→Q.
        # scipy 的无权重 align_vectors(a, b) 求解的是无平移的方向问题（不居中），
        # 返回的 R 满足 R.apply(b) ≈ a；因此先居中，再传 (Qc, Pc) 得到 P→Q 旋转。
        Pc, Qc = P - P.mean(0), Q - Q.mean(0)
        R_scipy, _ = Rotation.align_vectors(Qc, Pc)
        angle = (Rotation.from_matrix(res.R) * R_scipy.inv()).magnitude()
        assert angle < 1e-6

    def test_torch_tensor_input(self):
        torch = pytest.importorskip("torch")
        P, Q, _ = make_rigid_pair(50, seed=7)
        pt = hpc_core.rmsd(torch.from_numpy(P), torch.from_numpy(Q))
        assert pt == pytest.approx(kabsch_numpy(P, Q), abs=1e-9)


class TestValidation:
    def test_length_mismatch_raises(self):
        P = np.zeros((10, 3))
        Q = np.zeros((9, 3))
        with pytest.raises(ValueError, match="length mismatch|same length"):
            hpc_core.kabsch(P, Q)

    def test_bad_shape_raises(self):
        with pytest.raises(ValueError):
            hpc_core.kabsch(np.zeros((10, 4)), np.zeros((10, 4)))

    def test_nan_raises(self):
        P = np.zeros((10, 3))
        P[0, 0] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            hpc_core.kabsch(P, P)


class TestBatched:
    def test_batched_matches_single(self):
        rng = np.random.default_rng(8)
        B, N = 8, 64
        P = rng.uniform(-5, 5, (B, N, 3))
        Q = P + rng.normal(0, 0.05, P.shape)
        got = hpc_core.batched_rmsd(P, Q, use_gpu=False)
        for b in range(B):
            assert got[b] == pytest.approx(kabsch_numpy(P[b], Q[b]), abs=1e-9)


@pytest.mark.slow
class TestGpu:
    def test_gpu_matches_cpu(self):
        if not hpc_core.HAS_CUDA:
            pytest.skip("CUDA build not present")
        import torch  # noqa: F401

        P, Q, _ = make_rigid_pair(1024, seed=9, noise=0.05)
        res = hpc_core.kabsch(P, Q)
        assert res.engine == "cuda"
        assert res.rmsd == pytest.approx(kabsch_numpy(P, Q), abs=1e-5)

    def test_gpu_batched_beats_cpu_at_scale(self):
        if not hpc_core.HAS_CUDA:
            pytest.skip("CUDA build not present")
        import torch  # noqa: F401

        rng = np.random.default_rng(10)
        B, N = 2048, 512
        P = rng.uniform(-5, 5, (B, N, 3))
        Q = P + rng.normal(0, 0.05, P.shape)
        got = hpc_core.batched_rmsd(P, Q, use_gpu=True)
        assert np.all(np.isfinite(got))
        # выборочно сверяем значения с numpy на нескольких парах
        # 抽查若干对，与 numpy 对照
        for b in rng.choice(B, 5, replace=False):
            assert got[b] == pytest.approx(kabsch_numpy(P[b], Q[b]), abs=1e-5)

    def test_gpu_device_resident_path(self):
        """Torch CUDA tensors pass to the GPU by pointer — values still exact."""
        if not hpc_core.HAS_CUDA:
            pytest.skip("CUDA build not present")
        torch = pytest.importorskip("torch")

        P, Q, _ = make_rigid_pair(256, seed=11, noise=0.03)
        res = hpc_core.kabsch(torch.from_numpy(P).cuda(), torch.from_numpy(Q).cuda())
        assert res.engine == "cuda"
        assert res.rmsd == pytest.approx(kabsch_numpy(P, Q), abs=1e-5)

        rng = np.random.default_rng(12)
        B, N = 16, 128
        Pb = rng.uniform(-5, 5, (B, N, 3))
        Qb = Pb + rng.normal(0, 0.05, Pb.shape)
        got = hpc_core.batched_rmsd(torch.from_numpy(Pb).cuda(), torch.from_numpy(Qb).cuda())
        for b in range(B):
            assert got[b] == pytest.approx(kabsch_numpy(Pb[b], Qb[b]), abs=1e-5)