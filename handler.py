"""
业务处理模块

msg 字段: ToUserName, FromUserName, CreateTime, MsgType, Content, MsgId, AgentID
返回字符串 → 通过API发送给用户；返回 None → 不回复
"""

import csv
import os
import re
import threading

import requests

# ============================================================
# 路径
# ============================================================
_CFG = os.path.join(os.getenv("AH_LOG_ROOT", ""), "config")
ALARM_RATE_CSV = os.path.join(_CFG, "ah_alarmRate.csv")
ALERT_STATE_CSV = os.path.join(_CFG, "alert_state.csv")
STOCK_MAP_CSV = os.path.join(_CFG, "ah_stock_map.csv")

TENCENT_URL = "http://sqt.gtimg.cn/utf8/q="


# ============================================================
# CSV 读写辅助
# ============================================================

def _read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f, restval=""))


def _write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


_FILE_NAMES = {
    ALARM_RATE_CSV: "溢价监控文件",
    ALERT_STATE_CSV: "状态文件",
    STOCK_MAP_CSV: "股票监控文件",
}


def _must_read(path):
    rows = _read_csv(path)
    if rows is None:
        raise FileNotFoundError(f"{_FILE_NAMES.get(path, path)}不存在")
    return rows


def _get_stock_prefix(code: str) -> str:
    return "sh" if code.startswith(("5", "6", "7", "9")) else "sz"


# ============================================================
# 腾讯财经行情
# ============================================================

def _parse_tencent_a(raw: str) -> dict:
    """解析腾讯A股返回，key=6位代码"""
    result = {}
    for m in re.finditer(r'v_(s[zh]\d{6})="(.+?)"', raw):
        parts = m.group(2).split("~")
        if len(parts) < 40:
            continue
        code = parts[2]
        try:
            result[code] = {
                "name": parts[1],
                "now": float(parts[3]),
                "open": float(parts[5]),
                "close": float(parts[4]),
                "high": float(parts[33]),
                "low": float(parts[34]),
                "volume": float(parts[6]),
            }
        except (ValueError, IndexError):
            continue
    return result


def _parse_tencent_hk(raw: str) -> dict:
    """解析腾讯港股返回，key=5位代码"""
    result = {}
    for m in re.finditer(r'v_r_hk\d+="(.+?)"', raw):
        parts = m.group(1).split("~")
        if len(parts) < 50:
            continue
        code = parts[2]
        try:
            result[code] = {
                "name": parts[1],
                "now": float(parts[3]),
                "open": float(parts[5]),
                "close": float(parts[4]),
                "high": float(parts[33]),
                "low": float(parts[34]),
            }
        except (ValueError, IndexError):
            continue
    return result


def _fetch_stocks(a_code: str) -> str:
    """多线程获取A+H股行情，返回格式化的价格信息"""
    # 查H股代码
    h_code = None
    stock_name = ""
    map_rows = _must_read(STOCK_MAP_CSV)
    for row in map_rows:
        if row.get("a_stock_code", "").strip() == a_code:
            h_code = row.get("h_stock_code", "").strip()
            stock_name = row.get("stock_name", "")
            break
    if not h_code:
        return f"未找到 {a_code} 对应的H股代码"

    a_data = {}
    h_data = {}

    def _fetch_a():
        nonlocal a_data
        try:
            prefix = _get_stock_prefix(a_code)
            resp = requests.get(TENCENT_URL + prefix + a_code, timeout=15)
            resp.encoding = "utf-8"
            a_data = _parse_tencent_a(resp.text)
        except Exception as e:
            a_data = {"_error": str(e)}

    def _fetch_h():
        nonlocal h_data
        try:
            resp = requests.get(TENCENT_URL + "r_hk" + h_code, timeout=15)
            resp.encoding = "utf-8"
            h_data = _parse_tencent_hk(resp.text)
        except Exception as e:
            h_data = {"_error": str(e)}

    t_a = threading.Thread(target=_fetch_a)
    t_h = threading.Thread(target=_fetch_h)
    t_a.start()
    t_h.start()
    t_a.join()
    t_h.join()

    # 取结果
    a_info = a_data.get(a_code)
    h_info = h_data.get(h_code)

    if a_info is None:
        return f"获取A股 {a_code} 行情失败"
    if h_info is None:
        return f"获取港股 {h_code} 行情失败"

    # 计算溢价率
    try:
        rate = float(os.getenv("AH_EXCHG_RATE", "0.91"))
    except ValueError:
        rate = 0.91

    a_price = a_info["now"]
    h_price = h_info["now"]
    premium = (a_price / (h_price * rate) - 1) * 100  # 百分比

    return (
        f"{stock_name or a_code}\n"
        f"A股({a_code}): {a_price:.2f}\n"
        f"H股({h_code}): {h_price:.2f} HKD\n"
        f"A/H溢价率: {premium:+}%\n"
        f"(汇率: {rate:.4f})"
    )


# ============================================================
# 命令1: 更新告警阈值
# ============================================================

def _cmd_update_alarm(code: str, low: float, high: float) -> str:
    rows = _must_read(ALARM_RATE_CSV)
    found = False
    for r in rows:
        if r.get("a_stock_code", "").strip() == code:
            r["ah_low"] = str(low)
            r["ah_high"] = str(high)
            found = True
            break

    if not found:
        # 从 stock_map 查名称
        name = ""
        map_rows = _must_read(STOCK_MAP_CSV)
        for r in map_rows:
            if r.get("a_stock_code", "").strip() == code:
                name = r.get("stock_name", "")
                break
        if not name:
            return f"ah_stock_map.csv 中未找到 {code}，无法确定股票名称"
        rows.append({"a_stock_code": code, "a_name": name, "ah_low": str(low), "ah_high": str(high)})

    _write_csv(ALARM_RATE_CSV, rows, ["a_stock_code", "a_name", "ah_low", "ah_high"])

    # 同步重置 alert_state
    _reset_alert_state(code)

    # 返回整个文件内容
    return _csv_content(ALARM_RATE_CSV)


def _reset_alert_state(code: str):
    rows = _must_read(ALERT_STATE_CSV)
    for r in rows:
        if r.get("a_stock_code", "").strip() == code:
            r["last_state"] = "normal"
            break
    else:
        rows.append({"a_stock_code": code, "last_state": "normal"})
    _write_csv(ALERT_STATE_CSV, rows, ["a_stock_code", "last_state"])


# ============================================================
# 命令3: 提示列表 / 命令4: 监控列表
# ============================================================

def _csv_content(path) -> str:
    rows = _must_read(path)
    if not rows:
        return "（空）"
    lines = [",".join(rows[0].keys())]
    for r in rows:
        lines.append(",".join(r.values()))
    return "\n".join(lines)


def _cmd_monitor_list() -> str:
    rows = _must_read(STOCK_MAP_CSV)
    names = [r.get("stock_name", "") for r in rows
             if r.get("in_or_out", "").strip() == "1"]
    if not names:
        return "当前无监控股票"
    return "\n".join(names)


# ============================================================
# 命令5: 修改 in_or_out
# ============================================================

def _cmd_toggle_inout(code: str, flag: str) -> str:
    rows = _must_read(STOCK_MAP_CSV)
    found = False
    for r in rows:
        if r.get("a_stock_code", "").strip() == code:
            r["in_or_out"] = flag
            found = True
            break
    if not found:
        return f"ah_stock_map.csv 中未找到 {code}"

    cols = rows[0].keys()
    _write_csv(STOCK_MAP_CSV, rows, list(cols))

    return _cmd_monitor_list()


# ============================================================
# 主入口
# ============================================================

def handle(msg: dict) -> str | None:
    msg_type = msg.get("MsgType", "")
    content = msg.get("Content", "").strip()

    if msg_type != "text":
        return None

    # ---------- help ----------
    if content.lower() in ("help", "帮助", "?", "？"):
        return (
            "使用说明：\n"
            "1. 代码,下限,上限  →  更新AH溢价告警阈值（例：000333，0.02，0.08）\n"
            "2. 六位代码        →  查询A/H股价及溢价率（例：000333）\n"
            "3. 提示XXX         →  查看当前告警阈值列表\n"
            "4. 监控XXX         →  查看当前监控股票列表\n"
            "5. 代码,1或0       →  加入/移出监控列表（例：000333，1）\n"
            "6. help            →  查看本说明\n"
            "（分隔符支持半角,和全角，）"
        )

    # 全角逗号 → 半角
    content = content.replace("，", ",")

    try:
        # ---------- 提示 / 提示列表 ----------
        if content.startswith("提示"):
            return _csv_content(ALARM_RATE_CSV)

        # ---------- 监控 / 监控列表 ----------
        if content.startswith("监控"):
            return _cmd_monitor_list()

        # ---------- 逗号分隔的命令 ----------
        parts = [p.strip() for p in content.split(",")]

        if len(parts) == 3:
            code, low, high = parts
            if code.isdigit() and len(code) == 6:
                try:
                    return _cmd_update_alarm(code, float(low), float(high))
                except ValueError:
                    return "格式错误：下限和上限必须为数字"

        if len(parts) == 2:
            code, flag = parts
            if code.isdigit() and len(code) == 6 and flag in ("0", "1"):
                return _cmd_toggle_inout(code, flag)

        if len(parts) == 1:
            code = parts[0]
            if code.isdigit() and len(code) == 6:
                return _fetch_stocks(code)

        # ---------- 无法识别 ----------
        return f"无法识别指令: {content}\n发送「help」查看使用说明"

    except FileNotFoundError as e:
        return str(e)
