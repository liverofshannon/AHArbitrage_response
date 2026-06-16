"""
企业微信消息发送模块

- send_text(user_id, content)     → 发给指定用户
- send_alert(message)             → 同步 @all 广播
- send_alert_async(message)       → 异步 @all 广播
"""

import time
import threading
import requests
from logger import get_logger

log = get_logger()

# ============================================================
# 配置
# ============================================================
CORP_ID = "ww347dcac53083dfe1"
APP_SECRET = "CwYsgcIvJXE4PXK_bKGlbrUw2zPQ5FuDmnNn85_84S4"
AGENT_ID = "1000002"
API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

# ============================================================
# token 缓存
# ============================================================
_token_cache = {"token": None, "expire": 0}


def _fetch_token() -> str:
    resp = requests.get(
        f"{API_BASE}/gettoken",
        params={"corpid": CORP_ID, "corpsecret": APP_SECRET},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        log.error("get access_token failed: %s", data)
        raise RuntimeError(f"get access_token failed: {data}")
    return data["access_token"]


def _get_token() -> str:
    if _token_cache["expire"] > time.time():
        return _token_cache["token"]
    token = _fetch_token()
    _token_cache["token"] = token
    _token_cache["expire"] = time.time() + 7000
    return token


def _send(user_id: str, content: str) -> dict:
    """内部发送逻辑，含 token 过期重试"""
    token = _get_token()
    body = {
        "touser": user_id,
        "msgtype": "text",
        "agentid": AGENT_ID,
        "text": {"content": content},
    }
    resp = requests.post(
        f"{API_BASE}/message/send",
        params={"access_token": token},
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    errcode = data.get("errcode")

    if errcode == 0:
        return data
    elif errcode in (40001, 40014, 42001):
        log.warning("token expired (errcode=%s), refreshing", errcode)
        new_token = _fetch_token()
        _token_cache["token"] = new_token
        _token_cache["expire"] = time.time() + 7000
        resp = requests.post(
            f"{API_BASE}/message/send",
            params={"access_token": new_token},
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            log.error("send message retry failed: %s", data)
            raise RuntimeError(f"send message retry failed: {data}")
        return data
    else:
        log.error("send message failed: %s", data)
        raise RuntimeError(f"send message failed: {data}")

# ============================================================
# 公开接口
# ============================================================

def send_text(user_id: str, content: str) -> dict:
    """发送文本消息给指定用户"""
    return _send(user_id, content)


def send_alert(message: str) -> dict:
    """同步发送告警 @all"""
    return _send("@all", message)


def send_alert_async(message: str):
    """异步发送告警，另起线程"""

    def _run():
        try:
            send_alert(message)
        except Exception as e:
            log.error("send_alert_async failed: %s", e)

    t = threading.Thread(target=_run, daemon=False)
    t.start()
