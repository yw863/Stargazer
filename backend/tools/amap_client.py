"""
高德地图路径规划客户端

调用高德地图 Web 服务 API，查询公共交通和驾车路线。
API Key 通过环境变量 AMAP_WEB_SERVICE_KEY 注入，不得硬编码。

支持的查询模式：
  - 公共交通（跨城）：/v3/direction/transit/integrated
  - 驾车：/v3/direction/driving

坐标格式：高德 API 统一使用 "经度,纬度"（lon,lat）。
"""

import os
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _build_session() -> requests.Session:
    """创建带重试逻辑的 Session（网络抖动时自动重试 3 次）。"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_SESSION = _build_session()

# 高德 API 根地址
_BASE_URL = "https://restapi.amap.com"
_TIMEOUT = 10  # 秒


def _get_key() -> str:
    """从环境变量读取高德 Web 服务 Key。"""
    key = os.environ.get("AMAP_WEB_SERVICE_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "环境变量 AMAP_WEB_SERVICE_KEY 未设置。"
            "请在 backend/.env 中配置，或在运行环境中注入。"
        )
    return key


def _coords(lat: float, lon: float) -> str:
    """将纬度、经度转为高德坐标字符串（经度在前）。"""
    return f"{lon},{lat}"


def _parse_transit_route(route: dict) -> dict[str, Any]:
    """
    从高德公交 /transit/integrated 响应中提取最优方案摘要。
    取 transits[0]（高德默认按综合评分排序）。

    注意：高德 API 的地铁/火车/公交信息统一放在 segment.bus.buslines 中，
    segment.railway 字段在跨城查询时通常为空。
    """
    transits = route.get("transits") or []
    if not transits:
        return {"mode": "公共交通", "duration_minutes": None, "summary": "无可用方案", "transfers": 0}

    best = transits[0]
    duration_sec = int(best.get("duration", 0))
    duration_min = round(duration_sec / 60)

    segments = best.get("segments", [])
    steps = []
    transit_seg_count = 0  # 记录乘车段（不含步行）用于计算换乘次数

    for seg in segments:
        bus = seg.get("bus")
        walking = seg.get("walking")

        if bus:
            buslines = bus.get("buslines") or []
            if buslines:
                bl = buslines[0]
                line_name = bl.get("name", "公交")
                dep = (bl.get("departure_stop") or {}).get("name", "")
                arr = (bl.get("arrival_stop") or {}).get("name", "")
                # 截断过长的线路名（如高铁线路名含完整区间）
                if len(line_name) > 20:
                    line_name = line_name[:20] + "…"
                label = f"{line_name}"
                if dep and arr:
                    label += f"（{dep}→{arr}）"
                steps.append(label)
                transit_seg_count += 1
        elif walking:
            walk_dist_raw = walking.get("distance", 0)
            walk_dist = int(walk_dist_raw) if walk_dist_raw else 0
            if walk_dist > 300:
                steps.append(f"步行 {walk_dist}m")

    summary = " → ".join(steps) if steps else "详见地图"
    transfers = max(0, transit_seg_count - 1)

    return {
        "mode": "公共交通",
        "duration_minutes": duration_min,
        "summary": summary,
        "transfers": transfers,
    }


def _parse_driving_route(route: dict) -> dict[str, Any]:
    """从高德驾车 /direction/driving 响应中提取最优方案摘要。"""
    paths = route.get("paths") or []
    if not paths:
        return {"mode": "自驾", "duration_minutes": None, "summary": "无可用方案"}

    best = paths[0]
    duration_sec = int(best.get("duration", 0))
    duration_min = round(duration_sec / 60)

    # 取途经道路名称（前 3 条主干道）
    steps = best.get("steps", [])
    roads = []
    for step in steps:
        road = step.get("road", "").strip()
        if road and road not in roads:
            roads.append(road)
        if len(roads) >= 3:
            break
    summary = " → ".join(roads) if roads else "详见地图"

    return {
        "mode": "自驾",
        "duration_minutes": duration_min,
        "summary": summary,
    }


def get_transit_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    origin_city: str = "上海",
    dest_city: str = "",
) -> dict[str, Any]:
    """
    查询公共交通路线。

    Args:
        origin_lat / origin_lon : 出发地纬度、经度
        dest_lat / dest_lon     : 目的地纬度、经度
        origin_city             : 出发地城市名（如"上海"），用于跨城查询
        dest_city               : 目的地城市名，留空时高德自动判断

    Returns:
        {mode, duration_minutes, summary, transfers}
    """
    params: dict[str, Any] = {
        "key": _get_key(),
        "origin": _coords(origin_lat, origin_lon),
        "destination": _coords(dest_lat, dest_lon),
        "city": origin_city,
        "output": "json",
        "extensions": "all",
    }
    if dest_city:
        params["cityd"] = dest_city

    resp = _SESSION.get(
        f"{_BASE_URL}/v3/direction/transit/integrated",
        params=params,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "1":
        info = data.get("info", "未知错误")
        return {"mode": "公共交通", "duration_minutes": None, "summary": f"API 错误：{info}", "transfers": 0}

    route = data.get("route", {})
    return _parse_transit_route(route)


def get_driving_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> dict[str, Any]:
    """
    查询驾车路线。

    Args:
        origin_lat / origin_lon : 出发地纬度、经度
        dest_lat / dest_lon     : 目的地纬度、经度

    Returns:
        {mode, duration_minutes, summary}
    """
    params = {
        "key": _get_key(),
        "origin": _coords(origin_lat, origin_lon),
        "destination": _coords(dest_lat, dest_lon),
        "output": "json",
        "extensions": "base",
    }

    resp = _SESSION.get(
        f"{_BASE_URL}/v3/direction/driving",
        params=params,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "1":
        info = data.get("info", "未知错误")
        return {"mode": "自驾", "duration_minutes": None, "summary": f"API 错误：{info}"}

    route = data.get("route", {})
    return _parse_driving_route(route)


def get_transit_options(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    transport: str = "no_car",
    origin_city: str = "上海",
    dest_city: str = "",
) -> list[dict[str, Any]]:
    """
    根据用户交通方式偏好，返回路线选项列表。

    Args:
        transport: "no_car"（仅公共交通）或 "with_car"（公交+自驾）

    Returns:
        list of {mode, duration_minutes, summary[, transfers]}
    """
    options = []

    transit = get_transit_route(origin_lat, origin_lon, dest_lat, dest_lon, origin_city, dest_city)
    options.append(transit)

    if transport == "with_car":
        time.sleep(0.2)  # 避免高德 API 频率限制
        driving = get_driving_route(origin_lat, origin_lon, dest_lat, dest_lon)
        options.append(driving)

    return options


# ── 测试入口 ───────────────────────────────────────────────────────────────────

def _run_tests() -> None:
    """
    测试用例：上海人民广场 → 天荒坪（安吉观星地，约 166km）
    上海: 31.2304° N, 121.4737° E
    天荒坪: 30.5789° N, 119.6812° E（近似坐标）
    """
    # 加载本地 .env（仅用于本地测试；Dify 部署时由平台注入环境变量）
    try:
        from dotenv import load_dotenv
        load_dotenv("backend/.env")
    except ImportError:
        pass

    origin = (31.2304, 121.4737)   # 上海人民广场
    dest   = (30.5789, 119.6812)   # 天荒坪附近

    print("── 测试 1：仅公共交通（上海 → 天荒坪）────────────────────────")
    options_no_car = get_transit_options(*origin, *dest, transport="no_car", origin_city="上海", dest_city="安吉")
    for opt in options_no_car:
        print(f"  {opt['mode']}: {opt['duration_minutes']} 分钟")
        print(f"  路线: {opt['summary']}")
        if "transfers" in opt:
            print(f"  换乘: {opt['transfers']} 次")
    print()

    print("── 测试 2：公共交通 + 自驾（上海 → 天荒坪）───────────────────")
    options_with_car = get_transit_options(*origin, *dest, transport="with_car", origin_city="上海", dest_city="安吉")
    for opt in options_with_car:
        print(f"  {opt['mode']}: {opt['duration_minutes']} 分钟")
        print(f"  路线: {opt['summary']}")
    print()

    # 基础断言
    assert len(options_no_car) == 1
    assert len(options_with_car) == 2
    assert options_no_car[0]["mode"] == "公共交通"
    transit_min = options_no_car[0]["duration_minutes"]
    assert transit_min is None or transit_min > 0, "时长应为正数"

    driving_opt = next(o for o in options_with_car if o["mode"] == "自驾")
    driving_min = driving_opt["duration_minutes"]
    assert driving_min is None or driving_min > 0, "驾车时长应为正数"

    if transit_min and driving_min:
        print(f"公交 {transit_min} 分钟，自驾 {driving_min} 分钟（差值 {transit_min - driving_min} 分钟）")

    print("所有断言通过。")


if __name__ == "__main__":
    _run_tests()
