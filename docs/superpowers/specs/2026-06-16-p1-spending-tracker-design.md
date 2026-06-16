# P1 支付监控 + 行为劝诫 — 设计文档

> 日期：2026-06-16 | 状态：待实现

## 概述

阿玖的记账和消费劝诫能力。用户在 Flutter App 手动录入消费，阿玖对每一笔消费做出反应（卡片级吐槽 + 必要时聊天级关心），让用户感受到阿玖在关注他的钱包和生活习惯。

## 数据模型

### Spending

```python
class Spending(Base):
    __tablename__ = "spendings"

    id: UUID (PK)
    conversation_id: UUID? (FK → conversations.id)  # 聊天级反应关联对话
    amount: Numeric(10, 2)                           # 金额
    category: String(20)                             # 餐饮/交通/烟酒/购物/娱乐/其他
    note: Text?                                      # 用户手写备注
    reaction: Text                                   # 阿玖卡片级回复（1-2句，永远有值）
    chat_reaction: Text?                             # 阿玖聊天级回复（较长，触发才有）
    chat_delivered: Boolean (default False)          # 聊天回复是否已推送
    created_at: DateTime (server_default=now)
```

### 索引

- `spendings.created_at DESC` — 列表查询
- `spendings.category` — 分类筛选

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/spendings` | 提交消费，返回 `{spending, reaction, chat_reaction?}` |
| `GET` | `/api/spendings` | 消费列表（`?page=1&category=餐饮`），每条含 reaction |
| `GET` | `/api/spendings/stats` | 本月概况：`{total, category_breakdown, ajiu_comment}` |

### POST /api/spendings 请求体

```json
{
  "amount": 35.5,
  "category": "餐饮",
  "note": "麻辣烫加一杯奶茶"
}
```

### POST /api/spendings 响应

```json
{
  "id": "uuid",
  "amount": 35.5,
  "category": "餐饮",
  "note": "麻辣烫加一杯奶茶",
  "reaction": "又是麻辣烫？这周第三次了，你是打算把店搬回家？",
  "chat_reaction": null,
  "created_at": "2026-06-16T19:30:00Z"
}
```

### GET /api/spendings/stats 响应

```json
{
  "month": "2026-06",
  "total": 2840.0,
  "by_category": {
    "餐饮": 1200.0,
    "购物": 800.0,
    "烟酒": 420.0,
    "娱乐": 300.0,
    "交通": 120.0
  },
  "ajiu_comment": "这个月你在烟上花了420。够买两本好书了。算了不念叨了你也不听。"
}
```

## LLM 两级反应逻辑

每笔消费 POST 进来，调用 LLM 判断：

系统提示词上下文：
- 用户当月同类消费次数 + 总额
- 本月总消费
- 阿玖人格（毒舌+关心）

```json
{
  "reaction": "卡片级吐槽（1-2句，阿玖语气。必填）",
  "needs_chat": true/false,
  "chat_reaction": "聊天级长回复（3-5句。needs_chat=false 时留空）"
}
```

**needs_chat 触发条件**（任一满足即触发）：
- `category == "烟酒"` → 每次都触发
- `same_category_count_24h >= 3` → 同类太频繁
- `amount > monthly_avg * 2` → 单笔异常大额
- `note` 含 "冲动" "忍不住" "又买了" → 用户自己觉得不该买

**语气指导**：
- 烟酒：从担心出发，不要只说教。"这个月第X次了……你真的想戒的话我可以帮你记"
- 重复消费：翻白眼吐槽但轻松。"行了行了，知道你喜欢吃这个，但能不能换个口味"
- 大额消费：先问原因再念叨。"突然花这么多？发生什么了？……算了反正是你的钱"
- 普通消费：有趣简短。"记下了。下次请我喝一杯（虽然我不能喝）"

## Flutter 改动

### 录入入口
- 聊天页右下角 FAB（"+"图标），弹出 BottomSheet
- BottomSheet 内容：金额输入、分类下拉、备注文本框、提交按钮

### 消费卡片
- 提交后在聊天流插入消费卡片组件
- 卡片显示：emoji 分类图标 + 金额 + 分类标签
- 卡片下方显示阿玖 reaction（气泡样式）

### 聊天级反应
- 如果 API 返回 `chat_reaction`，在卡片后自动插入一条阿玖消息
- 用户看到的体验：消费卡片 → 阿玖突然冒出来念叨

### 统计入口
- 设置页增加"消费记录"入口
- 统计页：本月总额、分类饼图、阿玖点评文案

## 与现有代码的关系

| 文件 | 改动 |
|------|------|
| `backend/app/models/spending.py` | 新建：Spending 模型 |
| `backend/app/services/spending.py` | 新建：SpendingService（含 LLM 判断逻辑） |
| `backend/app/routes/spendings.py` | 新建：API 路由 |
| `backend/app/prompts/ajiu.py` | 追加：记账模式的系统提示词 |
| `backend/app/main.py` | 挂载 spending router |
| `app/lib/screens/chat_screen.dart` | 加 FAB + 消费卡片渲染 |
| `app/lib/screens/settings_screen.dart` | 加消费记录入口 |
| `app/lib/widgets/spending_card.dart` | 新建：消费卡片组件 |
| `app/lib/providers/spending_provider.dart` | 新建：消费状态管理 |
| `alembic` | 新增迁移 |

## 安全分级
- 记账操作：🟡 首次确认，后续免确认
- 所有消费操作必须带设备认证 token

## 测试计划

- `test_spending_create_with_reaction` — 提交消费应返回阿玖反应
- `test_spending_chat_reaction_triggers` — 烟酒类应触发聊天级反应
- `test_spending_normal_no_chat` — 普通小消费不应触发聊天
- `test_spending_list` — 列表查询
- `test_spending_stats` — 统计接口
- `test_spending_category_filter` — 分类筛选
