#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
企业微信回调服务器

GET  /callback  → URL验证
POST /callback  → 接收消息，解密后交给 handler.py 处理
"""

import os as _os
_os.environ.setdefault("AH_LOG_ROOT", _os.path.dirname(_os.path.abspath(__file__)))

import logging
from flask import Flask, request
from WXBizMsgCrypt import WXBizMsgCrypt
import defusedxml.ElementTree as ET

from handler import handle
from wecom_alert import send_text
from logger import get_logger

# ============================================================
# 配置
# ============================================================
CORP_ID = "ww347dcac53083dfe1"
TOKEN = "IKVwQgX9"
ENCODING_AES_KEY = "8hor06JnEPmgH96d7ufqLMHC3fMeQhDf2JPrkdiX2oK"

wxcpt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, CORP_ID)

# 异步文件日志，关闭 Flask 默认控制台日志
log = get_logger()
logging.getLogger("flask").handlers = []
logging.getLogger("flask.app").handlers = []
logging.getLogger("werkzeug").handlers = []

app = Flask(__name__)

# ============================================================
# 回调接口
# ============================================================

@app.route("/callback", methods=["GET", "POST"])
def callback():
    if request.method == "GET":
        ret, echo = wxcpt.VerifyURL(
            request.args.get("msg_signature", ""),
            request.args.get("timestamp", ""),
            request.args.get("nonce", ""),
            request.args.get("echostr", ""),
        )
        if ret != 0:
            log.error("URL verification failed, ret=%s", ret)
            return "verify failed", 403
        return echo

    ret, plain_xml = wxcpt.DecryptMsg(
        request.get_data(),
        request.args.get("msg_signature", ""),
        request.args.get("timestamp", ""),
        request.args.get("nonce", ""),
    )
    if ret != 0:
        log.error("message decrypt failed, ret=%s", ret)
        return "decrypt failed", 403

    root = ET.fromstring(plain_xml)
    msg = {el.tag: el.text or "" for el in root}
    log.info("msg from=%s type=%s content=%s",
             msg.get("FromUserName", ""), msg.get("MsgType", ""), msg.get("Content", ""))

    reply = handle(msg)
    if reply:
        try:
            result = send_text(msg.get("FromUserName", ""), reply)
            log.info("reply sent, msgid=%s", result.get("msgid"))
        except Exception as e:
            log.error("reply failed: %s", e)

    return "", 200


@app.route("/health")
def health():
    return "ok"


# 模块加载时启动汇率定时拉取（python bot.py 和 gunicorn bot:app 都会触发）
from scheduler import ExchangeRateScheduler
_sched = ExchangeRateScheduler()
_sched.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
