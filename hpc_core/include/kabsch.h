// Ядро совмещения Кабша + RMSD: общие объявления для CPU- и CUDA-путей.
// Конвенция векторов-столбцов: q_i ≈ R p_i + t,  RMSD = sqrt(mean ||R p_i + t − q_i||²).
// Kabsch 对齐 + RMSD 核心：CPU 与 CUDA 路径共用的声明。
// 列向量约定：q_i ≈ R p_i + t，RMSD = sqrt(mean ||R p_i + t − q_i||²)。
#pragma once

namespace hpc {

// Полный результат одного парного совмещения. Матрицы — row-major 3x3.
// 一次成对对齐的完整结果。矩阵为 row-major 3x3。
struct AlignResult {
  double rmsd;
  double tm_score;
  double R[9];
  double t[3];
  int n;
};

// Циклическое Якоби-разложение симметричной 3x3-матрицы A (row-major).
// На выходе: собственные значения в w (по возрастанию, как получились),
// ортонормированные собственные векторы в V (строка i матрицы V — вектор для w[i]).
// ~6 проходов достаточно до машинной точности.
// 对称 3x3 矩阵 A（行主序）的循环 Jacobi 特征分解。
// 结束时：特征值存于 w（按产生顺序递增），V 中保存正交归一的特征向量
//（V 的第 i 行即 w[i] 对应的特征向量）。约 6 次扫描即可达到机器精度。
void jacobi3x3(const double A[9], double V[9], double w[3]);

// Слитный Кабш: оптимальное жёсткое совмещение P на Q, возвращает RMSD + преобразование.
// P, Q: плоские row-major double-массивы n*3. n >= 3.
// 融合版 Kabsch：P 到 Q 的最优刚体叠合，返回 RMSD + 变换。
// P、Q：长度 n*3 的行主序 double 数组。n >= 3。
AlignResult kabsch_full(const double* P, const double* Q, int n);

// Слитный путь без построения преобразования (используется батчевыми бенчмарками).
// 不构造变换的融合路径（批量基准测试使用）。
double kabsch_rmsd(const double* P, const double* Q, int n);

// Батчевый RMSD по B независимым парам по n атомов. out[b] = rmsd(пара b).
// 对 B 组独立、每组 n 个原子的配对计算批量 RMSD。out[b] = rmsd(第 b 对)。
void batched_rmsd(const double* P, const double* Q, int B, int n, double* out);

// TM-score для двух цепей равной длины с наложением Кабша из kabsch_full.
// d0 = 1.24*(L-15)^(1/3) - 1.8, нормировано на L = n.
// 对两条等长链计算 TM-score，使用 kabsch_full 的 Kabsch 叠合。
// d0 = 1.24*(L-15)^(1/3) - 1.8，按 L = n 标准化。
double tm_score_from_transform(const double* P, const double* Q, int n,
                               const double R[9], const double t[3]);

}  // namespace hpc | namespace hpc 结束