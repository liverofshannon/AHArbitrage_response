import re
import requests
from logger import get_logger

logger = get_logger()

#在上证交所获取港股通参考汇率

BASE_URL = "http://www.sse.com.cn"
HOME_URL = f"{BASE_URL}/services/hkexsc/home/"

HEADERS = {
    "User-Agent": "curl/7.86.0",
    "Accept": "*/*",
}


def fetch_reference_rate():
    """爬取上交所港股通参考汇率买入/卖出价，返回 (买入, 卖出, 均值)"""
    # 1. 获取主页 HTML，从中提取 exchange 数据文件的路径（参考汇率）
    try:
        resp = requests.get(HOME_URL, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"

        match = re.search(
            r'js_files="[^"]*?(/services/hkexsc/home/exchange/[^",]+)', resp.text
        )
        if not match:
            raise ValueError("未在页面中找到 exchange 数据文件路径")

        exchange_path = match.group(1)

        # 2. 获取 exchange JS 数据文件（不用 session，避免 cookie 触发反爬）
        js_resp = requests.get(
            f"{BASE_URL}{exchange_path}", headers=HEADERS, timeout=15
        )
        js_resp.encoding = "utf-8"
        js_text = js_resp.text

        # 3. 从 JS 变量中提取价格（BUY_PRICE / SELL_PRICE 不带 _clear 后缀）
        buy_match = re.search(r"BUY_PRICE\s*=\s*'\s*([\d.]+)", js_text)
        sell_match = re.search(r"SELL_PRICE\s*=\s*'\s*([\d.]+)", js_text)

        if not buy_match or not sell_match:
            raise ValueError("未能从数据文件中解析出买入/卖出价格")

        buy_price = float(buy_match.group(1))
        sell_price = float(sell_match.group(1))
        avg_price = (buy_price + sell_price) / 2
        return avg_price
    except Exception as e:
        logger.error(e)