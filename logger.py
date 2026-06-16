"""
异步文件日志，格式与 ahlogger.py 一致
路径: {AH_LOG_ROOT}/log/response/{YYYYMMDD}/AHarbitrage_response_{YYYYMMDD}.log
"""

import atexit
import os
import queue
import threading
import sys
from datetime import datetime


class AsyncFileLogger:
    MAX_BYTES = 5 * 1024 * 1024

    def __init__(self, script_name: str = None):
        self._script_name = script_name or self._detect_name()
        self._root = os.getenv("AH_LOG_ROOT") or os.getcwd()
        self._queue = queue.Queue()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        atexit.register(self.close)

    @staticmethod
    def _detect_name():
        m = sys.modules.get("__main__")
        if m and hasattr(m, "__file__") and m.__file__:
            return os.path.basename(m.__file__).rsplit(".", 1)[0]
        return "unknown"

    def _log_dir(self):
        d = datetime.now().strftime("%Y%m%d")
        return os.path.join(self._root, "log", "response", d)

    def _resolve_path(self):
        d = datetime.now().strftime("%Y%m%d")
        base = os.path.join(self._log_dir(), f"AHarbitrage_response_{d}")
        os.makedirs(os.path.dirname(base), exist_ok=True)
        path = base + ".log"
        if not os.path.exists(path) or os.path.getsize(path) < self.MAX_BYTES:
            return path
        idx = 1
        while True:
            p = f"{base}_{idx:02d}.log"
            if not os.path.exists(p) or os.path.getsize(p) < self.MAX_BYTES:
                return p
            idx += 1

    @staticmethod
    def _ts():
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"

    def _loop(self):
        while True:
            level, msg = self._queue.get()
            if msg is None:
                break
            line = f"{self._script_name} {threading.get_ident()} {level} {self._ts()} {msg}\n"
            with open(self._resolve_path(), "a", encoding="utf-8") as f:
                f.write(line)

    def info(self, msg, *args):
        if args:
            msg = msg % args
        self._queue.put(("INFO", msg))

    def warning(self, msg, *args):
        if args:
            msg = msg % args
        self._queue.put(("WARNING", msg))

    def error(self, msg, *args):
        if args:
            msg = msg % args
        self._queue.put(("ERROR", msg))

    def close(self):
        self._queue.put((None, None))
        self._t.join(timeout=5)


_logger = None
_lock = threading.Lock()


def get_logger():
    global _logger
    if _logger is None:
        with _lock:
            if _logger is None:
                _logger = AsyncFileLogger("response")
    return _logger
