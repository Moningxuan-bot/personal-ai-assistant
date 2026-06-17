"""
共享工具函数。

当前内容：
- extract_json_from_llm: 从 LLM 返回文本中提取 JSON（处理 markdown fence 等）
"""

import json
import logging

logger = logging.getLogger(__name__)


def extract_json_from_llm(text: str) -> dict | list:
    """从 LLM 响应中提取 JSON 对象或数组。

    处理常见的 LLM 输出格式：
    - ```json ... ``` 包裹
    - ``` ... ``` 包裹（无语言标记）
    - 纯 JSON 字符串

    Raises:
        json.JSONDecodeError: 无法解析为 JSON 时抛出
    """
    text = text.strip()

    # 去掉 markdown fence
    if text.startswith("```"):
        # 跳过可能的语言标记行（```json / ```）
        lines = text.split("\n")
        # 去掉第一行（``` 或 ```json）
        lines = lines[1:]
        # 如果最后一行是 ```，去掉
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)
