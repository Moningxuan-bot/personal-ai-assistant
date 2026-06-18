"""
请求上下文 —— 用 contextvars 在异步调用链中传递 request_id。

用法：
    from app.request_context import request_id, set_request_id

    set_request_id("abc123")       # middleware 设置
    rid = request_id.get()          # 任何深层代码读取，无需传参
"""
import contextvars

# 默认值为 None，middleware 设置后整条异步链都可读
request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def set_request_id(rid: str) -> None:
    request_id.set(rid)


def get_request_id() -> str | None:
    return request_id.get()
