#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作日北京时间 9:24 拉参考汇率，16:10 拉结算汇兑比率，存入 AH_EXCHG_RATE
"""

import os
from datetime import timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from logger import get_logger
import sse_reference_rate
from wecom_alert import send_alert

logger = get_logger()

TZ = timezone(timedelta(hours=8))
TRIGGER = dict(day_of_week="mon-fri", timezone=TZ)


class ExchangeRateScheduler:

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone=TZ)

    def _update(self, label, fetch_fn):
        try:
            rate = fetch_fn()
            if rate:
                os.environ["AH_EXCHG_RATE"] = str(rate)
                logger.info("%s updated: %s", label, rate)
                send_alert(f"今日港股通{label}已更新：{rate:.4f}（1港元 = {rate:.4f}人民币）")
            else:
                logger.error("%s returned None", label)
        except Exception as e:
            logger.error("%s failed: %s", label, e)

    def start(self):
        self._scheduler.add_job(
            lambda: self._update("参考汇率", sse_reference_rate.fetch_reference_rate),
            CronTrigger(hour=9, minute=24, **TRIGGER),
            id="reference_rate",
        )
        self._scheduler.add_job(
            lambda: self._update("结算汇兑比率", sse_reference_rate.fetch_settlement_rate),
            CronTrigger(hour=16, minute=10, **TRIGGER),
            id="settlement_rate",
        )
        self._scheduler.start()
        # 启动时先拉一次参考汇率
        self._update("参考汇率", sse_reference_rate.fetch_reference_rate)
        logger.info("scheduler started: reference_rate@9:24, settlement_rate@16:10 (UTC+8)")

    def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
