# 阿玖 V1.0 Alpha — 前端架构设计

> 把后端已完成的 P0-P2 能力全部落地到 Flutter 端，让阿玖真正能用起来。

## 范围

**入 V1.0 Alpha：** 后端已实现的所有模块

| 模块 | 后端状态 | 前端 α 目标 |
|------|---------|------------|
| 聊天 | ✅ | 增强：模式指示器 + 教练问答面板 |
| 教练引擎 | ✅ | CoachPanel 组件 + 六问交互 |
| 任务 CRUD | ✅ | GoalsScreen + GoalDetailScreen |
| 梗检索 | ✅ | MemesScreen + 保留/删除 |
| 消费记账 | ✅ | 已有，无需改动 |
| 设置 | ✅ | 已有，补模式信息展示 |

**不入 α：**
- P3 设备/视觉/声音
- 管家模式定时推送（需要后台任务 + 推送通道）
- Embedding 模型最终选型
- 视觉特效 / 动画

## 架构

### 目录（新增标 `+`）

```
app/lib/
├── main.dart
├── app.dart                          # MaterialApp + Provider 挂载 + 路由
├── core/
│   ├── api_client.dart               # HTTP 封装（已存在，补 API 方法）
│   └── theme.dart                    # 阿玖主题色
├── models/
│   ├── chat_message.dart             # 已存在
│   ├── spending.dart                 # 已存在
│ + ├── goal.dart                     # Goal 模型
│ + └── meme.dart                     # Meme 模型
├── providers/
│   ├── chat_provider.dart            # 已存在，增强（模式检测 + 教练状态）
│   ├── spending_provider.dart        # 已存在
│ + ├── goal_provider.dart            # Goal CRUD
│ + └── meme_provider.dart            # 梗列表 + 保留/删除
├── screens/
│   ├── chat_screen.dart              # 已存在
│   ├── settings_screen.dart          # 已存在
│   ├── spending_stats_screen.dart    # 已存在
│ + ├── goals_screen.dart             # 任务列表
│ + ├── goal_detail_screen.dart       # 任务详情 + 里程碑
│ + └── memes_screen.dart             # 今日梗 + 管理
└── widgets/
    ├── chat_bubble.dart              # 已存在
    ├── message_input.dart            # 已存在
    ├── spending_card.dart            # 已存在
    ├── spending_entry_sheet.dart     # 已存在
│ + ├── goal_card.dart                # 任务卡片
│ + ├── milestone_tile.dart           # 里程碑勾选
│ + ├── meme_card.dart                # 梗卡片
│ + ├── coach_panel.dart              # 教练问答面板
│ + ├── mode_indicator.dart           # 模式标识
│ + └── main_scaffold.dart            # 底部导航壳
```

### 导航

```
底部 TabBar（4 tab）：
  💬 阿玖     → ChatScreen
  🎯 任务     → GoalsScreen → GoalDetailScreen
  🔥 梗       → MemesScreen
  ⚙️ 设置     → SettingsScreen

FAB（聊天页专属）：
  💰 记账     → SpendingEntrySheet
```

### 数据流

```
Screen ←→ Provider ←→ ApiClient ←→ 后端 API (localhost:8000)
                ↕
             Model
```

状态管理：Provider（不改 Riverpod，保持轻量）。

### API 方法（ApiClient 需补）

```dart
// Goal
Future<List<Goal>> getGoals()
Future<Goal> getGoal(String id)
Future<Goal> createGoal(Map<String, dynamic> data)
Future<Goal> updateGoal(String id, Map<String, dynamic> data)
Future<void> abandonGoal(String id)

// Meme
Future<List<Meme>> getMemes()
Future<Meme> keepMeme(String id, bool keep)
Future<void> deleteMeme(String id)

// Chat（增强）
Future<Map<String, dynamic>> sendMessage(String content, {String? mode})
```

## 新增页面 & 组件

### 1. MainScaffold（底部导航壳）

包裹 MaterialApp，提供 4 个 tab。职责：
- 维护当前 tab index
- 根据 tab 决定是否显示 FAB（只有聊天页显示记账按钮）
- 懒加载各 tab 的 screen

### 2. ModeIndicator（模式标识）

聊天页顶部的轻量 widget：
- 显示当前模式名称（闲聊 / 教练 / 管家）
- 3 种颜色对应 3 种模式
- 模式切换时短暂动画
- 数据来自 ChatProvider.currentMode

### 3. CoachPanel（教练问答面板）

聊天页内嵌的教练对话 UI。当 ChatProvider.currentMode == 'coach' 时展开：
- 顶部：六问进度条（当前问题 / 6，已完成的显示 ✓）
- 主区：当前问题的阿玖提问（来自后端 coach_state）
- 输入区：用户回答（复用 message_input）
- 表现：追问时面板微抖动，放行时叹气动画
- 确认阶段：计划摘要预览 + 行/不行两个按钮

### 4. GoalCard（任务卡片）

GoalsScreen 的列表项：
- 标题 + 简短描述
- 状态标签（进行中 / 已完成 / 已放弃）+ 颜色区分
- 复活次数（"复活赛第 3 轮"）
- 点击进入 GoalDetailScreen

### 5. GoalDetailScreen（任务详情）

- 目标标题 + 完整描述
- 里程碑列表（每项显示文字 + 通过标准 + 勾选框）
- 已完成 / 放弃按钮
- 阿玖的评论（来自创建时的计划摘要）

### 6. MemeCard + MemesScreen

MemeCard：
- 梗标题 + 来源
- 保留 / 删除按钮（红绿双色）
- 保留的梗高亮边框

MemesScreen：
- 顶部：上次更新时间
- 列表：所有今日梗
- 空状态："今日已无梗，阿玖 22:00 帮你捞新的"

## Provider 设计

### ChatProvider（增强项）

```
现有：发送消息、接收 SSE 流、消息列表
新增：
  - currentMode: String ('casual'|'coach'|'butler')
  - coachState: Map?  # 当前教练状态
  - 模式自动检测（解析后端 chat/stream 返回的 mode 字段）
```

### GoalProvider

```
- goals: List<Goal>
- fetchGoals(), refreshGoal(id)
- createGoal(data), updateGoal(id, data), abandonGoal(id)
- activeGoals: 仅进行中的任务
```

### MemeProvider

```
- memes: List<Meme>
- keptMemes: 已保留的梗
- fetchTodayMemes()
- toggleKeep(id), deleteMeme(id)
```

## 后端需改动

### Chat 路由增强

`POST /api/chat/stream` 返回的 SSE 事件中，每个 `token` 事件需附带 `mode` 字段（当前阿玖判断的模式）。前端根据此字段更新 `ChatProvider.currentMode`。

### 模式切换端点的确认

后端已实现教练状态机，前端 chat 消息流需区分：
- 普通消息（闲聊）
- 教练问答（六问逐条）
- 计划预览（确认/拒绝/修改）

`POST /api/chat/stream` 的 SSE 事件中增加 `event: coach_state` 事件，携带当前 coach_state JSON。

## 测试策略

- **Provider 单测**：Mock ApiClient，验证每个 Provider 的 CRUD 行为
- **Widget 单测**：主要组件（GoalCard, MemeCard, CoachPanel）的渲染和交互
- **集成测试**：完整教练流程（开启 → 六问 → 计划确认）
- **目标**：新增代码覆盖率 ≥ 70%

## 风险

| 风险 | 缓解 |
|------|------|
| SSE 流解析复杂（新增 mode/coach_state 事件） | 复用现有 SSE 解析，新增事件类型用 switch-case |
| 教练 UI 交互路径多（追问/放行/确认/拒绝/修改） | 后端 coach_state 驱动 UI，前端只做渲染 |
| Provider 数量增多导致 widget rebuild | 用 `Selector`/`Consumer` 精确订阅，避免 `context.watch` 全局刷新 |

## 未决

- [ ] 教练流程 UI 的具体动画效果（交 GPT 设计）
- [ ] 梗卡片具体视觉样式（交 GPT 设计）
- [ ] 任务详情页的里程碑交互细节
