# 阿玖 V1.0 Alpha — 前端 Handoff

> 接手这份文档后，直接开始写代码。所有需要的信息都在这里。

---

## 你是谁、在做什么

你在给**阿玖**（ajiur）做 Flutter 前端。阿玖是一个个人专属 AI Agent——毒舌可爱反差的 AI 伴侣。她不是聊天机器人，是有性格的智能体。

**当前任务：** 后端 P0-P2 已经全部完成（教练引擎、任务系统、支付监控、梗系统、记忆系统、51 个测试全绿），但 Flutter 端只有一个聊天页面+消费页。你需要把后端的全部能力落到前端，做出 V1.0 Alpha。

---

## 技术栈

- Flutter 3.x + Dart
- 状态管理：`flutter_riverpod`（手动 `StateNotifier` + `StateNotifierProvider`，**不用** `@riverpod` 注解）
- HTTP：`dio`
- UI：Material 3
- 后端：FastAPI（localhost:8000）

---

## 项目位置

```
D:\Claude code\个人API应用\
├── backend/          # FastAPI 后端（已完成，不要动）
├── app/              # Flutter 前端（你要改的）
│   └── lib/
│       ├── main.dart
│       ├── app.dart
│       ├── core/     # api_client.dart, theme.dart
│       ├── models/   # chat_message.dart, spending.dart
│       ├── providers/# chat_provider.dart, spending_provider.dart
│       ├── screens/  # chat_screen.dart, settings_screen.dart, spending_stats_screen.dart
│       └── widgets/  # chat_bubble.dart, message_input.dart, spending_card.dart, spending_entry_sheet.dart
└── docs/superpowers/
    ├── specs/2026-06-17-v1-alpha-frontend-design.md  # 设计文档（必读）
    └── plans/2026-06-17-v1-alpha-frontend.md         # 15 Task 实施计划（必读）
```

---

## 必须遵守的代码模式

### Provider 模式
```dart
final myProvider = StateNotifierProvider<MyNotifier, List<MyModel>>((ref) {
  final apiAsync = ref.watch(apiClientProvider);
  return apiAsync.when(
    data: (api) => MyNotifier(api),
    loading: () => MyNotifier.loading(),
    error: (e, _) => MyNotifier.error(e),
  );
});

class MyNotifier extends StateNotifier<List<MyModel>> {
  final ApiClient? _api;
  MyNotifier(this._api) : super([]);
  MyNotifier.loading() : _api = null, super([]);
  MyNotifier.error(Object e) : _api = null, super([]);
}
```

### Screen 模式
```dart
class MyScreen extends ConsumerStatefulWidget { ... }  // 需要生命周期
// 或
class MyScreen extends ConsumerWidget { ... }           // 只需 watch
```

### 导航
- 底部 4 Tab：`MainScaffold`（`NavigationBar`）
- 子页面：`Navigator.of(context).push(MaterialPageRoute(...))`
- 底部弹窗：`showModalBottomSheet`

### API 调用
- 所有请求走 `ApiClient`（Dio 实例，自动注入 `X-Device-Token`）
- 后端返回 snake_case JSON → Dart 模型用 `fromJson` 转换
- SSE 流用 `ChatStreamEvent.fromJson` 解析

---

## 后端 API（已完成，前端直接调）

| 端点 | 用途 |
|------|------|
| `POST /api/chat` | 发送消息（SSE 流，meta/delta/done 事件） |
| `GET /api/conversations/{id}/messages` | 历史消息 |
| `GET /api/goals` | 全部任务列表 |
| `GET /api/goals/{id}` | 任务详情（含 checks） |
| `PATCH /api/goals/{id}` | 更新任务状态 `{status: "completed"}` |
| `POST /api/goals/{id}/revive` | 复活已放弃任务 |
| `POST /api/goals/{id}/checks` | 打卡 `{status: "done"}` |
| `GET /api/memes/today` | 今日梗列表 |
| `POST /api/memes/{id}/keep` | 保留梗 |
| `POST /api/memes/{id}/discard` | 删除梗 |

**SSE 事件结构（重要！）：**
```json
// meta 事件（连接初始）
{"type": "meta", "conversation_id": "...", "mode": "casual|coach", "coach_state": {...}}

// delta 事件（流式 token）
{"type": "delta", "content": "..."}

// done 事件（结束）
{"type": "done", "coach_action": "plan_ready|confirmed|...", "coach_state": {...}}

// error 事件
{"type": "error", "message": "..."}
```

---

## 核心设计决策

1. **底部 4 Tab**：💬阿玖 / 🎯任务 / 🔥梗 / ⚙️设置
2. **聊天页**：集成 `ModeIndicator`（顶部模式标识）+ `CoachPanel`（教练模式下展开的六问面板）
3. **模式**：闲聊(casual) / 教练(coach) / 管家(butler)，由后端 SSE meta 事件的 `mode` 字段驱动
4. **教练流程**：6 必问 → LLM 评估 → 追问/放行 → 计划预览 → 确认/拒绝/修改
5. **里程碑**：`milestones` 是 `List<Map<String, dynamic>>`，每项 `{text: "", criteria: "", done: false}`

---

## 你需要做的

**两个必读文件（按顺序）：**
1. `docs/superpowers/specs/2026-06-17-v1-alpha-frontend-design.md` — 架构设计，所有组件的职责
2. `docs/superpowers/plans/2026-06-17-v1-alpha-frontend.md` — 15 个 Task，含完整代码

**实施顺序：**
```
Task 1 (Models) → Task 2 (ApiClient) → Task 3,4,5 (Providers)
                                          ↓
                     Task 6 (MainScaffold) → Task 7-10 (Widgets)
                                              ↓
                               Task 11,12,13 (Screens) → Task 14 (ChatScreen) → Task 15 (验证)
```

**你可以自由发挥的部分：**
- 聊天页 ModeIndicator / CoachPanel 的具体 layout 和间距（设计文档里的布局是骨架）
- 教练流程动画（追问抖动、放行叹气）
- 梗卡片的视觉样式
- 任何让 UI 更好看的东西

**不要动：**
- 后端代码（`backend/`）
- 现有 Flutter 代码的核心逻辑（API 调用方式、Provider 模式、认证流程）

---

## 环境

```bash
# 启动后端（如果没跑）
cd "D:\Claude code\个人API应用\backend"
docker compose up -d db
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 运行 Flutter 测试
cd "D:\Claude code\个人API应用\app"
flutter test

# 静态分析
flutter analyze
```

---

## 阿玖性格（写 UI 文案时参考）

- 毒舌但可爱，傲娇本质——"傲是外壳，娇是内心"
- 嘴上不饶人，手上不偷懒
- 用户真需要她的时候，立刻收起傲娇变温柔
- 称呼：永远叫"阿玖"，禁止"AI助手""聊天机器人"
- 她叫用户"笨蛋"是爱称
