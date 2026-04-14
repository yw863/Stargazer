"""
每日定时拟合任务

流程：
1. 读取 data/events.json，筛选 status=active 且 type=comet 的事件
2. 对每个事件：
   a. 调用 COBS API 拉取全量观测记录（JSON 格式）
   b. 调用 Horizons API 查询地心星历（COBS 最早记录日 → 今天+30 天）
   c. 用 comet_model 拟合 H、n
   d. 将拟合结果 + 未来 30 天星历写入 data/cache/{event_id}_fit.json（PRD 6.3 格式）
3. 任意步骤失败时记录错误，跳过当前事件，不覆盖已有缓存

运行方式（项目根目录）：
  python3 backend/daily_job/daily_fit.py

GitHub Actions 每日 UTC 17:00（北京时间 01:00）自动执行。
"""

import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

# 将 backend/tools 加入模块搜索路径
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend" / "tools"))

from cobs_parser import parse_cobs_response
from comet_model import fit_comet_model, predict_magnitude
from horizons_parser import parse_horizons_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────────────────

_EVENTS_PATH = _REPO_ROOT / "data" / "events.json"
_CACHE_DIR   = _REPO_ROOT / "data" / "cache"
_TIMEOUT     = 30   # 秒
_FUTURE_DAYS = 30   # 缓存未来 N 天的星历

_COBS_BASE = "https://cobs.si/api/obs_list.api"
_HORIZONS_BASE = "https://ssd.jpl.nasa.gov/api/horizons.api"


# ── API 调用 ──────────────────────────────────────────────────────────────────

def _fetch_cobs(designation: str) -> dict:
    """拉取 COBS 全量观测记录（JSON 格式）。"""
    resp = requests.get(
        _COBS_BASE,
        params={"format": "json", "des": designation},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_horizons(horizons_id: str, start: str, stop: str) -> dict:
    """
    查询 Horizons 地心星历（Quantities 9,19,20,23,25）。

    Args:
        horizons_id: 如 "C/2025 R3"
        start      : 开始日期，如 "2025-10-01"
        stop       : 结束日期，如 "2026-05-14"
    """
    params = {
        "format": "json",
        "COMMAND": f"'{horizons_id}'",
        "CENTER": "'500@399'",
        "MAKE_EPHEM": "YES",
        "TABLE_TYPE": "OBSERVER",
        "START_TIME": f"'{start}'",
        "STOP_TIME": f"'{stop}'",
        "STEP_SIZE": "'1d'",
        "QUANTITIES": "'9,19,20,23,25'",
    }
    resp = requests.get(_HORIZONS_BASE, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if "result" not in data:
        raise ValueError(f"Horizons 响应缺少 result 字段：{list(data.keys())}")
    return data


# ── 缓存构建 ──────────────────────────────────────────────────────────────────

def _build_cache(
    event_id: str,
    fit_result: dict,
    horizons_all: list[dict],
    today: date,
) -> dict:
    """
    构建符合 PRD 6.3 的缓存 JSON。

    ephemeris 只保留今天起未来 30 天（含今天），同时加入 predicted_mag。
    """
    future_cutoff = today + timedelta(days=_FUTURE_DAYS)
    ephemeris = []
    for rec in horizons_all:
        rec_date = date.fromisoformat(rec["date"])
        if rec_date < today or rec_date > future_cutoff:
            continue
        pred_mag = predict_magnitude(fit_result["H"], fit_result["n"], rec["r"], rec["delta"])
        ephemeris.append({
            "date":         rec["date"],
            "r":            rec["r"],
            "delta":        rec["delta"],
            "t_mag":        rec["t_mag"],
            "predicted_mag": pred_mag,
            "s_o_t":        rec["s_o_t"],
            "s_o_t_flag":   rec["s_o_t_flag"],
            "t_o_m":        rec["t_o_m"],
            "mn_illu":      rec["mn_illu"],
        })

    return {
        "event_id":  event_id,
        "fit_date":  today.isoformat(),
        "H":         fit_result["H"],
        "n":         fit_result["n"],
        "rmse":      fit_result["rmse"],
        "n_points":  fit_result["n_points"],
        "ephemeris": ephemeris,
    }


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> None:
    """
    执行每日拟合任务。

    Args:
        dry_run: 若为 True，仅打印结果，不写入缓存文件（用于测试）。
    """
    today = datetime.now(timezone.utc).date()
    future_stop = (today + timedelta(days=_FUTURE_DAYS)).isoformat()

    with open(_EVENTS_PATH, encoding="utf-8") as f:
        events = json.load(f)

    active_comets = [e for e in events if e.get("status") == "active" and e.get("type") == "comet"]
    log.info("活跃彗星事件 %d 个：%s", len(active_comets), [e["event_id"] for e in active_comets])

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    success, failed = [], []

    for event in active_comets:
        event_id = event["event_id"]
        cobs_des = event["cobs_designation"]
        horizons_id = event["horizons_id"]
        log.info("── 处理 %s ──────────────────────────────", event_id)

        try:
            # 1. 拉取 COBS 数据
            log.info("[%s] 拉取 COBS 数据（des=%s）…", event_id, cobs_des)
            cobs_raw = _fetch_cobs(cobs_des)
            cobs_records = parse_cobs_response(cobs_raw)
            log.info("[%s] COBS 解析完成：%d 个日期", event_id, len(cobs_records))

            if not cobs_records:
                raise ValueError("COBS 无有效观测记录")

            # 2. 确定 Horizons 查询范围
            earliest_cobs = cobs_records[0]["date"]   # 已按日期升序
            horizons_start = earliest_cobs
            log.info("[%s] Horizons 查询范围：%s → %s", event_id, horizons_start, future_stop)

            # 3. 拉取 Horizons 全程星历
            log.info("[%s] 请求 Horizons API…", event_id)
            horizons_raw = _fetch_horizons(horizons_id, horizons_start, future_stop)
            horizons_records = parse_horizons_response(horizons_raw)
            log.info("[%s] Horizons 解析完成：%d 天", event_id, len(horizons_records))

            # 4. 拟合
            log.info("[%s] 拟合光变参数…", event_id)
            fit_result = fit_comet_model(cobs_records, horizons_records)
            log.info(
                "[%s] 拟合结果：H=%.4f  n=%.4f  RMSE=%.4f  n_points=%d",
                event_id, fit_result["H"], fit_result["n"],
                fit_result["rmse"], fit_result["n_points"],
            )

            # H、n 合理性检查（警告但不中断）
            if not (0 < fit_result["H"] < 20):
                log.warning("[%s] H=%.4f 超出常见范围 (0, 20)，请人工核查", event_id, fit_result["H"])
            if not (0 < fit_result["n"] < 15):
                log.warning("[%s] n=%.4f 超出常见范围 (0, 15)，请人工核查", event_id, fit_result["n"])

            # 5. 构建并写入缓存
            cache = _build_cache(event_id, fit_result, horizons_records, today)
            cache_path = _CACHE_DIR / f"{event_id}_fit.json"

            if dry_run:
                log.info("[%s] dry_run=True，跳过写入。缓存预览：", event_id)
                preview = dict(cache)
                preview["ephemeris"] = cache["ephemeris"][:3]
                print(json.dumps(preview, ensure_ascii=False, indent=2))
            else:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                log.info("[%s] 缓存写入：%s（ephemeris %d 天）",
                         event_id, cache_path.relative_to(_REPO_ROOT), len(cache["ephemeris"]))

            success.append(event_id)

        except Exception as exc:
            log.error("[%s] 失败：%s", event_id, exc, exc_info=True)
            failed.append(event_id)

    log.info("── 完成 ─────────────────────────────────────")
    log.info("成功：%s", success or "（无）")
    log.info("失败：%s", failed or "（无）")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run(dry_run=dry_run)
