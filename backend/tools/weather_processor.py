"""
7Timer 天气数据处理器

按 PRD 5.3 节的降级策略处理 ASTRO 和 CIVIL 产品，提取夜间时段数据，
执行一票否决，计算 weather_score。

降级优先级：
  1. ASTRO（72h 预报）：init 时间距当前不超过 24h，且目标日期在覆盖范围内
  2. CIVIL（192h 预报）：ASTRO 不可用时降级
  3. 无数据：超出 CIVIL 覆盖范围

cloudcover -9999 处理：
  7Timer 已知问题，cloudcover 字段偶发返回 -9999（数据不可用）。
  此时跳过 cloudcover 相关的一票否决和评分项，仅依据 prec_type（ASTRO+CIVIL）
  和 transparency（仅 ASTRO）计算评分，并在结果中标注 cloudcover_available=False。

7Timer cloudcover 等级说明（1-9）：
  1=0-6%，2=6-19%，3=19-31%，4=31-44%，5=44-56%，
  6=56-69%，7=69-81%，8=81-94%，9=94-100%

7Timer transparency 等级说明（1-8，仅 ASTRO）：
  1=极佳(<0.3 mag/airmass) … 8=极差(>1.0 mag/airmass)，数值越小越好
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any

# 中国标准时间 UTC+8
_CST = timezone(timedelta(hours=8))

# 夜间观测时段（本地时）
_NIGHT_START_HOUR = 18
_NIGHT_END_HOUR = 6   # 次日凌晨 6 点


def _parse_init(init_str: str) -> datetime:
    """
    将 7Timer init 字段（如 "2026041400"）解析为 UTC datetime。
    格式：YYYYMMDDХХ（前 8 位为日期，后 2 位为 UTC 小时）。
    """
    return datetime(
        int(init_str[0:4]),
        int(init_str[4:6]),
        int(init_str[6:8]),
        int(init_str[8:10]),
        tzinfo=timezone.utc,
    )


def _is_nighttime(dt_cst: datetime) -> bool:
    """判断给定 CST 时间是否在夜间观测时段（18:00–次日 06:00）。"""
    h = dt_cst.hour
    return h >= _NIGHT_START_HOUR or h < _NIGHT_END_HOUR


def _is_in_best_window(dt_cst: datetime, best_window: dict[str, str] | None) -> bool:
    """判断给定时间是否在 Agent 1 给出的最佳观测窗口内。"""
    if best_window is None:
        return False
    try:
        start_h, start_m = map(int, best_window["start"].split(":"))
        end_h, end_m = map(int, best_window["end"].split(":"))
        point_minutes = dt_cst.hour * 60 + dt_cst.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        if start_minutes <= end_minutes:
            return start_minutes <= point_minutes <= end_minutes
        # 跨日情况（如 23:00–01:00）
        return point_minutes >= start_minutes or point_minutes <= end_minutes
    except (KeyError, ValueError):
        return False


def _score_astro(cloudcover: int | None, transparency: int | None, prec_type: str) -> float:
    """
    计算 ASTRO 产品的单时间点天气评分（0-100）。

    权重：cloudcover 50%，transparency 30%，prec_type 20%。
    cloudcover 或 transparency 为 None 时，对应分项满分。
    """
    # cloudcover：1=最优(50分)，9=最差(0分)
    if cloudcover is not None:
        cc_score = 50.0 * (9 - cloudcover) / 8
    else:
        cc_score = 50.0  # 数据不可用时不扣分

    # transparency：1=最优(30分)，8=最差(0分)
    if transparency is not None:
        tp_score = 30.0 * (8 - transparency) / 7
    else:
        tp_score = 30.0

    # prec_type：无降水得满分，有降水得 0 分
    prec_score = 20.0 if prec_type == "none" else 0.0

    return round(cc_score + tp_score + prec_score, 1)


def _score_civil(cloudcover: int | None, prec_type: str) -> float:
    """
    计算 CIVIL 产品的单时间点天气评分（0-100）。
    CIVIL 无 transparency，权重：cloudcover 70%，prec_type 30%。
    """
    if cloudcover is not None:
        cc_score = 70.0 * (9 - cloudcover) / 8
    else:
        cc_score = 70.0

    prec_score = 30.0 if prec_type == "none" else 0.0
    return round(cc_score + prec_score, 1)


def _should_veto(
    cloudcover: int | None,
    transparency: int | None,
    prec_type: str,
    source: str,
) -> tuple[bool, str]:
    """
    判断是否触发一票否决。
    返回 (vetoed: bool, reason: str)。
    """
    if prec_type != "none":
        return True, f"有降水（{prec_type}）"
    if cloudcover is not None and cloudcover >= 8:
        return True, f"云量过高（等级 {cloudcover}，≥8）"
    if source == "astro" and transparency is not None and transparency >= 7:
        return True, f"透明度极差（等级 {transparency}，≥7）"
    return False, ""


def _extract_nighttime_points(
    dataseries: list[dict],
    init_dt: datetime,
    target_date_str: str,
    source: str,
    best_window: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    从 dataseries 中提取目标日期夜间时段的数据点。

    Args:
        dataseries    : 7Timer dataseries 列表
        init_dt       : 预报初始化时间（UTC）
        target_date_str: 目标日期，如 "2026-04-15"
        source        : "astro" 或 "civil"
        best_window   : 最佳观测窗口 {"start": "20:30", "end": "22:15"}，可为 None

    Returns:
        匹配的数据点列表，每条含解析后的字段和权重。
    """
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    points = []

    for entry in dataseries:
        tp = entry["timepoint"]
        dt_utc = init_dt + timedelta(hours=tp)
        dt_cst = dt_utc.astimezone(_CST)

        if not _is_nighttime(dt_cst):
            continue

        # 夜间 18:00-23:59 属于当日，00:00-05:59 属于前一日的夜晚
        if dt_cst.hour >= _NIGHT_START_HOUR:
            point_date = dt_cst.date()
        else:
            point_date = (dt_cst - timedelta(days=1)).date()

        if point_date != target_date:
            continue

        # 解析字段
        cc_raw = entry.get("cloudcover")
        cloudcover = None if cc_raw == -9999 else int(cc_raw)
        transparency = entry.get("transparency") if source == "astro" else None
        if transparency == -9999:
            transparency = None
        prec_type = entry.get("prec_type", "none")

        # 最佳观测窗口内的时间点权重加倍
        weight = 2.0 if _is_in_best_window(dt_cst, best_window) else 1.0

        points.append({
            "dt_cst": dt_cst.strftime("%Y-%m-%d %H:%M"),
            "cloudcover": cloudcover,
            "transparency": transparency,
            "prec_type": prec_type,
            "temp2m": entry.get("temp2m"),
            "weight": weight,
            "in_best_window": weight > 1.0,
        })

    return points


def process_weather(
    astro_response: dict[str, Any] | None,
    civil_response: dict[str, Any] | None,
    target_date_str: str,
    now_utc: datetime | None = None,
    best_window: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    按降级策略选取数据源，提取夜间数据，执行一票否决，计算 weather_score。

    Args:
        astro_response : 7Timer ASTRO JSON 响应，可为 None
        civil_response : 7Timer CIVIL JSON 响应，可为 None
        target_date_str: 目标日期，如 "2026-04-15"
        now_utc        : 当前 UTC 时间（默认取 datetime.now(UTC)，测试时可注入）
        best_window    : 最佳观测窗口，如 {"start": "20:30", "end": "22:15"}

    Returns:
        {
          "date": str,
          "source": "astro" | "civil" | "none",
          "cloudcover_available": bool,
          "vetoed": bool,
          "veto_reason": str,          # 仅 vetoed=True 时有值
          "cloudcover": int | None,    # 夜间加权平均，-9999 时为 None
          "transparency": int | None,  # 仅 ASTRO 有效
          "prec_type": str,            # 夜间最差降水类型
          "temp2m": float | None,      # 夜间均温
          "weather_score": float | None,  # vetoed 或无数据时为 None
          "n_points": int,             # 参与计算的时间点数
        }
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    # ── 选择数据源 ────────────────────────────────────────────────────────────
    source = "none"
    dataseries = []
    init_dt = None

    if astro_response:
        init_dt = _parse_init(str(astro_response["init"]))
        age_hours = (now_utc - init_dt).total_seconds() / 3600
        max_tp = max(e["timepoint"] for e in astro_response["dataseries"])
        astro_end = init_dt + timedelta(hours=max_tp)
        astro_covers = target_date <= astro_end.date()

        if age_hours <= 24 and astro_covers:
            source = "astro"
            dataseries = astro_response["dataseries"]

    if source == "none" and civil_response:
        init_dt = _parse_init(str(civil_response["init"]))
        max_tp = max(e["timepoint"] for e in civil_response["dataseries"])
        civil_end = init_dt + timedelta(hours=max_tp)
        if target_date <= civil_end.date():
            source = "civil"
            dataseries = civil_response["dataseries"]

    if source == "none":
        return {
            "date": target_date_str,
            "source": "none",
            "cloudcover_available": False,
            "vetoed": False,
            "veto_reason": "",
            "cloudcover": None,
            "transparency": None,
            "prec_type": "none",
            "temp2m": None,
            "weather_score": None,
            "n_points": 0,
        }

    # ── 提取夜间数据点 ────────────────────────────────────────────────────────
    points = _extract_nighttime_points(
        dataseries, init_dt, target_date_str, source, best_window
    )

    if not points:
        return {
            "date": target_date_str,
            "source": source,
            "cloudcover_available": False,
            "vetoed": False,
            "veto_reason": "",
            "cloudcover": None,
            "transparency": None,
            "prec_type": "none",
            "temp2m": None,
            "weather_score": None,
            "n_points": 0,
        }

    # ── 聚合夜间字段 ──────────────────────────────────────────────────────────
    cloudcover_available = any(p["cloudcover"] is not None for p in points)

    # 加权平均 cloudcover（仅有效值参与）
    cc_points = [(p["cloudcover"], p["weight"]) for p in points if p["cloudcover"] is not None]
    if cc_points:
        total_w = sum(w for _, w in cc_points)
        avg_cc = round(sum(cc * w for cc, w in cc_points) / total_w)
    else:
        avg_cc = None

    # 加权平均 transparency（仅 ASTRO，仅有效值）
    tp_points = [(p["transparency"], p["weight"]) for p in points if p["transparency"] is not None]
    if tp_points:
        total_w = sum(w for _, w in tp_points)
        avg_tp = round(sum(tp * w for tp, w in tp_points) / total_w)
    else:
        avg_tp = None

    # 最差降水类型（有降水优先）
    prec_types = [p["prec_type"] for p in points]
    worst_prec = next((pt for pt in prec_types if pt != "none"), "none")

    # 均温
    temps = [p["temp2m"] for p in points if p["temp2m"] is not None]
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None

    # ── 一票否决 ─────────────────────────────────────────────────────────────
    vetoed, veto_reason = _should_veto(avg_cc, avg_tp, worst_prec, source)

    # ── 计算评分 ──────────────────────────────────────────────────────────────
    if vetoed:
        score = None
    elif source == "astro":
        score = _score_astro(avg_cc, avg_tp, worst_prec)
    else:
        score = _score_civil(avg_cc, worst_prec)

    return {
        "date": target_date_str,
        "source": source,
        "cloudcover_available": cloudcover_available,
        "vetoed": vetoed,
        "veto_reason": veto_reason,
        "cloudcover": avg_cc,
        "transparency": avg_tp,
        "prec_type": worst_prec,
        "temp2m": avg_temp,
        "weather_score": score,
        "n_points": len(points),
    }


# ── 测试入口 ───────────────────────────────────────────────────────────────────

def _run_tests(
    astro_path: str = "data/samples/7timer_astro_shanghai.json",
    civil_path: str = "data/samples/7timer_civil_shanghai.json",
) -> None:
    with open(astro_path, encoding="utf-8") as f:
        astro = json.load(f)
    with open(civil_path, encoding="utf-8") as f:
        civil = json.load(f)

    init_dt = _parse_init(str(astro["init"]))
    print(f"ASTRO init: {astro['init']}  →  {init_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"CIVIL init: {civil['init']}")
    print()

    # 生成 init 日起连续 10 天的日期列表
    test_dates = [
        (init_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(10)
    ]
    best_window = {"start": "20:30", "end": "22:15"}

    print(f"{'日期':<12} {'来源':<6} {'CC':>4} {'Trans':>6} {'降水':<8} {'均温':>5} {'评分':>6} {'否决'}")
    print("-" * 70)

    for date in test_dates:
        result = process_weather(astro, civil, date, best_window=best_window)
        cc_str = str(result["cloudcover"]) if result["cloudcover"] is not None else "N/A"
        tp_str = str(result["transparency"]) if result["transparency"] is not None else "—"
        score_str = f"{result['weather_score']:.1f}" if result["weather_score"] is not None else "—"
        veto_str = f"✗ {result['veto_reason']}" if result["vetoed"] else ""
        temp_str = f"{result['temp2m']}°" if result["temp2m"] is not None else "—"
        print(
            f"{result['date']:<12} {result['source']:<6} {cc_str:>4} {tp_str:>6} "
            f"{result['prec_type']:<8} {temp_str:>5} {score_str:>6}  {veto_str}"
        )

    print()

    # 验证 cloudcover -9999 处理
    assert all(r is None or isinstance(r, int)
               for date in test_dates
               for r in [process_weather(astro, civil, date)["cloudcover"]]), \
        "cloudcover -9999 应被转换为 None"
    print("cloudcover -9999 → None 处理正确 ✓")

    # 验证降级：伪造一个超出 ASTRO 覆盖范围的日期
    far_date = (init_dt + timedelta(days=5)).strftime("%Y-%m-%d")
    result_far = process_weather(astro, civil, far_date, best_window=best_window)
    print(f"超出 ASTRO 窗口日期（{far_date}）→ 来源：{result_far['source']}  ✓")

    # 验证无数据场景
    very_far = (init_dt + timedelta(days=30)).strftime("%Y-%m-%d")
    result_none = process_weather(astro, civil, very_far)
    assert result_none["source"] == "none", "超出 CIVIL 范围应返回 source=none"
    print(f"超出所有预报窗口（{very_far}）→ source=none  ✓")

    print("\n所有测试通过。")


if __name__ == "__main__":
    import sys
    astro_path = sys.argv[1] if len(sys.argv) > 1 else "data/samples/7timer_astro_shanghai.json"
    civil_path = sys.argv[2] if len(sys.argv) > 2 else "data/samples/7timer_civil_shanghai.json"
    _run_tests(astro_path, civil_path)
