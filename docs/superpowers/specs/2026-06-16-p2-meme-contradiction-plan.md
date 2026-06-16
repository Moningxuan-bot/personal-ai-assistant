# P2 梗系统 + 记忆矛盾检测 — 任务计划

> 给 GPT 执行 | 项目：阿玖个人 AI Agent | 日期：2026-06-16
> 
> 当前 master：`4ad5487` | 测试：42/42 通过
> 
> 运行环境：`D:/Claude code/个人API应用/backend/.venv/Scripts/python.exe`

## 背景

P0（教练引擎+任务系统）和 P1（支付监控+行为劝诫）已完成。P2 包含两个独立子系统：B 站梗更新和记忆矛盾检测。两者可并行开发。

---

## 子系统 A：B 站梗系统

### A-1: Meme 模型

创建 `backend/app/models/meme.py`：

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.database import Base


class Meme(Base):
    __tablename__ = "memes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="bilibili")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 逗号分隔的标签，如 "游戏,科技,鬼畜"

    kept: Mapped[bool] = mapped_column(Boolean, default=False)
    # 用户决定保留的梗
    discarded: Mapped[bool] = mapped_column(Boolean, default=False)
    # 用户永久丢弃的梗（不再显示）
    asked: Mapped[bool] = mapped_column(Boolean, default=False)
    # 是否已经问过用户"要不要留"

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

更新 `backend/app/models/__init__.py`，导入 Meme。

生成并运行迁移：
```bash
cd backend
alembic revision --autogenerate -m "add memes table"
alembic upgrade head
```

### A-2: 用户偏好模型扩展

在 `backend/app/models/memory.py` 中已有的 Memory 模型基础上，不需要新建表。偏好以 `category="preference"` 的 Memory 存储即可。B 站梗的偏好标签从这些 Memory 中读取。

确保 `MemoryService` 有方法获取偏好标签列表：
```python
async def get_preference_tags(self) -> list[str]:
    """获取用户设定的偏好标签列表。"""
```

### A-3: B 站热梗抓取服务

创建 `backend/app/services/meme.py`：

```python
import json
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.meme import Meme
from app.providers.llm import LLMProvider, ChatMessage


class MemeService:
    def __init__(self, db: AsyncSession, llm: LLMProvider):
        self.db = db
        self.llm = llm

    async def fetch_bilibili_hot(self, limit: int = 20) -> list[dict]:
        """调用 B 站 API 获取热门视频/话题。返回原始列表。"""
        # B 站热门 API：https://api.bilibili.com/x/web-interface/popular?ps=50
        # 注意：B 站 API 可能需要合适的 User-Agent
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/web-interface/popular",
                params={"ps": min(limit, 50)},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Bilibili API error: {data.get('message')}")
            return [
                {
                    "title": v["title"],
                    "url": f"https://www.bilibili.com/video/{v['bvid']}",
                    "tags": v.get("tname", ""),
                    "summary": v.get("desc", "")[:200],
                }
                for v in data["data"]["list"]
            ]

    async def filter_by_preferences(
        self, memes: list[dict], prefs: list[str]
    ) -> list[dict]:
        """用 LLM 过滤：只保留匹配用户偏好的梗。如果没有偏好，全保留。"""
        if not prefs:
            return memes  # 用户还没设偏好，全保留
        # LLM 批量判断
        ...
```

**关键逻辑：**

1. **抓取**：调 B 站 `/x/web-interface/popular` 热门 API，取 top 20
2. **LLM 过滤**：把梗标题+标签发给 LLM，和用户偏好标签比对，只保留相关的
3. **LLM 改写**：把保留的梗改写成阿玖的语气（1-2句中文），方便注入聊天
4. **去重**：已 `discarded=True` 的梗不再出现
5. **存储**：写入 Meme 表，`asked=False`

### A-4: 梗清理 API

在 `backend/app/routes/memes.py`：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/memes/today` | 获取当天未处理的梗列表 |
| `POST` | `/api/memes/{id}/keep` | 保留该梗（kept=True, asked=True） |
| `POST` | `/api/memes/{id}/discard` | 永久丢弃（discarded=True, asked=True） |

### A-5: 定时任务

创建 `backend/app/tasks/meme_daily.py`：

```python
"""每晚 22:00 执行的梗更新任务。由外部 cron 或 scheduler 触发。"""

async def run_daily_meme_fetch():
    """1. 抓取 B 站热门 2. LLM 过滤 3. 存入 DB 4. 标记待询问"""
```

调用方式：
- 开发期间：手动 `curl POST /api/memes/fetch` 触发
- 生产：VPS crontab `0 22 * * * curl -X POST ...`

### A-6: 聊天注入

修改 `backend/app/services/chat.py`：

在闲聊模式的系统提示词中注入今天保留的梗（`kept=True` 且 `fetched_at` 是今天）：

```python
# 在 _build_system_prompt 中添加 meme_context 参数
# 查询：SELECT * FROM memes WHERE kept=true AND fetched_at >= today
# 注入格式：
"""
## 今天的热梗
- [梗1标题] 阿玖版解释
- [梗2标题] 阿玖版解释

你可以在闲聊中自然地提到这些梗，但不要生硬地背诵。"
```

---

## 子系统 B：记忆矛盾检测

### B-1: 矛盾追踪模型扩展

在 `backend/app/models/memory.py` 的 Memory 模型中添加字段：

```python
# 已有字段保持不变，新增：
contradiction_topic: Mapped[str | None]  # 矛盾话题标签，如 "喜欢的颜色"
contradiction_count: Mapped[int] = mapped_column(default=0)  # 该话题被推翻次数
contradiction_history: Mapped[list[dict] | None]  # JSONB，记录每次变更
# [{"old": "喜欢蓝色", "new": "喜欢红色", "at": "2026-06-16T10:00:00"}]
```

生成迁移。

### B-2: 记忆提取时检测矛盾

修改 `backend/app/services/memory.py` 的 `extract_and_save_memories` 方法：

当前流程：LLM 从对话提取事实 → 存入 Memory

新增流程：
1. LLM 提取事实（不变）
2. 对每条新事实，向量搜索已有的同类 Memory（同 category）
3. 如果 LLM 判断新事实与旧记忆矛盾：
   - `contradiction_count += 1`
   - `contradiction_history` 追加记录
   - 旧记忆内容转为"过时"，新记忆写入
   - 如果 `contradiction_count >= 3`：返回 `trigger_mockery: True` + 话题标签
4. 如果 LLM 判断不矛盾：
   - 普通更新/新增

### B-3: 矛盾触发阿玖嘲讽

在 `ChatService.chat()` 中：

记忆提取完成后，检查是否有 `trigger_mockery` 的记忆：
- 如果有，在闲聊回复开头插入阿玖的嘲讽：
  - "等下——你说你{新说法}？不对啊，我记得你之前明明说{旧说法}的。这是第{count}次变了。真是多变的笨蛋。"
  - 嘲讽后继续正常回复

### B-4: 阿玖嘲讽 Prompt 追加

在 `backend/app/prompts/ajiu.py` 中追加矛盾检测模式的语气指导：

```python
CONTRADICTION_PROMPT = """
用户刚刚的说法和之前的记忆矛盾了。这是同一话题第{count}次变化。

阿玖的反应：
- 第1-2次变化：轻松调侃 "咦？你之前不是说……？算了你说了算"
- 第3+次变化：翻白眼嘲讽 "真是多变的笨蛋。这是第{count}次了，我该信哪个？"
- 嘲讽完继续正常对话，不要一直揪着不放
"""
```

---

## 开发顺序

### Phase 1：B 站梗系统（Tasks A1-A6）

| Task | 文件 | 内容 |
|------|------|------|
| A-1 | `models/meme.py` | Meme 模型 + 迁移 |
| A-2 | `services/meme.py` | MemeService（抓取 + LLM 过滤 + 改写） |
| A-3 | `routes/memes.py` | API（today/keep/discard + fetch 触发） |
| A-4 | `prompts/ajiu.py` | 追加梗模式提示词 |
| A-5 | `services/chat.py` | 闲聊注入当天热梗 |
| A-6 | `tests/test_meme.py` | 测试（抓取 mock、过滤、API） |

### Phase 2：记忆矛盾检测（Tasks B1-B4）

| Task | 文件 | 内容 |
|------|------|------|
| B-1 | `models/memory.py` | Memory 模型加矛盾追踪字段 + 迁移 |
| B-2 | `services/memory.py` | extract_and_save_memories 加矛盾检测 |
| B-3 | `services/chat.py` | 矛盾触发时注入嘲讽 |
| B-4 | `prompts/ajiu.py` | 矛盾检测语气指导 |
| B-5 | `tests/test_memory.py` | 矛盾检测测试（mock LLM 返回矛盾/不矛盾） |

### 最后

- 全量测试：42 + 新增 ≥ 50 个通过
- Push + 更新 CONTEXT.md 进度

---

## 注意事项

- **B 站 API**：不需要 API Key，但需要 User-Agent 头。热门接口有频率限制（~1次/秒），每日一次足够
- **LLM 调用**：梗过滤和改写各一次 LLM 调用，两次可以合并为一个 prompt（输入原始梗列表 + 偏好标签 → 输出过滤并改写后的列表）
- **时区**：所有 datetime 用 `timezone.utc`，22:00 指北京时间（UTC+8 = 14:00 UTC）
- **测试**：B 站 API 调用必须 mock，不要真的请求外网
- **命名**：始终称她为"阿玖"，代码和注释用中文
