"""
Haversine 距离计算工具

输入两组经纬度，输出地球表面直线距离（km）。
用于 Agent 2 的 600km 候选地点预筛，避免调用外部 API。
"""

import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算两点之间的 Haversine 大圆距离。

    Args:
        lat1: 起点纬度（度）
        lon1: 起点经度（度）
        lat2: 终点纬度（度）
        lon2: 终点经度（度）

    Returns:
        两点间直线距离（km），保留两位小数。
    """
    R = 6371.0  # 地球平均半径（km）

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(R * c, 2)


# ── 单元测试 ──────────────────────────────────────────────────────────────────

def _run_tests() -> None:
    # 上海 → 杭州，预期约 166km
    shanghai = (31.23, 121.47)
    hangzhou = (30.27, 120.15)
    dist = haversine(*shanghai, *hangzhou)
    assert 160 <= dist <= 172, f"上海→杭州距离异常：{dist} km（预期 ~166km）"
    print(f"上海 → 杭州：{dist} km  ✓")

    # 同一点距离应为 0
    dist_zero = haversine(31.23, 121.47, 31.23, 121.47)
    assert dist_zero == 0.0, f"同一点距离应为 0，实际：{dist_zero}"
    print(f"同一点距离：{dist_zero} km  ✓")

    # 北京 → 上海，预期约 1068km
    beijing = (39.90, 116.40)
    dist_bj_sh = haversine(*beijing, *shanghai)
    assert 1050 <= dist_bj_sh <= 1090, f"北京→上海距离异常：{dist_bj_sh} km（预期 ~1068km）"
    print(f"北京 → 上海：{dist_bj_sh} km  ✓")

    print("\n所有测试通过。")


if __name__ == "__main__":
    _run_tests()
