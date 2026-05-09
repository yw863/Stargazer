"""
JPL Horizons API 响应解析器

将 Horizons API 返回的 JSON 中嵌套的纯文本星历表解析为结构化列表。
每条记录对应一个日期，提取光变拟合和观测规划所需的字段。

支持的 Quantities：9（T-mag/N-mag）、19（r/rdot）、20（delta/deldot）、
23（S-O-T /r）、25（T-O-M/MN_Illu%）。
"""

import json
import re
from datetime import datetime
from typing import Any


# 月份缩写 → 数字，用于将 Horizons 日期格式 "2026-Apr-01" 转为 "2026-04-01"
_MONTH_MAP: dict[str, str] = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

# 匹配 $$SOE … $$EOE 之间的每条数据行
# 列顺序（Quantities 9,19,20,23,25）：
#   日期时间  T-mag  N-mag  r  rdot  delta  deldot  S-O-T  /r_flag  T-O-M  /  MN_Illu%
_ROW_RE = re.compile(
    r"^\s*(\d{4}-[A-Za-z]{3}-\d{2})\s+\d{2}:\d{2}"  # 日期（忽略时分）
    r"\s+([\d.]+)"                                     # T-mag
    r"\s+[\d.]+"                                       # N-mag（不需要）
    r"\s+([\d.]+)\s+[-\d.]+"                           # r, rdot
    r"\s+([\d.]+)\s+[-\d.]+"                           # delta, deldot
    r"\s+([\d.]+)\s+(/[LT?*])"                        # S-O-T, /r flag
    r"\s+([\d.]+)/\s*([\d.]+)"                         # T-O-M, MN_Illu%
)


def _parse_date(raw: str) -> str:
    """将 "2026-Apr-01" 转换为 ISO 格式 "2026-04-01"。"""
    parts = raw.split("-")
    return f"{parts[0]}-{_MONTH_MAP[parts[1]]}-{parts[2]}"


def parse_horizons_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    """
    解析 Horizons API 返回的 JSON 响应。

    Args:
        response: Horizons API 的完整 JSON 响应字典，包含 "result" 键。

    Returns:
        结构化星历列表，每条记录包含：
        - date (str): ISO 日期，如 "2026-04-01"
        - t_mag (float): Horizons 内置预测星等
        - r (float): 日心距离（AU）
        - delta (float): 地心距离（AU）
        - s_o_t (float): 太阳角距（度）
        - s_o_t_flag (str): "/L"（晨星）或 "/T"（昏星）
        - t_o_m (float): 月亮角距（度）
        - mn_illu (float): 月亮照明度（%）

    Raises:
        KeyError: response 中缺少 "result" 字段。
        ValueError: 未找到有效的星历数据行（$$SOE … $$EOE 为空）。
    """
    result_text: str = response["result"]

    # 提取 $$SOE … $$EOE 之间的内容
    soe_idx = result_text.find("$$SOE")
    eoe_idx = result_text.find("$$EOE")
    if soe_idx == -1 or eoe_idx == -1:
        raise ValueError("Horizons 响应中未找到 $$SOE / $$EOE 标记")

    table_block = result_text[soe_idx + len("$$SOE"):eoe_idx]

    records: list[dict[str, Any]] = []
    for line in table_block.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        raw_date, t_mag, r, delta, s_o_t, flag, t_o_m, mn_illu = m.groups()
        records.append({
            "date": _parse_date(raw_date),
            "t_mag": float(t_mag),
            "r": float(r),
            "delta": float(delta),
            "s_o_t": float(s_o_t),
            "s_o_t_flag": flag,
            "t_o_m": float(t_o_m),
            "mn_illu": float(mn_illu),
        })

    if not records:
        raise ValueError("Horizons 响应解析结果为空，请检查 Quantities 配置")

    return records


# ── 测试入口 ───────────────────────────────────────────────────────────────────

def _run_tests(sample_path: str = "data/horizons_sample.json") -> None:
    """
    使用 data/horizons_sample.json 验证解析结果。
    预期：2026-04-01 行 r≈0.6698, Δ≈1.2487, T-mag≈10.424, S-O-T=32.31/L, MN_Illu≈98.74
    """
    with open(sample_path, encoding="utf-8") as f:
        raw = json.load(f)

    records = parse_horizons_response(raw)

    print(f"共解析 {len(records)} 条记录：\n")
    print(f"{'日期':<12} {'T-mag':>6} {'r(AU)':>12} {'delta(AU)':>16} {'S-O-T':>7} {'flag':>4} {'T-O-M':>7} {'MN_Illu%':>9}")
    print("-" * 78)
    for rec in records:
        print(
            f"{rec['date']:<12} {rec['t_mag']:>6.3f} {rec['r']:>12.9f} "
            f"{rec['delta']:>16.11f} {rec['s_o_t']:>7.4f} {rec['s_o_t_flag']:>4} "
            f"{rec['t_o_m']:>7.1f} {rec['mn_illu']:>9.4f}"
        )

    # 对拍验证：2026-04-01 行
    first = records[0]
    assert first["date"] == "2026-04-01", f"日期解析错误：{first['date']}"
    assert abs(first["r"] - 0.6698) < 0.0001, f"r 偏差过大：{first['r']}"
    assert abs(first["delta"] - 1.2487) < 0.0001, f"delta 偏差过大：{first['delta']}"
    assert abs(first["t_mag"] - 10.424) < 0.001, f"t_mag 偏差过大：{first['t_mag']}"
    assert abs(first["s_o_t"] - 32.3121) < 0.001, f"s_o_t 偏差过大：{first['s_o_t']}"
    assert first["s_o_t_flag"] == "/L", f"s_o_t_flag 错误：{first['s_o_t_flag']}"
    assert abs(first["mn_illu"] - 98.7411) < 0.001, f"mn_illu 偏差过大：{first['mn_illu']}"

    print("\n对拍验证通过（2026-04-01 行所有字段正确）。")


if __name__ == "__main__":
    import sys
    sample = sys.argv[1] if len(sys.argv) > 1 else "data/horizons_sample.json"
    _run_tests(sample)


# ══════════════════════════════════════════════════════════════════════════════
# Horizons 查询 B：topocentric AZ/EL（用户触发，实时查询）
# ══════════════════════════════════════════════════════════════════════════════

import time as _time_module
from datetime import date as _date_cls, datetime as _dt_cls, timedelta as _td

import requests as _requests

_HORIZONS_BASE = "https://ssd.jpl.nasa.gov/api/horizons.api"

# Matches AZ/EL rows from Horizons OBSERVER table (Quantities=4).
# Format: "YYYY-Mon-DD HH:MM [flags]   AZ   EL"
# Flags are optional 0-2 chars (A, N, Cr, *, etc.) or absent.
_AZ_EL_ROW_RE = re.compile(
    r"^\s*(\d{4}-[A-Za-z]{3}-\d{2})\s+(\d{2}:\d{2})\s+\S*\s+([\d.]+)\s+([-\d.]+)"
)


def _az_el_to_minutes(time_str: str) -> int:
    """Convert "HH:MM" to total minutes since midnight."""
    return int(time_str[:2]) * 60 + int(time_str[3:5])


def _minutes_to_hhmm(total: int) -> str:
    """Convert integer minutes (may exceed 1440) to "HH:MM", clamped to 24h."""
    total = total % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_az_el_response(
    response: dict[str, Any],
    utc_offset_hours: int = 0,
) -> list[dict[str, Any]]:
    """
    Parse Horizons AZ/EL observer table (Quantities=4).

    Args:
        response: Horizons API JSON response dict containing "result".
        utc_offset_hours: Add this to UTC times to obtain local times
            (e.g. 8 for China Standard Time).

    Returns:
        Chronologically sorted list of records::

            [{"time": "HH:MM", "az": float, "el": float}, ...]

        where ``time`` is local time (HH:MM, 24h) and midnight-crossing
        is handled correctly.

    Raises:
        KeyError: "result" key absent.
        ValueError: $$SOE/$$EOE markers missing, or no valid rows found.
    """
    result_text: str = response["result"]
    soe_idx = result_text.find("$$SOE")
    eoe_idx = result_text.find("$$EOE")
    if soe_idx == -1 or eoe_idx == -1:
        raise ValueError("Horizons 响应中未找到 $$SOE / $$EOE 标记")

    table_block = result_text[soe_idx + len("$$SOE"):eoe_idx]
    records: list[dict[str, Any]] = []

    for line in table_block.splitlines():
        m = _AZ_EL_ROW_RE.match(line)
        if not m:
            continue
        _date_str, time_utc, az_str, el_str = m.groups()

        if utc_offset_hours:
            total_min = _az_el_to_minutes(time_utc) + utc_offset_hours * 60
            local_time = _minutes_to_hhmm(total_min)
        else:
            local_time = time_utc

        records.append({
            "time": local_time,
            "az":   round(float(az_str), 1),
            "el":   round(float(el_str), 1),
        })

    if not records:
        raise ValueError("未从 Horizons AZ/EL 响应中解析到任何行，请检查 QUANTITIES='4' 配置")

    return records


def extract_target_passage(az_el_data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Extract rise/peak/set from a chronological AZ/EL time series.

    The function uses linear interpolation to estimate the exact minute when
    the target's elevation crosses 0°.

    Args:
        az_el_data: List of ``{"time": "HH:MM", "az": float, "el": float}``
            records in chronological order (local time).  Midnight-crossing
            sequences are supported.

    Returns:
        ``{"rise_time", "peak_time", "set_time", "peak_altitude_deg"}``

        All time values are ``"HH:MM"`` strings (local time, 24h).
        Fields are ``None`` when the event does not occur within the data
        window; a ``"note"`` key is added with a human-readable explanation.

    Edge cases handled:
        - Target never rises  → ``rise_time``, ``peak_time``, ``set_time`` all ``None``
        - Already above horizon at window start → ``rise_time`` is ``None``
        - Never sets within window → ``set_time`` is ``None``
    """
    if not az_el_data:
        return {
            "rise_time": None, "peak_time": None,
            "set_time": None, "peak_altitude_deg": None,
            "note": "AZ/EL 数据为空",
        }

    # Build a monotonically increasing minutes sequence to handle midnight crossing.
    mono: list[tuple[int, float, float]] = []   # (minutes, az, el)
    prev_min = -1
    day_offset = 0
    for rec in az_el_data:
        m = _az_el_to_minutes(rec["time"])
        if m < prev_min:      # midnight wrap detected
            day_offset += 24 * 60
        mono.append((m + day_offset, rec["az"], rec["el"]))
        prev_min = m

    els = [p[2] for p in mono]
    max_el = max(els)

    if max_el <= 0:
        return {
            "rise_time": None, "peak_time": None,
            "set_time": None, "peak_altitude_deg": None,
            "note": "目标在整个查询窗口内均低于地平线",
        }

    note_parts: list[str] = []

    # ── Rise time ──────────────────────────────────────────────────────────
    rise_min: int | None = None
    if mono[0][2] > 0:
        note_parts.append("查询窗口开始时目标已在地平线以上，升起时间未捕获")
    else:
        for i in range(len(mono) - 1):
            el_a, el_b = mono[i][2], mono[i + 1][2]
            if el_a <= 0 < el_b:
                frac = -el_a / (el_b - el_a)
                rise_min = int(round(mono[i][0] + frac * (mono[i + 1][0] - mono[i][0])))
                break

    # ── Peak ───────────────────────────────────────────────────────────────
    peak_idx = max(range(len(els)), key=lambda i: els[i])
    peak_min = mono[peak_idx][0]
    peak_el  = round(els[peak_idx], 1)

    # ── Set time ───────────────────────────────────────────────────────────
    set_min: int | None = None
    for i in range(peak_idx, len(mono) - 1):
        el_a, el_b = mono[i][2], mono[i + 1][2]
        if el_a >= 0 > el_b:
            frac = el_a / (el_a - el_b)
            set_min = int(round(mono[i][0] + frac * (mono[i + 1][0] - mono[i][0])))
            break
    if set_min is None and mono[-1][2] > 0:
        note_parts.append("目标在查询窗口结束时仍在地平线以上，落下时间未捕获")

    result: dict[str, Any] = {
        "rise_time":         _minutes_to_hhmm(rise_min) if rise_min is not None else None,
        "peak_time":         _minutes_to_hhmm(peak_min),
        "set_time":          _minutes_to_hhmm(set_min)  if set_min  is not None else None,
        "peak_altitude_deg": peak_el,
    }
    if note_parts:
        result["note"] = "；".join(note_parts)
    return result


def query_horizons_topocentric(
    command: str,
    latitude: float,
    longitude: float,
    date: str,
    timezone_offset: int = 8,
    step_size: str = "30m",
    timeout: int = 10,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """
    Query Horizons for apparent AZ/EL of a target seen from a ground location.

    Queries one night: from 17:00 local time (approximately civil twilight)
    to 07:00 local time the following morning.

    Args:
        command:          Horizons target designation, e.g. ``"C/2025 R3"``.
        latitude:         Observer latitude in decimal degrees (north positive).
        longitude:        Observer longitude in decimal degrees (east positive).
        date:             Local observation date, ISO format ``"YYYY-MM-DD"``.
        timezone_offset:  UTC offset in integer hours (default 8 for CST).
        step_size:        Horizons STEP_SIZE parameter (default ``"30m"``).
        timeout:          HTTP request timeout in seconds.
        max_retries:      Number of additional attempts on transient failure.

    Returns:
        Chronologically sorted list of ``{"time": "HH:MM", "az": float, "el": float}``
        records in local time.

    Raises:
        requests.HTTPError: Non-transient HTTP error.
        ValueError: Response parsing failed.
    """
    date_obj = _date_cls.fromisoformat(date)

    # UTC window: 17:00 local → 07:00 local next day, expressed as UTC offsets
    # from midnight of the local date converted to UTC reference.
    start_utc_h = 17 - timezone_offset   # hours from local-date midnight (UTC)
    stop_utc_h  = 31 - timezone_offset   # 07:00 next local day from same reference

    def _fmt(base: _date_cls, extra_h: int) -> str:
        dt = _dt_cls(base.year, base.month, base.day) + _td(hours=extra_h)
        return dt.strftime("%Y-%m-%d %H:%M")

    start_str = _fmt(date_obj, start_utc_h)
    stop_str  = _fmt(date_obj, stop_utc_h)

    params = {
        "format":       "json",
        "COMMAND":      f"'{command}'",
        "CENTER":       "'coord'",
        "SITE_COORD":   f"'{longitude},{latitude},0'",
        "COORD_TYPE":   "'GEODETIC'",
        "MAKE_EPHEM":   "YES",
        "TABLE_TYPE":   "OBSERVER",
        "START_TIME":   f"'{start_str}'",
        "STOP_TIME":    f"'{stop_str}'",
        "STEP_SIZE":    f"'{step_size}'",
        "QUANTITIES":   "'4'",
    }

    for attempt in range(max_retries + 1):
        try:
            resp = _requests.get(_HORIZONS_BASE, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "result" not in data:
                raise ValueError(f"Horizons 响应缺少 result 字段：{list(data.keys())}")
            return parse_az_el_response(data, utc_offset_hours=timezone_offset)
        except (_requests.Timeout, _requests.ConnectionError) as exc:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            _time_module.sleep(wait)
