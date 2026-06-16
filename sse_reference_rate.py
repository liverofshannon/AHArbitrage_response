import re
import requests
from logger import get_logger

logger = get_logger()

BASE_URL = "http://www.sse.com.cn"
HOME_URL = f"{BASE_URL}/services/hkexsc/home/"

HEADERS = {
    "User-Agent": "curl/7.86.0",
    "Accept": "*/*",
}


def _fetch_avg(buy: float, sell: float) -> float:
    return (buy + sell) / 2


def _get_home_data():
    """获取主页，返回 (exchange_path, ratios_path)"""
    resp = requests.get(HOME_URL, headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"
    # js_files 中的多个路径用逗号分隔
    m = re.search(r'js_files="([^"]+)"', resp.text)
    if not m:
        raise ValueError("未在页面中找到 js_files")
    paths = [p.strip() for p in m.group(1).split(",")]
    exchange_path = ratios_path = None
    for p in paths:
        if "/exchange/" in p:
            exchange_path = p
        elif "/ratios/" in p:
            ratios_path = p
    return exchange_path, ratios_path


def _fetch_js(path):
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"
    return resp.text


def fetch_reference_rate():
    """爬取上交所港股通参考汇率（买入+卖出均值）"""
    try:
        exchange_path, _ = _get_home_data()
        if not exchange_path:
            raise ValueError("未找到参考汇率数据文件路径")

        js_text = _fetch_js(exchange_path)
        buy_match = re.search(r"BUY_PRICE\b\s*=\s*'\s*([\d.]+)", js_text)
        sell_match = re.search(r"SELL_PRICE\b\s*=\s*'\s*([\d.]+)", js_text)

        if not buy_match or not sell_match:
            raise ValueError("未能解析参考汇率买入/卖出价格")

        buy = float(buy_match.group(1))
        sell = float(sell_match.group(1))
        return _fetch_avg(buy, sell)
    except Exception as e:
        logger.error("fetch_reference_rate failed: %s", e)
        return None


def fetch_settlement_rate():
    """爬取上交所港股通结算汇兑比率（买入+卖出均值）"""
    try:
        _, ratios_path = _get_home_data()
        if not ratios_path:
            raise ValueError("未找到结算汇兑比率数据文件路径")

        js_text = _fetch_js(ratios_path)
        buy_match = re.search(r"BUY_PRICE_clear\s*=\s*'\s*([\d.]+)", js_text)
        sell_match = re.search(r"SELL_PRICE_clear\s*=\s*'\s*([\d.]+)", js_text)

        if not buy_match or not sell_match:
            raise ValueError("未能解析结算汇兑比率买入/卖出价格")

        buy = float(buy_match.group(1))
        sell = float(sell_match.group(1))
        return _fetch_avg(buy, sell)
    except Exception as e:
        logger.error("fetch_settlement_rate failed: %s", e)
        return None
