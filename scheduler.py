#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 9:24 从上交所获取港股通参考汇率，写入环境变量 AH_EXCHG_RATE
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from logger import get_logger

import sse_reference_rate
from wecom_alert import send_alert

logger = get_logger()


class ExchangeRateScheduler:
    """汇率定时更新调度器"""

    def __init__(self):
        self._scheduler = BackgroundScheduler()

    def _fetch_and_set(self):
        try:
            rate = sse_reference_rate.fetch_reference_rate()
            if rate:
                os.environ["AH_EXCHG_RATE"] = str(rate)
                logger.info("AH_EXCHG_RATE updated: %s", rate)
                send_alert(f"今日港股通参考汇率已更新：{rate:.4f}（1港元 = {rate:.4f}人民币）")
            else:
                logger.error("fetch_reference_rate returned None")
        except Exception as e:
            logger.error("fetch AH_EXCHG_RATE failed: %s", e)

    def start(self):
        self._scheduler.add_job(
            self._fetch_and_set,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=24),
            id="fetch_exchange_rate",
        )
        # 启动时立即拉一次
        self._fetch_and_set()
        self._scheduler.start()
        logger.info("scheduler started, daily at 9:24")

    def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
