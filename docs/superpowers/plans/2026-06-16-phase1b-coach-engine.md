# 阿玖 — 教练引擎 + 任务系统 实施计划

> 基于 grill-me 方法论：逐个追问 → 质量评估 → 不合格追问 → 全过后生成计划

## 目标

让阿玖从"能聊天的 AI"变成"能帮用户做事的 Agent"。教练模式下，按 6 必问项逐个追问，评估回答质量，不合格就追问到底。6 问全过后生成计划，创建任务，切换到管家模式。

## 数据结构

### 1. conversations 表新增列

```python
coach_state = Column(JSONB, nullable=True)
# {
#   "active": true,
#   "current_question": 3,       # 1-6
#   "answers": {
#     "goal_picture": "...",
#     "baseline": "...",
#     ...
#   },
#   "follow_up_count": 0,        # 当前追问轮次
#   "last_question_at": "ISO..."
# }
```

### 2. 新表 goals

```sql
goals: id UUID PK,
       conversation_id UUID FK → conversations,
       title VARCHAR(255),
       description TEXT,
       milestones JSONB,          -- [{ "text": "...", "done": false }, ...]
       status VARCHAR(20),        -- active/paused/completed/abandoned
       revive_count INT DEFAULT 0,
       created_at TIMESTAMPTZ,
       completed_at TIMESTAMPTZ NULL
```

### 3. 新表 goal_checks

```sql
goal_checks: id UUID PK,
             goal_id UUID FK → goals,
             check_time TIMESTAMPTZ,
             status VARCHAR(20),   -- done/skipped/missed
             note TEXT
```

## 实现步骤

### Task 1: 数据库迁移

- [ ] 修改 Conversation model 加 `coach_state` JSONB 列
- [ ] 创建 Goal model
- [ ] 创建 GoalCheck model
- [ ] Alembic 迁移
- [ ] Commit

### Task 2: CoachEngine 状态机

- [ ] `backend/app/services/coach.py`

核心类：
```python
class CoachEngine:
    QUESTIONS = [
        {"id": "goal_picture", "label": "目标画像", "ask": "做到什么程度算完成？", ...},
        {"id": "baseline", "label": "当前基线", "ask": "现在什么水平？", ...},
        ...
    ]

    async def process(self, user_message: str, coach_state: dict, llm, db):
        """处理用户回答 → 评估 → 追问 or 下一问 or 完成"""
        ...
```

评估逻辑：
1. 拿当前问题的定义 + 用户回答 → LLM 评估是否合格
2. 合格 → 记录答案 → 下一问（不合格答案攒到 3 轮放行）
3. 6 问全过 → 生成计划摘要 → 返回 `complete` 信号

### Task 3: 接入 ChatService

- [ ] 修改 `chat.py`：教练模式时调用 CoachEngine
- [ ] CoachEngine 的输出作为 SSE 事件返回（meta 带 coach_state 更新）
- [ ] 计划确认后创建 Goal → 切管家模式

### Task 4: Goal API

- [ ] `backend/app/routes/goals.py` — CRUD
- [ ] Goal list / detail / update status / revive

### Task 5: 测试

- [ ] CoachEngine 单元测试（mock LLM）
- [ ] 状态机流转测试
- [ ] 集成测试：教练对话 → 创建 Goal 全流程
