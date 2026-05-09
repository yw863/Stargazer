"""
单元测试：horizons_parser 新增函数 + twilight_calculator

运行方式（项目根目录）：
  pytest backend/tests/test_new_functions.py -v

或直接运行（纯 assert，无需 pytest）：
  python3 backend/tests/test_new_functions.py
"""

import sys
from pathlib import Path

# 将 backend/tools 加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from horizons_parser import (
    _az_el_to_minutes,
    _minutes_to_hhmm,
    extract_target_passage,
    parse_az_el_response,
)


# ══════════════════════════════════════════════════════════════════════════════
# 辅助工具函数
# ══════════════════════════════════════════════════════════════════════════════

def test_az_el_to_minutes_basic():
    assert _az_el_to_minutes("19:00") == 19 * 60
    assert _az_el_to_minutes("00:30") == 30
    assert _az_el_to_minutes("23:59") == 23 * 60 + 59


def test_minutes_to_hhmm_basic():
    assert _minutes_to_hhmm(19 * 60) == "19:00"
    assert _minutes_to_hhmm(0) == "00:00"
    assert _minutes_to_hhmm(24 * 60 + 30) == "00:30"   # 跨午夜折叠


# ══════════════════════════════════════════════════════════════════════════════
# parse_az_el_response
# ══════════════════════════════════════════════════════════════════════════════

_FAKE_AZ_EL_RESPONSE = {
    "result": (
        "$$SOE\n"
        " 2026-Apr-22 17:00      35.488111 -37.463132\n"
        " 2026-Apr-22 17:30      42.869217 -33.470744\n"
        " 2026-Apr-22 20:00 A    69.403954  -7.082908\n"
        " 2026-Apr-22 20:30 N    73.424102  -1.080952\n"
        " 2026-Apr-22 21:00 Cr   77.244502   5.045640\n"
        " 2026-Apr-22 21:30 *    80.948957  11.264756\n"
        " 2026-Apr-22 22:00 *    84.621464  17.548400\n"
        "$$EOE\n"
    )
}


def test_parse_az_el_response_utc():
    records = parse_az_el_response(_FAKE_AZ_EL_RESPONSE, utc_offset_hours=0)
    assert len(records) == 7
    assert records[0]["time"] == "17:00"
    assert records[0]["az"] == 35.5
    assert records[0]["el"] == -37.5


def test_parse_az_el_response_utc8():
    """UTC+8：每个时间点 +8h，检查午夜跨越。"""
    records = parse_az_el_response(_FAKE_AZ_EL_RESPONSE, utc_offset_hours=8)
    # 17:00 UTC + 8h = 01:00 next day
    assert records[0]["time"] == "01:00"
    # 21:00 UTC + 8h = 05:00 next day
    assert records[4]["time"] == "05:00"


def test_parse_az_el_response_missing_markers():
    try:
        parse_az_el_response({"result": "no markers here"})
        raise AssertionError("应抛出 ValueError，但未抛出")
    except ValueError:
        pass  # 预期行为


# ══════════════════════════════════════════════════════════════════════════════
# extract_target_passage — 正常情况
# ══════════════════════════════════════════════════════════════════════════════

# AZ/EL 序列：目标从负仰角升起，在约 21:30 峰值，再落下
_NORMAL_AZ_EL = [
    {"time": "19:00", "az": 262.0, "el": -5.0},
    {"time": "19:30", "az": 270.0, "el":  0.0},  # 恰好在地平线
    {"time": "20:00", "az": 278.0, "el":  7.0},
    {"time": "20:30", "az": 290.0, "el": 14.0},
    {"time": "21:00", "az": 310.0, "el": 21.0},
    {"time": "21:30", "az": 325.0, "el": 24.0},  # 峰值
    {"time": "22:00", "az": 335.0, "el": 19.0},
    {"time": "22:30", "az": 342.0, "el": 12.0},
    {"time": "23:00", "az": 348.0, "el":  4.0},
    {"time": "23:30", "az": 353.0, "el": -3.0},
]


def test_extract_target_passage_normal():
    result = extract_target_passage(_NORMAL_AZ_EL)

    assert result["peak_altitude_deg"] == 24.0
    assert result["peak_time"] == "21:30"
    assert result["set_time"] is not None
    assert "note" not in result


def test_extract_target_passage_rise_interpolation():
    """升起时刻应在 19:00（el=-5）和 19:30（el=0）之间，线性插值应为 19:30 精确。"""
    # 构造更精确的边界
    data = [
        {"time": "19:00", "az": 260.0, "el": -10.0},
        {"time": "20:00", "az": 270.0, "el":  10.0},  # 跨越 0° 的区间
    ]
    result = extract_target_passage(data)
    # 插值：-10 → 10，在区间中点（19:30）过零
    assert result["rise_time"] == "19:30", f"期望 19:30，得到 {result['rise_time']}"


def test_extract_target_passage_set_interpolation():
    """落下时刻线性插值测试。"""
    data = [
        {"time": "21:00", "az": 300.0, "el": 20.0},
        {"time": "22:00", "az": 330.0, "el": 10.0},
        {"time": "23:00", "az": 350.0, "el":  0.0},   # 恰好
        {"time": "23:30", "az": 355.0, "el": -5.0},
    ]
    result = extract_target_passage(data)
    # 峰值在 21:00（el=20）
    assert result["peak_time"] == "21:00"
    # 落下内插：22:00 el=10 → 23:00 el=0，el 在 23:00 精确过零
    assert result["set_time"] is not None


# ══════════════════════════════════════════════════════════════════════════════
# extract_target_passage — 边界情况
# ══════════════════════════════════════════════════════════════════════════════

def test_extract_target_passage_never_rises():
    """整晚仰角为负 → 所有字段 None。"""
    data = [
        {"time": "20:00", "az": 100.0, "el": -10.0},
        {"time": "21:00", "az": 110.0, "el": -8.0},
        {"time": "22:00", "az": 120.0, "el": -5.0},
    ]
    result = extract_target_passage(data)
    assert result["rise_time"]         is None
    assert result["peak_time"]         is None
    assert result["set_time"]          is None
    assert result["peak_altitude_deg"] is None
    assert "note" in result


def test_extract_target_passage_already_above():
    """窗口开始时已在地平线以上 → rise_time=None，有 note，peak/set 正常。"""
    data = [
        {"time": "19:00", "az": 260.0, "el": 10.0},
        {"time": "20:00", "az": 280.0, "el": 20.0},  # 峰值
        {"time": "21:00", "az": 310.0, "el": 10.0},
        {"time": "22:00", "az": 340.0, "el": -5.0},
    ]
    result = extract_target_passage(data)
    assert result["rise_time"] is None
    assert result["peak_time"] == "20:00"
    assert result["set_time"]  is not None
    assert "note" in result


def test_extract_target_passage_no_set():
    """窗口结束时仍在地平线以上 → set_time=None，有 note。"""
    data = [
        {"time": "19:00", "az": 260.0, "el": -5.0},
        {"time": "20:00", "az": 280.0, "el":  5.0},
        {"time": "21:00", "az": 310.0, "el": 20.0},  # 峰值
        {"time": "22:00", "az": 340.0, "el": 15.0},
        {"time": "23:00", "az": 355.0, "el":  8.0},
    ]
    result = extract_target_passage(data)
    assert result["rise_time"] is not None
    assert result["set_time"]  is None
    assert "note" in result


def test_extract_target_passage_midnight_crossing():
    """跨午夜序列（22:00 → 01:00）不应导致时序错误。"""
    data = [
        {"time": "22:00", "az": 270.0, "el": -5.0},
        {"time": "22:30", "az": 275.0, "el":  2.0},
        {"time": "23:00", "az": 280.0, "el": 12.0},
        {"time": "23:30", "az": 290.0, "el": 20.0},
        {"time": "00:00", "az": 310.0, "el": 25.0},  # 午夜后，峰值
        {"time": "00:30", "az": 330.0, "el": 18.0},
        {"time": "01:00", "az": 345.0, "el":  8.0},
        {"time": "01:30", "az": 355.0, "el": -3.0},
    ]
    result = extract_target_passage(data)
    assert result["peak_time"]         == "00:00"
    assert result["peak_altitude_deg"] == 25.0
    assert result["rise_time"]         is not None
    assert result["set_time"]          is not None


def test_extract_target_passage_empty():
    result = extract_target_passage([])
    assert result["peak_altitude_deg"] is None
    assert "note" in result


# ══════════════════════════════════════════════════════════════════════════════
# twilight_calculator（集成测试，需要 skyfield + 网络首次下载）
# ══════════════════════════════════════════════════════════════════════════════

def test_calculate_twilight_shanghai():
    """
    上海 2026-04-22 晨昏时刻集成测试。
    依赖 skyfield 和 de421.bsp（首次运行需要网络）。
    """
    try:
        from twilight_calculator import calculate_twilight
    except ImportError:
        import pytest
        pytest.skip("skyfield 未安装，跳过晨昏集成测试")

    result = calculate_twilight(31.23, 121.47, "2026-04-22", timezone_offset=8)

    required_keys = ("sunset", "civil_dusk", "astro_dusk",
                     "astro_dawn", "civil_dawn", "sunrise", "moon_set")
    for key in required_keys:
        assert key in result, f"缺少字段 '{key}'"

    # 非 None 字段应为 HH:MM 格式
    for key in ("sunset", "civil_dusk", "astro_dusk",
                "astro_dawn", "civil_dawn", "sunrise"):
        val = result[key]
        assert val is not None, f"'{key}' 不应为 None（上海无极昼极夜）"
        assert len(val) == 5 and val[2] == ":", f"'{key}' 格式错误：{val}"

    # 时序检查：黄昏组（同一晚间，字符串直接比较）和黎明组（次日早晨）分开验证
    # 跨午夜情况下不能对 astro_dusk 和 astro_dawn 做字符串大小比较
    dusk_keys  = ("sunset", "civil_dusk", "astro_dusk")
    dawn_keys  = ("astro_dawn", "civil_dawn", "sunrise")
    for keys in (dusk_keys, dawn_keys):
        vals = [result[k] for k in keys]
        for i in range(len(vals) - 1):
            a, b = vals[i], vals[i + 1]
            if a and b:
                assert a < b, f"时序错误：{keys[i]}={a} 应早于 {keys[i+1]}={b}"

    # 夜间方向确认：astro_dusk 在傍晚（应 > "12:00"），astro_dawn 在凌晨（应 < "12:00"）
    if result["astro_dusk"] and result["astro_dawn"]:
        assert result["astro_dusk"] > "12:00", "astro_dusk 应在傍晚（>12:00）"
        assert result["astro_dawn"] < "12:00", "astro_dawn 应在凌晨（<12:00）"


# ══════════════════════════════════════════════════════════════════════════════
# 直接运行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in test_fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__} — {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
