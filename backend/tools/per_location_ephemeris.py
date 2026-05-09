"""
地点星历与晨昏计算（PRD 步骤 5.5）

为 Agent 3 筛选后的存活候选地点，并行计算每个地点在每个可观测日期的：
  - target_passage  : 目标天体升起/峰值/落下时间及峰值高度角
  - twilight        : 日落、民昏、天昏、天曙、民曙、日出、月落时刻
  - azimuth_elevation : 完整 AZ/EL 时间序列（前端曲线的校验锚点）

并行策略：ThreadPoolExecutor（最大 10 worker），与现有代码库的同步 requests 风格保持一致。
单个地点请求失败时静默降级：target_passage 和 azimuth_elevation 设为 null，
twilight 仍从 skyfield 本地计算（无需网络）。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

log = logging.getLogger(__name__)

# 最大并行 Horizons 请求数；避免对 JPL 施加过大瞬时压力
_MAX_WORKERS = 10


def _compute_single(
    command: str,
    candidate: dict[str, Any],
    date: str,
    timezone_offset: int,
) -> dict[str, Any]:
    """
    为单个 (candidate, date) 组合计算 target_passage、twilight 和 azimuth_elevation。

    Args:
        command:          Horizons 目标 ID，如 ``"C/2025 R3"``。
        candidate:        地点字典，至少含 ``latitude``、``longitude``、``name`` 字段。
        date:             本地日期，ISO 格式 ``"YYYY-MM-DD"``。
        timezone_offset:  UTC 偏移小时数（默认 8，北京时间）。

    Returns:
        包含 ``target_passage``、``twilight``、``azimuth_elevation`` 的字典。
        如果 Horizons 请求失败，前两个字段为 ``None``，``azimuth_elevation`` 为空列表。
    """
    from horizons_parser import extract_target_passage, query_horizons_topocentric
    from twilight_calculator import calculate_twilight

    lat = candidate["latitude"]
    lon = candidate["longitude"]
    name = candidate.get("name", f"({lat},{lon})")

    # ── Horizons topocentric 查询 ─────────────────────────────────────────
    az_el_data: list[dict] = []
    target_passage: Optional[dict] = None

    try:
        az_el_data = query_horizons_topocentric(
            command=command,
            latitude=lat,
            longitude=lon,
            date=date,
            timezone_offset=timezone_offset,
        )
        target_passage = extract_target_passage(az_el_data)
        log.debug("[%s %s] Horizons OK：peak_el=%.1f°",
                  name, date, target_passage.get("peak_altitude_deg") or 0)
    except Exception as exc:
        log.warning("[%s %s] Horizons 请求失败，target_passage 置 null：%s", name, date, exc)
        target_passage = None

    # ── skyfield 晨昏计算（本地，不依赖网络）────────────────────────────
    try:
        twilight = calculate_twilight(lat, lon, date, timezone_offset=timezone_offset)
    except Exception as exc:
        log.warning("[%s %s] 晨昏计算失败：%s", name, date, exc)
        twilight = None

    return {
        "target_passage":    target_passage,
        "twilight":          twilight,
        "azimuth_elevation": az_el_data,
    }


def compute_per_location_data(
    command: str,
    candidates: list[dict[str, Any]],
    dates: list[str],
    timezone_offset: int = 8,
) -> list[dict[str, Any]]:
    """
    为所有存活候选地点并行计算地点特定的星历与晨昏数据（PRD 步骤 5.5）。

    对每个 (candidate, date) 组合并行调用 Horizons topocentric 查询（Quantities=4）
    和 skyfield 晨昏计算。结果按 ``(candidate_index, date)`` 顺序合并回候选列表。

    Args:
        command:          Horizons 目标 ID，如 ``"C/2025 R3"``。
        candidates:       候选地点列表，每条至少含 ``latitude``、``longitude``、
                          ``name`` 字段（Agent 3 输出格式）。
        dates:            可观测日期列表，ISO 格式，如 ``["2026-04-22", "2026-04-23"]``。
        timezone_offset:  UTC 偏移小时数（默认 8）。

    Returns:
        深拷贝后的 ``candidates`` 列表，每条地点记录新增以下字段::

            {
                ...原有字段...,
                "ephemeris_by_date": {
                    "2026-04-22": {
                        "target_passage":    {...} | null,
                        "twilight":          {...} | null,
                        "azimuth_elevation": [...],
                    },
                    "2026-04-23": { ... },
                },
            }

        当某个 (candidate, date) 的 Horizons 请求失败时，该日期的
        ``target_passage`` 和 ``azimuth_elevation`` 设为 ``null``；
        ``twilight`` 为 skyfield 本地计算结果（仍可得到）。

    Notes:
        最大并发数为 10。每个 Horizons 请求含 2 次自动重试（指数退避）。
        典型耗时：8–10 个地点 × 2 日期 ≈ 单次 Horizons 请求时间（~1–3s），
        并行后总耗时约等于单次请求耗时。
    """
    import copy

    result_candidates = copy.deepcopy(candidates)
    for c in result_candidates:
        c["ephemeris_by_date"] = {}

    # 构造所有 (candidate_idx, date) 任务
    tasks: list[tuple[int, str]] = [
        (i, d)
        for i in range(len(candidates))
        for d in dates
    ]

    total = len(tasks)
    log.info("步骤 5.5：开始并行计算 %d 个地点 × %d 个日期 = %d 个任务",
             len(candidates), len(dates), total)

    futures_map: dict = {}

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, total)) as pool:
        for idx, date in tasks:
            fut = pool.submit(
                _compute_single,
                command, candidates[idx], date, timezone_offset,
            )
            futures_map[fut] = (idx, date)

        completed = 0
        for fut in as_completed(futures_map):
            idx, date = futures_map[fut]
            name = candidates[idx].get("name", f"loc{idx}")
            try:
                data = fut.result()
                result_candidates[idx]["ephemeris_by_date"][date] = data
                completed += 1
                log.debug("[%s %s] 完成 (%d/%d)", name, date, completed, total)
            except Exception as exc:
                log.error("[%s %s] 计算异常（已捕获）：%s", name, date, exc)
                result_candidates[idx]["ephemeris_by_date"][date] = {
                    "target_passage":    None,
                    "twilight":          None,
                    "azimuth_elevation": [],
                }

    log.info("步骤 5.5 完成：%d/%d 任务成功", completed, total)
    return result_candidates


# ── CLI 自测入口 ───────────────────────────────────────────────────────────────

def _run_smoke_test() -> None:
    """
    冒烟测试：用两个长三角地点计算 2026-04-22 的数据。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    candidates = [
        {"name": "天荒坪", "latitude": 30.58, "longitude": 119.68, "bortle": 3},
        {"name": "上海市区（对照）", "latitude": 31.23, "longitude": 121.47, "bortle": 8},
    ]
    dates = ["2026-04-22"]

    print("开始冒烟测试（约需 5–10s）…")
    result = compute_per_location_data("C/2025 R3", candidates, dates)

    for cand in result:
        print(f"\n── {cand['name']} ──")
        for date, data in cand["ephemeris_by_date"].items():
            tp = data["target_passage"]
            tw = data["twilight"]
            az = data["azimuth_elevation"]
            print(f"  日期: {date}")
            print(f"  target_passage: {tp}")
            print(f"  twilight.sunset: {tw.get('sunset') if tw else None}")
            print(f"  azimuth_elevation 行数: {len(az)}")

    print("\n冒烟测试完成。")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    _run_smoke_test()
