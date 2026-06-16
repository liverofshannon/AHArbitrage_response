#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易日 9:24 获取参考汇率，16:10 获取结算汇兑比率，写入 AH_EXCHG_RATE
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from logger import get_logger

import sse_reference_rate
from wecom_alert import send_alert

logger = get_logger()

TRIGGER_DAILY = dict(day_of_week="mon-fri")


class ExchangeRateScheduler:

    def __init__(self):
        self._scheduler = BackgroundScheduler()

    def _update_rate(self, label, fetch_fn):
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

    def _fetch_reference(self):
        self._update_rate("参考汇率", sse_reference_rate.fetch_reference_rate)

    def _fetch_settlement(self):
        self._update_rate("结算汇兑比率", sse_reference_rate.fetch_settlement_rate)

    def start(self):
        self._scheduler.add_job(
            self._fetch_reference,
            CronTrigger(hour=9, minute=24, **TRIGGER_DAILY),
            id="reference_rate",
        )
        self._scheduler.add_job(
            self._fetch_settlement,
            CronTrigger(hour=16, minute=10, **TRIGGER_DAILY),
            id="settlement_rate",
        )
        # 启动时拉一次参考汇率
        self._fetch_reference()
        self._scheduler.start()
        logger.info("scheduler started: reference_rate@9:24, settlement_rate@16:10")

    def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
