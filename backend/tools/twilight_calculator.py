"""
晨昏时刻计算器

基于 skyfield 计算指定地点在指定日期的日出日落、各阶段晨昏和月落时刻。
纯本地计算，不调用任何外部 API。

首次运行时 skyfield 会自动下载 de421.bsp（~17 MB）到 backend/ 目录。
后续调用使用缓存，加载耗时 < 1 ms。
"""

from __future__ import annotations

from datetime import date as _date_cls, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

# de421.bsp 存储在 backend/ 目录下（与本文件同级的上一级）
_BSP_DIR = str(Path(__file__).parent.parent)


@lru_cache(maxsize=1)
def _get_eph():
    """返回 skyfield de421.bsp 星历对象（全局单例，首次调用自动下载）。"""
    from skyfield.api import Loader
    loader = Loader(_BSP_DIR)
    return loader("de421.bsp")


@lru_cache(maxsize=1)
def _get_ts():
    """返回 skyfield 时标（全局单例）。"""
    from skyfield.api import load
    return load.timescale()


def calculate_twilight(
    latitude: float,
    longitude: float,
    date_str: str,
    timezone_offset: int = 8,
) -> dict[str, Optional[str]]:
    """
    计算指定地点在指定日期的晨昏时刻和月落时刻。

    搜索窗口：本地日期当天正午 → 次日正午，涵盖完整的日落到日出周期。

    Args:
        latitude:         观测者纬度（度，北正南负）。
        longitude:        观测者经度（度，东正西负）。
        date_str:         本地日期，ISO 格式 ``"YYYY-MM-DD"``。
        timezone_offset:  UTC 偏移小时数，默认 8（北京时间 CST）。

    Returns:
        字典，所有时间字段均为本地时间 ``"HH:MM"`` 字符串（24h 制）::

            {
                "sunset":     "17:58",  # 太阳中心高度角 = -0.833°（日落）
                "civil_dusk": "18:26",  # 太阳高度角 = -6°
                "astro_dusk": "18:53",  # 太阳高度角 = -18°
                "astro_dawn": "04:05",  # 太阳高度角 = -18°（黎明方向）
                "civil_dawn": "04:33",  # 太阳高度角 = -6°
                "sunrise":    "05:02",  # 太阳中心高度角 = -0.833°（日出）
                "moon_set":   "22:30",  # 日落后当晚第一次月落；整晚不落则为 null
            }

    Edge cases:
        - 极昼/极夜地区：无法确定的字段设为 ``None``。
        - 月亮整晚不落：``moon_set`` 为 ``None``。

    Raises:
        ImportError: skyfield 未安装。
        FileNotFoundError: de421.bsp 下载失败（网络问题）。
    """
    from skyfield import almanac
    from skyfield.api import wgs84

    utc_tz = timezone.utc
    offset = timedelta(hours=timezone_offset)

    date_obj = _date_cls.fromisoformat(date_str)
    next_date = date_obj + timedelta(days=1)

    # 搜索窗口：本地正午 → 次日正午（转换为 UTC）
    local_noon_start = datetime(date_obj.year,  date_obj.month,  date_obj.day,  12, tzinfo=utc_tz) - offset
    local_noon_end   = datetime(next_date.year, next_date.month, next_date.day, 12, tzinfo=utc_tz) - offset

    ts  = _get_ts()
    eph = _get_eph()
    t0  = ts.from_datetime(local_noon_start)
    t1  = ts.from_datetime(local_noon_end)

    location = wgs84.latlon(latitude, longitude)

    def _to_local(t) -> str:
        """skyfield Time → 本地时间 "HH:MM"。"""
        dt = t.utc_datetime() + offset
        return dt.strftime("%H:%M")

    # ── 太阳晨昏 ───────────────────────────────────────────────────────────
    # dark_twilight_day 值定义：
    #   4 = 白天（太阳 > -0.8333°），3 = 民用暮光，2 = 航海暮光，
    #   1 = 天文暮光，0 = 天文夜
    result: dict[str, Optional[str]] = {
        "sunset": None, "civil_dusk": None, "astro_dusk": None,
        "astro_dawn": None, "civil_dawn": None, "sunrise": None,
        "moon_set": None,
    }

    f_sun = almanac.dark_twilight_day(eph, location)
    sun_times, sun_events = almanac.find_discrete(t0, t1, f_sun)

    # 追踪前一个状态值，用于判断过渡方向（上升 or 下降）
    prev_val = int(f_sun(t0))
    sunset_utc: Optional[datetime] = None

    for t, new_val in zip(sun_times, sun_events):
        new_val = int(new_val)
        if prev_val > new_val:
            # 下降方向（黄昏）
            if new_val == 3:
                result["sunset"] = _to_local(t)
                sunset_utc = t.utc_datetime()
            elif new_val == 2:
                result["civil_dusk"] = _to_local(t)
            elif new_val == 0:
                result["astro_dusk"] = _to_local(t)
        else:
            # 上升方向（黎明）
            if new_val == 1:
                result["astro_dawn"] = _to_local(t)
            elif new_val == 3:
                result["civil_dawn"] = _to_local(t)
            elif new_val == 4:
                result["sunrise"] = _to_local(t)
        prev_val = new_val

    # ── 月落 ───────────────────────────────────────────────────────────────
    # 取日落后当晚第一次月落（setting = event value 0）
    f_moon = almanac.risings_and_settings(eph, eph["moon"], location)
    moon_times, moon_events = almanac.find_discrete(t0, t1, f_moon)

    for t, event in zip(moon_times, moon_events):
        if int(event) == 0:   # 月落
            if sunset_utc is None or t.utc_datetime() > sunset_utc:
                result["moon_set"] = _to_local(t)
                break

    return result


# ── CLI 自测入口 ───────────────────────────────────────────────────────────────

def _run_tests() -> None:
    """
    快速冒烟测试：以上海坐标计算 2026-04-22 的晨昏时刻。
    预期：日落约 18:00 左右，天文昏约 19:00 左右（北京时间）。
    """
    result = calculate_twilight(31.23, 121.47, "2026-04-22", timezone_offset=8)
    print("上海 2026-04-22 晨昏时刻：")
    for k, v in result.items():
        print(f"  {k:<14}: {v}")

    assert result["sunset"]     is not None, "日落时间未计算"
    assert result["civil_dusk"] is not None, "民用昏时间未计算"
    assert result["astro_dusk"] is not None, "天文昏时间未计算"
    assert result["astro_dawn"] is not None, "天文曙时间未计算"
    assert result["civil_dawn"] is not None, "民用曙时间未计算"
    assert result["sunrise"]    is not None, "日出时间未计算"

    # 顺序检查：日落 < 民昏 < 天昏 < 天曙 < 民曙 < 日出
    ordered = [result[k] for k in ("sunset", "civil_dusk", "astro_dusk",
                                   "astro_dawn", "civil_dawn", "sunrise")]
    for i in range(len(ordered) - 1):
        if ordered[i] and ordered[i + 1]:
            assert ordered[i] < ordered[i + 1], (
                f"时序错误：{ordered[i]} 应早于 {ordered[i + 1]}"
            )

    print("\n自测通过。")


if __name__ == "__main__":
    _run_tests()
