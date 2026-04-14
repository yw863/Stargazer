"""
彗星光变拟合模型

使用经典光变公式拟合 H（绝对星等）和 n（活动参数）：
    m = H + 5·log10(Δ) + 2.5·n·log10(r)

其中：
    m   : 表观星等（COBS 日均中位值）
    r   : 日心距（AU，来自 Horizons）
    Δ   : 地心距（AU，来自 Horizons）
    H, n: 待拟合参数

依赖：cobs_parser.parse_cobs_response, horizons_parser.parse_horizons_response
"""

import json
import math
from typing import Any

import numpy as np
from scipy.optimize import curve_fit

from cobs_parser import parse_cobs_response
from horizons_parser import parse_horizons_response


def _model(X: tuple, H: float, n: float) -> np.ndarray:
    """光变公式（供 curve_fit 使用）。"""
    r, delta = X
    return H + 5.0 * np.log10(delta) + 2.5 * n * np.log10(r)


def fit_comet_model(
    cobs_records: list[dict[str, Any]],
    horizons_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    拟合彗星光变参数 H 和 n。

    Args:
        cobs_records   : cobs_parser 输出，列表元素含 {date, magnitude}。
        horizons_records: horizons_parser 输出，列表元素含 {date, r, delta}。

    Returns:
        {
          "H"    : float,   # 拟合绝对星等
          "n"    : float,   # 拟合活动参数
          "rmse" : float,   # 残差均方根（mag）
          "n_points": int,  # 参与拟合的数据点数
        }

    Raises:
        ValueError: 重叠日期少于 3 个（无法拟合）。
    """
    # 按日期建索引
    cobs_by_date = {r["date"]: r["magnitude"] for r in cobs_records}
    horizons_by_date = {r["date"]: r for r in horizons_records}

    # 内连接：取两者共有日期
    common_dates = sorted(set(cobs_by_date) & set(horizons_by_date))
    if len(common_dates) < 3:
        raise ValueError(
            f"重叠日期仅 {len(common_dates)} 个，至少需要 3 个才能拟合。"
            f"请确认 COBS 与 Horizons 数据的时间范围是否匹配。"
        )

    m_obs = np.array([cobs_by_date[d] for d in common_dates])
    r_arr = np.array([horizons_by_date[d]["r"] for d in common_dates])
    delta_arr = np.array([horizons_by_date[d]["delta"] for d in common_dates])

    # 初始参数：参考 C/2025 R3 Horizons 给出的 M1=11.9, k1=11.25（n=k1/2.5=4.5）
    p0 = [11.9, 4.5]

    popt, _ = curve_fit(_model, (r_arr, delta_arr), m_obs, p0=p0)
    H_fit, n_fit = float(popt[0]), float(popt[1])

    m_pred = _model((r_arr, delta_arr), H_fit, n_fit)
    rmse = float(np.sqrt(np.mean((m_obs - m_pred) ** 2)))

    return {
        "H": round(H_fit, 4),
        "n": round(n_fit, 4),
        "rmse": round(rmse, 4),
        "n_points": len(common_dates),
    }


def predict_magnitude(
    H: float,
    n: float,
    r: float,
    delta: float,
) -> float:
    """
    给定拟合参数和星历，预测表观星等。

    Args:
        H    : 拟合绝对星等
        n    : 拟合活动参数
        r    : 日心距（AU）
        delta: 地心距（AU）

    Returns:
        预测表观星等（保留两位小数）。
    """
    return round(H + 5.0 * math.log10(delta) + 2.5 * n * math.log10(r), 2)


# ── 测试入口 ───────────────────────────────────────────────────────────────────

def _run_tests(
    cobs_path: str = "data/cobs_sample.json",
    horizons_path: str = "data/horizons_sample.json",
) -> None:
    """
    用样本文件验证拟合流程。

    注意：Horizons 样本仅含 2026-04-01 至 04-05 共 5 天，
    与 COBS 重叠日期有限，拟合结果仅作形式验证，非真实精度。
    """
    with open(cobs_path, encoding="utf-8") as f:
        cobs_raw = json.load(f)
    with open(horizons_path, encoding="utf-8") as f:
        horizons_raw = json.load(f)

    cobs_records = parse_cobs_response(cobs_raw)
    horizons_records = parse_horizons_response(horizons_raw)

    # 显示重叠情况
    cobs_dates = {r["date"] for r in cobs_records}
    horizons_dates = {r["date"] for r in horizons_records}
    overlap = sorted(cobs_dates & horizons_dates)
    print(f"COBS 日期数：{len(cobs_dates)}，Horizons 日期数：{len(horizons_dates)}")
    print(f"重叠日期（{len(overlap)} 个）：{overlap}")
    print()

    result = fit_comet_model(cobs_records, horizons_records)

    print("── 拟合结果 ──────────────────────────────────")
    print(f"  H      = {result['H']:.4f}  mag")
    print(f"  n      = {result['n']:.4f}")
    print(f"  RMSE   = {result['rmse']:.4f}  mag")
    print(f"  数据点  = {result['n_points']} 个")
    print()

    # 参数范围合理性检查（宽松，因样本重叠有限）
    H, n = result["H"], result["n"]
    if not (0 < H < 20):
        print(f"  警告：H={H} 超出通常范围 (0, 20)，请检查数据质量。")
    else:
        print(f"  H 范围检查通过（{H} ∈ (0, 20)）")

    if not (0 < n < 15):
        print(f"  警告：n={n} 超出通常范围 (0, 15)，请检查数据质量。")
    else:
        print(f"  n 范围检查通过（{n} ∈ (0, 15)）")

    # 用重叠日中的第一天做预测示例
    if overlap:
        h_rec = next(r for r in horizons_records if r["date"] == overlap[0])
        pred = predict_magnitude(H, n, h_rec["r"], h_rec["delta"])
        cobs_mag = next(r["magnitude"] for r in cobs_records if r["date"] == overlap[0])
        print()
        print(f"── 预测示例（{overlap[0]}）─────────────────────────")
        print(f"  COBS 实测中位星等：{cobs_mag:.3f}")
        print(f"  模型预测星等　　：{pred:.2f}")
        print(f"  残差　　　　　　：{abs(pred - cobs_mag):.3f} mag")

    print("\n流程验证完成。（全量数据拟合请运行 daily_fit.py）")


if __name__ == "__main__":
    import sys
    cobs_path = sys.argv[1] if len(sys.argv) > 1 else "data/cobs_sample.json"
    horizons_path = sys.argv[2] if len(sys.argv) > 2 else "data/horizons_sample.json"
    _run_tests(cobs_path, horizons_path)
