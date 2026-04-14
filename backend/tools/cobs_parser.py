"""
COBS 彗星观测数据解析器

解析 COBS API 返回的 JSON（format=json），提取每日代表星等。
API: https://cobs.si/api/obs_list.api?format=json&des=C/2025%20R3

数据清洗规则：
1. 跳过 magnitude 为 null 或非数值的记录。
2. 按日期分组（取 obs_date 的日期部分）。
3. 同日多条记录取中位数作为当日代表值。
4. 偏离当日中位数超过 1.5 mag 的记录视为异常值，丢弃后重新计算中位数。
"""

import json
import statistics
from typing import Any


def parse_cobs_response(response: dict[str, Any], verbose: bool = False) -> list[dict[str, Any]]:
    """
    解析 COBS API 返回的 JSON 响应。

    Args:
        response: COBS API 完整 JSON 响应，包含 "objects" 列表。
        verbose: 若为 True，逐日打印原始记录数、过滤后记录数和最终中位数。

    Returns:
        按日期升序排列的列表，每条记录包含：
        - date (str): ISO 日期，如 "2026-04-14"
        - magnitude (float): 当日中位星等（异常值剔除后）
    """
    objects: list[dict] = response.get("objects", [])

    # 按日期聚合有效星等
    daily_raw: dict[str, list[float]] = {}
    for obs in objects:
        mag_raw = obs.get("magnitude")
        if mag_raw is None:
            continue
        try:
            mag = float(mag_raw)
        except (ValueError, TypeError):
            continue

        # 取 "2026-04-14 04:28:00" 的日期部分
        obs_date = obs.get("obs_date", "")
        date = obs_date[:10]
        if not date:
            continue

        daily_raw.setdefault(date, []).append(mag)

    results: list[dict[str, Any]] = []
    for date in sorted(daily_raw.keys()):
        raw_mags = daily_raw[date]
        n_raw = len(raw_mags)

        # 第一轮中位数
        median_first = statistics.median(raw_mags)

        # 剔除偏离超过 1.5 mag 的异常值
        filtered = [m for m in raw_mags if abs(m - median_first) <= 1.5]
        n_filtered = len(filtered)

        # 若全部被剔除（极端情况），回退使用原始数据
        if not filtered:
            filtered = raw_mags

        final_median = round(statistics.median(filtered), 3)

        if verbose:
            outliers = n_raw - n_filtered
            outlier_note = f"（剔除 {outliers} 条异常值）" if outliers > 0 else ""
            print(
                f"{date}  原始 {n_raw:>3} 条 → 保留 {n_filtered:>3} 条{outlier_note}"
                f"  中位星等 {final_median:.3f}"
            )

        results.append({"date": date, "magnitude": final_median})

    return results


# ── 测试入口 ───────────────────────────────────────────────────────────────────

def _run_tests(sample_path: str = "data/cobs_sample.json") -> None:
    with open(sample_path, encoding="utf-8") as f:
        raw = json.load(f)

    total_obs = len(raw.get("objects", []))
    print(f"样本记录总数：{total_obs} 条\n")
    print(f"{'日期':<12} {'原始':>5} {'保留':>5}  {'中位星等':>8}")
    print("-" * 40)

    records = parse_cobs_response(raw, verbose=True)

    print(f"\n共生成 {len(records)} 个日期的代表星等。")

    # 基础合理性检查
    assert len(records) > 0, "解析结果为空"
    for rec in records:
        assert "date" in rec and len(rec["date"]) == 10, f"日期格式异常：{rec}"
        assert "magnitude" in rec and 0 < rec["magnitude"] < 20, f"星等值异常：{rec}"

    print("基础合理性检查通过。")


if __name__ == "__main__":
    import sys
    sample = sys.argv[1] if len(sys.argv) > 1 else "data/cobs_sample.json"
    _run_tests(sample)
