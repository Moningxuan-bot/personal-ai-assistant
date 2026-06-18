"""
统一日志配置。

开发环境：DEBUG 级别，彩色人类可读，输出到 stderr（不污染 stdout 日志流）
生产环境：INFO 级别，JSON lines，输出到 stdout（Docker/Zeabur 直接收容）

用法：
    from app.logging_config import setup_logging
    setup_logging()  # 在 main.py 最顶部调用一次
"""
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from app.config import settings


_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


class JsonFormatter(logging.Formatter):
    """JSON lines 格式化器。每条日志一行 JSON，适合 docker logs / jq。"""

    def format(self, record: logging.LogRecord) -> str:
        # 从 ContextVar 读取 request_id（安全：无 request_id 时为 None）
        try:
            from app.request_context import request_id
            rid = request_id.get()
        except Exception:
            rid = None

        ts = datetime.fromtimestamp(record.created, tz=timezone(timedelta(hours=8)))

        payload = {
            "ts": ts.strftime(_ISO_FORMAT) + "+08:00",
            "level": record.levelname,
            "logger": record.name,
        }
        if rid:
            payload["rid"] = rid

        # 把额外上下文字段合并进来
        if hasattr(record, "extra_fields") and record.extra_fields:
            payload.update(record.extra_fields)

        # 消息正文
        payload["msg"] = record.getMessage()

        # 异常堆栈
        if record.exc_info and record.exc_info[0]:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """开发环境可读格式。"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s %(levelname)-5s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        try:
            from app.request_context import request_id
            rid = request_id.get()
        except Exception:
            rid = None

        base = super().format(record)
        if rid:
            base = base.replace(record.getMessage(), f"[rid={rid}] {record.getMessage()}")
        return base


def setup_logging() -> None:
    """配置全局日志系统。调用一次，幂等。"""
    root = logging.getLogger()
    # 防止重复配置（uvicorn reload 时模块重新执行）
    if root.handlers:
        return

    is_dev = settings.app_env == "development"

    # ---- handler ----
    if is_dev:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(HumanFormatter())
        level = logging.DEBUG
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        level = logging.INFO

    root.setLevel(level)
    root.addHandler(handler)

    # ---- 静默 noisy 库 ----
    # httpx/httpcore 在 INFO 级别下会输出大量请求日志，提到 WARNING
    for noisy in ("httpx", "httpcore", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn 保持 INFO，生产需要看启动和关闭
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(handler)
    uvicorn_logger.setLevel(logging.INFO)
    # uvicorn.access 用同样 handler
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)
