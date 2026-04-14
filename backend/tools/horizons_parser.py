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
