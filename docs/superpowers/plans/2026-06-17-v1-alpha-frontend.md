# 阿玖 V1.0 Alpha — 前端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将后端已完成的 P0-P2 全部能力落到 Flutter 端，4 个 tab（聊天/任务/梗/设置）+ 教练问答 UI + 任务/梗管理。

**Architecture:** 保持现有 Riverpod + StateNotifierProvider 模式。新增 2 个 Model、2 个 Provider、6 个 Widget、3 个 Screen。ApiClient 增强 SSE 解析 + 补 Goal/Meme API 方法。ChatProvider 增强 mode/coach_state 追踪。

**Tech Stack:** Flutter 3.x, Dart, flutter_riverpod, dio, Material 3

**关键发现：** 后端 chat 路由已在 SSE `meta` 事件中输出 `mode` 和 `coach_state`，在 `done` 事件中输出 `coach_action` 和 `coach_state`。后端 Goal/Meme API 路由已齐全。前端只需补齐解析和 UI。

---

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 创建 | `app/lib/models/goal.dart` | Goal + GoalCheck 不可变模型 |
| 创建 | `app/lib/models/meme.dart` | Meme 不可变模型 |
| 修改 | `app/lib/core/api_client.dart` | 增强 ChatStreamEvent（解析 mode/coach_state/coach_action），补 Goal/Meme CRUD 方法 |
| 创建 | `app/lib/providers/goal_provider.dart` | Goal 列表状态管理 |
| 创建 | `app/lib/providers/meme_provider.dart` | 今日梗列表状态管理 |
| 修改 | `app/lib/providers/chat_provider.dart` | 新增 currentMode + coachState 状态 |
| 创建 | `app/lib/widgets/mode_indicator.dart` | 聊天页顶部模式标识条 |
| 创建 | `app/lib/widgets/coach_panel.dart` | 教练问答面板（进度条+六问交互） |
| 创建 | `app/lib/widgets/goal_card.dart` | 任务列表卡片 |
| 创建 | `app/lib/widgets/milestone_tile.dart` | 里程碑勾选行 |
| 创建 | `app/lib/widgets/meme_card.dart` | 梗卡片（保留/删除） |
| 创建 | `app/lib/widgets/main_scaffold.dart` | 底部 4 Tab 导航壳 |
| 创建 | `app/lib/screens/goals_screen.dart` | 任务列表页 |
| 创建 | `app/lib/screens/goal_detail_screen.dart` | 任务详情+里程碑 |
| 创建 | `app/lib/screens/memes_screen.dart` | 今日梗列表页 |
| 修改 | `app/lib/screens/chat_screen.dart` | 集成 ModeIndicator + CoachPanel |
| 修改 | `app/lib/app.dart` | 入口改为 MainScaffold，注册路由 |
| 创建 | `app/test/models/goal_test.dart` | Goal 模型单测 |
| 创建 | `app/test/models/meme_test.dart` | Meme 模型单测 |
| 创建 | `app/test/providers/goal_provider_test.dart` | GoalProvider 单测 |
| 创建 | `app/test/providers/meme_provider_test.dart` | MemeProvider 单测 |
| 创建 | `app/test/widgets/coach_panel_test.dart` | CoachPanel widget 单测 |

---

### Task 1: Dart 数据模型

**Files:**
- Create: `app/lib/models/goal.dart`
- Create: `app/lib/models/meme.dart`
- Create: `app/test/models/goal_test.dart`
- Create: `app/test/models/meme_test.dart`

- [ ] **Step 1: 写 Goal 模型测试**

```dart
// app/test/models/goal_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_ai_app/models/goal.dart';

void main() {
  group('Goal', () {
    final sampleJson = {
      'id': '550e8400-e29b-41d4-a716-446655440000',
      'conversation_id': '660e8400-e29b-41d4-a716-446655440001',
      'title': '减重到70kg',
      'description': '通过饮食和运动在3个月内减重10kg',
      'milestones': [
        {'text': '第一周：每天跑步30分钟', 'criteria': '连续7天完成'},
        {'text': '第一个月：减重3kg', 'criteria': '体重秤显示<77kg'},
      ],
      'status': 'active',
      'revive_count': 2,
      'created_at': '2026-06-17T10:00:00Z',
      'completed_at': null,
    };

    test('fromJson parses all fields', () {
      final goal = Goal.fromJson(sampleJson);
      expect(goal.id, '550e8400-e29b-41d4-a716-446655440000');
      expect(goal.title, '减重到70kg');
      expect(goal.status, 'active');
      expect(goal.reviveCount, 2);
      expect(goal.milestones.length, 2);
      expect(goal.completedAt, isNull);
    });

    test('fromJson parses completed_at when present', () {
      final jsonWithCompleted = {...sampleJson, 'completed_at': '2026-09-17T10:00:00Z'};
      final goal = Goal.fromJson(jsonWithCompleted);
      expect(goal.completedAt, isNotNull);
    });

    test('statusLabel returns Chinese labels', () {
      expect(Goal.fromJson({...sampleJson, 'status': 'active'}).statusLabel, '进行中');
      expect(Goal.fromJson({...sampleJson, 'status': 'paused'}).statusLabel, '已暂停');
      expect(Goal.fromJson({...sampleJson, 'status': 'completed'}).statusLabel, '已完成');
      expect(Goal.fromJson({...sampleJson, 'status': 'abandoned'}).statusLabel, '已放弃');
    });

    test('statusColor returns correct colors', () {
      expect(Goal.fromJson({...sampleJson, 'status': 'active'}).statusColor, isNotNull);
    });
  });

  group('GoalCheck', () {
    test('fromJson parses all fields', () {
      final json = {
        'id': '770e8400-e29b-41d4-a716-446655440002',
        'goal_id': '550e8400-e29b-41d4-a716-446655440000',
        'check_time': '2026-06-18T08:00:00Z',
        'status': 'done',
        'note': '完成5km跑步',
      };
      final check = GoalCheck.fromJson(json);
      expect(check.status, 'done');
      expect(check.note, '完成5km跑步');
    });
  });
}
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/models/goal_test.dart
```

预期：FAIL — `goal.dart` 文件不存在

- [ ] **Step 3: 写 Goal + GoalCheck 模型**

```dart
// app/lib/models/goal.dart
class Goal {
  final String id;
  final String conversationId;
  final String title;
  final String description;
  final List<Map<String, dynamic>> milestones;
  final String status;
  final int reviveCount;
  final DateTime createdAt;
  final DateTime? completedAt;
  final List<GoalCheck> checks;

  const Goal({
    required this.id,
    required this.conversationId,
    required this.title,
    required this.description,
    this.milestones = const [],
    this.status = 'active',
    this.reviveCount = 0,
    required this.createdAt,
    this.completedAt,
    this.checks = const [],
  });

  factory Goal.fromJson(Map<String, dynamic> json) {
    return Goal(
      id: json['id'] as String,
      conversationId: json['conversation_id'] as String,
      title: json['title'] as String,
      description: (json['description'] as String?) ?? '',
      milestones: (json['milestones'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
      status: (json['status'] as String?) ?? 'active',
      reviveCount: (json['revive_count'] as int?) ?? 0,
      createdAt: DateTime.parse(json['created_at'] as String),
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
      checks: (json['checks'] as List<dynamic>?)
              ?.map((e) => GoalCheck.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  String get statusLabel {
    switch (status) {
      case 'active':
        return '进行中';
      case 'paused':
        return '已暂停';
      case 'completed':
        return '已完成';
      case 'abandoned':
        return '已放弃';
      default:
        return status;
    }
  }

  int get statusColor {
    switch (status) {
      case 'active':
        return 0xFF6366F1; // 紫色
      case 'paused':
        return 0xFFF59E0B; // 橙黄
      case 'completed':
        return 0xFF10B981; // 绿色
      case 'abandoned':
        return 0xFF9CA3AF; // 灰色
      default:
        return 0xFF9CA3AF;
    }
  }

  int get completedMilestoneCount =>
      milestones.where((m) => m['done'] == true).length;

  double get progress => milestones.isEmpty
      ? 0.0
      : completedMilestoneCount / milestones.length;
}

class GoalCheck {
  final String id;
  final String goalId;
  final DateTime checkTime;
  final String status; // done / skipped / missed / pending
  final String? note;

  const GoalCheck({
    required this.id,
    required this.goalId,
    required this.checkTime,
    this.status = 'pending',
    this.note,
  });

  factory GoalCheck.fromJson(Map<String, dynamic> json) {
    return GoalCheck(
      id: json['id'] as String,
      goalId: json['goal_id'] as String,
      checkTime: DateTime.parse(json['check_time'] as String),
      status: (json['status'] as String?) ?? 'pending',
      note: json['note'] as String?,
    );
  }
}
```

- [ ] **Step 4: 运行 Goal 测试**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/models/goal_test.dart
```

预期：PASS

- [ ] **Step 5: 写 Meme 模型测试**

```dart
// app/test/models/meme_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_ai_app/models/meme.dart';

void main() {
  group('Meme', () {
    final sampleJson = {
      'id': '880e8400-e29b-41d4-a716-446655440003',
      'title': '⚡️ 卧槽，这也太离谱了吧',
      'source': 'bilibili',
      'url': 'https://bilibili.com/video/BV1xx41127xx',
      'summary': '一个剪辑师把鬼畜做到了一帧一帧对嘴型，播放量三天破千万',
      'tags': '鬼畜,搞笑,神剪辑',
      'kept': false,
      'discarded': false,
      'asked': false,
      'fetched_at': '2026-06-16T22:00:00Z',
    };

    test('fromJson parses all fields', () {
      final meme = Meme.fromJson(sampleJson);
      expect(meme.id, '880e8400-e29b-41d4-a716-446655440003');
      expect(meme.title, '⚡️ 卧槽，这也太离谱了吧');
      expect(meme.source, 'bilibili');
      expect(meme.kept, false);
      expect(meme.discarded, false);
      expect(meme.summary, isNotNull);
    });

    test('fromJson handles missing optional fields', () {
      final minimal = {
        'id': '990e8400-e29b-41d4-a716-446655440004',
        'title': '测试梗',
        'source': 'bilibili',
        'kept': false,
        'discarded': false,
        'asked': false,
        'fetched_at': '2026-06-16T22:00:00Z',
      };
      final meme = Meme.fromJson(minimal);
      expect(meme.url, isNull);
      expect(meme.summary, isNull);
      expect(meme.tags, isNull);
    });
  });
}
```

- [ ] **Step 6: 写 Meme 模型**

```dart
// app/lib/models/meme.dart
class Meme {
  final String id;
  final String title;
  final String source;
  final String? url;
  final String? summary;
  final String? tags;
  final bool kept;
  final bool discarded;
  final bool asked;
  final DateTime fetchedAt;

  const Meme({
    required this.id,
    required this.title,
    this.source = 'bilibili',
    this.url,
    this.summary,
    this.tags,
    this.kept = false,
    this.discarded = false,
    this.asked = false,
    required this.fetchedAt,
  });

  factory Meme.fromJson(Map<String, dynamic> json) {
    return Meme(
      id: json['id'] as String,
      title: json['title'] as String,
      source: (json['source'] as String?) ?? 'bilibili',
      url: json['url'] as String?,
      summary: json['summary'] as String?,
      tags: json['tags'] as String?,
      kept: (json['kept'] as bool?) ?? false,
      discarded: (json['discarded'] as bool?) ?? false,
      asked: (json['asked'] as bool?) ?? false,
      fetchedAt: DateTime.parse(json['fetched_at'] as String),
    );
  }
}
```

- [ ] **Step 7: 运行全部模型测试**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/models/
```

预期：全部 PASS（2 个测试文件，约 7 个 case）

- [ ] **Step 8: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/models/goal.dart app/lib/models/meme.dart app/test/models/ && git commit -m "feat: add Goal and Meme Dart models with tests"
```

---

### Task 2: ApiClient 增强

**Files:**
- Modify: `app/lib/core/api_client.dart`

- [ ] **Step 1: 增强 ChatStreamEvent，新增 meta 字段解析**

在 `api_client.dart` 中修改 `ChatStreamEvent` 类：

```dart
// 替换原有 ChatStreamEvent 为：
class ChatStreamEvent {
  final String type;         // "meta", "delta", "done", "error"
  final String? conversationId;
  final String? content;
  final String? message;     // error message
  final String? mode;        // "casual" | "coach" | "butler" (from meta event)
  final Map<String, dynamic>? coachState;  // 教练状态 (from meta/done events)
  final String? coachAction; // 教练动作 (from done event): "ask_question" | "follow_up" | "plan_ready" | "confirmed" | "abandoned" | "revise"

  ChatStreamEvent({
    required this.type,
    this.conversationId,
    this.content,
    this.message,
    this.mode,
    this.coachState,
    this.coachAction,
  });

  factory ChatStreamEvent.fromJson(Map<String, dynamic> json) {
    return ChatStreamEvent(
      type: json['type'] as String? ?? 'unknown',
      conversationId: json['conversation_id'] as String?,
      content: json['content'] as String?,
      message: json['message'] as String?,
      mode: json['mode'] as String?,
      coachState: json['coach_state'] is Map<String, dynamic>
          ? json['coach_state'] as Map<String, dynamic>
          : null,
      coachAction: json['coach_action'] as String?,
    );
  }
}
```

- [ ] **Step 2: 在 ApiClient 中新增 Goal API 方法**

在 `ApiClient` 类末尾新增：

```dart
  // ---- Goals ----

  Future<List<Map<String, dynamic>>> getGoals() async {
    final resp = await _dio.get('/goals');
    return List<Map<String, dynamic>>.from(resp.data as List);
  }

  Future<List<Map<String, dynamic>>> getActiveGoals() async {
    final resp = await _dio.get('/goals/active');
    return List<Map<String, dynamic>>.from(resp.data as List);
  }

  Future<Map<String, dynamic>> getGoal(String id) async {
    final resp = await _dio.get('/goals/$id');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateGoalStatus(String id, String status) async {
    final resp = await _dio.patch('/goals/$id', data: {'status': status});
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> reviveGoal(String id) async {
    final resp = await _dio.post('/goals/$id/revive');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> addGoalCheck(String goalId, {String status = 'done', String? note}) async {
    final resp = await _dio.post('/goals/$goalId/checks', data: {
      'status': status,
      if (note != null) 'note': note,
    });
    return resp.data as Map<String, dynamic>;
  }
```

- [ ] **Step 3: 在 ApiClient 中新增 Meme API 方法**

```dart
  // ---- Memes ----

  Future<List<Map<String, dynamic>>> getTodayMemes() async {
    final resp = await _dio.get('/memes/today');
    return List<Map<String, dynamic>>.from(resp.data as List);
  }

  Future<Map<String, dynamic>> fetchMemes() async {
    final resp = await _dio.post('/memes/fetch');
    return resp.data; // returns List but keep as-is for manual trigger
  }

  Future<Map<String, dynamic>> keepMeme(String id) async {
    final resp = await _dio.post('/memes/$id/keep');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> discardMeme(String id) async {
    final resp = await _dio.post('/memes/$id/discard');
    return resp.data as Map<String, dynamic>;
  }
```

- [ ] **Step 4: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/core/api_client.dart
```

预期：no issues found

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/core/api_client.dart && git commit -m "feat: enhance ChatStreamEvent with mode/coach_state, add Goal+Meme API methods"
```

---

### Task 3: GoalProvider

**Files:**
- Create: `app/lib/providers/goal_provider.dart`
- Create: `app/test/providers/goal_provider_test.dart`

- [ ] **Step 1: 写 GoalProvider 测试**

```dart
// app/test/providers/goal_provider_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_ai_app/providers/goal_provider.dart';

void main() {
  test('GoalNotifier.loading creates empty state', () {
    final notifier = GoalNotifier.loading();
    expect(notifier.state, isEmpty);
  });

  test('GoalNotifier.error creates empty state', () {
    final notifier = GoalNotifier.error(Exception('test error'));
    expect(notifier.state, isEmpty);
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/providers/goal_provider_test.dart
```

预期：FAIL

- [ ] **Step 3: 写 GoalProvider**

```dart
// app/lib/providers/goal_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/goal.dart';
import 'chat_provider.dart';

final goalProvider = StateNotifierProvider<GoalNotifier, List<Goal>>((ref) {
  final apiAsync = ref.watch(apiClientProvider);
  return apiAsync.when(
    data: (api) => GoalNotifier(api),
    loading: () => GoalNotifier.loading(),
    error: (e, _) => GoalNotifier.error(e),
  );
});

class GoalNotifier extends StateNotifier<List<Goal>> {
  final ApiClient? _api;

  GoalNotifier(this._api) : super([]);

  GoalNotifier.loading() : _api = null, super([]);

  GoalNotifier.error(Object error) : _api = null, super([]);

  Future<void> loadGoals() async {
    if (_api == null) return;
    try {
      final data = await _api!.getGoals();
      state = data.map((json) => Goal.fromJson(json)).toList();
    } catch (_) {}
  }

  Future<Goal?> getGoalDetail(String id) async {
    if (_api == null) return null;
    try {
      final data = await _api!.getGoal(id);
      return Goal.fromJson(data);
    } catch (_) {
      return null;
    }
  }

  Future<void> updateStatus(String id, String status) async {
    if (_api == null) return;
    try {
      await _api!.updateGoalStatus(id, status);
      await loadGoals();
    } catch (_) {}
  }

  Future<void> revive(String id) async {
    if (_api == null) return;
    try {
      await _api!.reviveGoal(id);
      await loadGoals();
    } catch (_) {}
  }

  Future<void> addCheck(String goalId, {String status = 'done', String? note}) async {
    if (_api == null) return;
    try {
      await _api!.addGoalCheck(goalId, status: status, note: note);
      await loadGoals();
    } catch (_) {}
  }

  List<Goal> get activeGoals =>
      state.where((g) => g.status == 'active').toList();

  List<Goal> get completedGoals =>
      state.where((g) => g.status == 'completed').toList();
}
```

- [ ] **Step 4: 运行 GoalProvider 测试**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/providers/goal_provider_test.dart
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/providers/goal_provider.dart app/test/providers/goal_provider_test.dart && git commit -m "feat: add GoalProvider with tests"
```

---

### Task 4: MemeProvider

**Files:**
- Create: `app/lib/providers/meme_provider.dart`
- Create: `app/test/providers/meme_provider_test.dart`

- [ ] **Step 1: 写 MemeProvider 测试**

```dart
// app/test/providers/meme_provider_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_ai_app/providers/meme_provider.dart';

void main() {
  test('MemeNotifier.loading creates empty state', () {
    final notifier = MemeNotifier.loading();
    expect(notifier.state, isEmpty);
  });

  test('MemeNotifier.error creates empty state', () {
    final notifier = MemeNotifier.error(Exception('test error'));
    expect(notifier.state, isEmpty);
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/providers/meme_provider_test.dart
```

预期：FAIL

- [ ] **Step 3: 写 MemeProvider**

```dart
// app/lib/providers/meme_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/meme.dart';
import 'chat_provider.dart';

final memeProvider = StateNotifierProvider<MemeNotifier, List<Meme>>((ref) {
  final apiAsync = ref.watch(apiClientProvider);
  return apiAsync.when(
    data: (api) => MemeNotifier(api),
    loading: () => MemeNotifier.loading(),
    error: (e, _) => MemeNotifier.error(e),
  );
});

class MemeNotifier extends StateNotifier<List<Meme>> {
  final ApiClient? _api;

  MemeNotifier(this._api) : super([]);

  MemeNotifier.loading() : _api = null, super([]);

  MemeNotifier.error(Object error) : _api = null, super([]);

  Future<void> loadTodayMemes() async {
    if (_api == null) return;
    try {
      final data = await _api!.getTodayMemes();
      state = data.map((json) => Meme.fromJson(json)).toList();
    } catch (_) {}
  }

  Future<void> keep(String id) async {
    if (_api == null) return;
    try {
      await _api!.keepMeme(id);
      // 更新本地状态
      state = state.map((m) {
        if (m.id == id) {
          return Meme(
            id: m.id,
            title: m.title,
            source: m.source,
            url: m.url,
            summary: m.summary,
            tags: m.tags,
            kept: true,
            discarded: false,
            asked: m.asked,
            fetchedAt: m.fetchedAt,
          );
        }
        return m;
      }).toList();
    } catch (_) {}
  }

  Future<void> discard(String id) async {
    if (_api == null) return;
    try {
      await _api!.discardMeme(id);
      state = state.map((m) {
        if (m.id == id) {
          return Meme(
            id: m.id,
            title: m.title,
            source: m.source,
            url: m.url,
            summary: m.summary,
            tags: m.tags,
            kept: false,
            discarded: true,
            asked: m.asked,
            fetchedAt: m.fetchedAt,
          );
        }
        return m;
      }).toList();
    } catch (_) {}
  }

  List<Meme> get keptMemes => state.where((m) => m.kept).toList();
}
```

- [ ] **Step 4: 运行 MemeProvider 测试**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/providers/meme_provider_test.dart
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/providers/meme_provider.dart app/test/providers/meme_provider_test.dart && git commit -m "feat: add MemeProvider with tests"
```

---

### Task 5: ChatProvider 增强 — 模式 + 教练状态

**Files:**
- Modify: `app/lib/providers/chat_provider.dart`

- [ ] **Step 1: 在 ChatNotifier 中新增 currentMode 和 coachState**

在 `chat_provider.dart` 的 `ChatNotifier` 类中新增字段和方法：

```dart
// 在 ChatNotifier 类内部，_conversationId 之后新增：
  String _currentMode = 'casual';
  Map<String, dynamic>? _coachState;

  String get currentMode => _currentMode;
  Map<String, dynamic>? get coachState => _coachState;
```

- [ ] **Step 2: 修改 sendMessage() 中的 SSE 事件处理**

修改 `sendMessage` 方法中 `await for` 循环内的事件处理：

```dart
  // 在 await for (final event in api.chatStream(...)) 循环内，
  // 处理 meta 事件时新增 mode/coachState 解析：
  
  case 'meta':
    _conversationId = event.conversationId ?? _conversationId;
    if (event.mode != null) {
      _currentMode = event.mode!;
    }
    if (event.coachState != null) {
      _coachState = event.coachState;
    }
    break;

  // 处理 done 事件时新增 coach_action/coach_state：
  case 'done':
    state = state.map((m) {
      if (m.id == assistantId) {
        return m.copyWith(isStreaming: false);
      }
      return m;
    }).toList();
    if (event.coachAction != null) {
      // 计划已确认 → 退出教练模式
      if (event.coachAction == 'confirmed' || event.coachAction == 'abandoned') {
        _currentMode = 'casual';
        _coachState = null;
      } else if (event.coachState != null) {
        _coachState = event.coachState;
      }
    }
    break;
```

- [ ] **Step 3: 新增 clearChat 重置模式状态**

修改 `clearChat()`：

```dart
  void clearChat() {
    state = [];
    _conversationId = null;
    _currentMode = 'casual';
    _coachState = null;
  }
```

- [ ] **Step 4: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/providers/chat_provider.dart
```

预期：no issues found

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/providers/chat_provider.dart && git commit -m "feat: add mode and coach_state tracking to ChatProvider"
```

---

### Task 6: MainScaffold — 底部导航壳

**Files:**
- Create: `app/lib/widgets/main_scaffold.dart`

- [ ] **Step 1: 写 MainScaffold**

```dart
// app/lib/widgets/main_scaffold.dart
import 'package:flutter/material.dart';
import '../screens/chat_screen.dart';
import '../screens/goals_screen.dart';
import '../screens/memes_screen.dart';
import '../screens/settings_screen.dart';

class MainScaffold extends StatefulWidget {
  const MainScaffold({super.key});

  @override
  State<MainScaffold> createState() => _MainScaffoldState();
}

class _MainScaffoldState extends State<MainScaffold> {
  int _currentIndex = 0;

  final _screens = const [
    ChatScreen(),
    GoalsScreen(),
    MemesScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() => _currentIndex = index);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: '阿玖',
          ),
          NavigationDestination(
            icon: Icon(Icons.flag_outlined),
            selectedIcon: Icon(Icons.flag),
            label: '任务',
          ),
          NavigationDestination(
            icon: Icon(Icons.local_fire_department_outlined),
            selectedIcon: Icon(Icons.local_fire_department),
            label: '梗',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: '设置',
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: 更新 App.dart，入口改为 MainScaffold**

修改 `app/lib/app.dart`：

```dart
import 'package:flutter/material.dart';
import 'core/theme.dart';
import 'widgets/main_scaffold.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '阿玖',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const MainScaffold(),
    );
  }
}
```

- [ ] **Step 3: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/widgets/main_scaffold.dart lib/app.dart
```

预期：no issues found

- [ ] **Step 4: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/widgets/main_scaffold.dart app/lib/app.dart && git commit -m "feat: add MainScaffold with 4-tab bottom navigation"
```

---

### Task 7: ModeIndicator — 模式标识

**Files:**
- Create: `app/lib/widgets/mode_indicator.dart`

- [ ] **Step 1: 写 ModeIndicator**

```dart
// app/lib/widgets/mode_indicator.dart
import 'package:flutter/material.dart';

class ModeIndicator extends StatelessWidget {
  final String mode;

  const ModeIndicator({super.key, this.mode = 'casual'});

  @override
  Widget build(BuildContext context) {
    final (label, color, icon) = switch (mode) {
      'coach' => ('教练模式', const Color(0xFF6366F1), Icons.psychology),
      'butler' => ('管家模式', const Color(0xFF10B981), Icons.assignment_turned_in),
      _ => ('闲聊', const Color(0xFFF59E0B), Icons.chat),
    };

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withAlpha(80)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/widgets/mode_indicator.dart
```

预期：no issues found

- [ ] **Step 3: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/widgets/mode_indicator.dart && git commit -m "feat: add ModeIndicator widget"
```

---

### Task 8: CoachPanel — 教练问答面板

**Files:**
- Create: `app/lib/widgets/coach_panel.dart`
- Create: `app/test/widgets/coach_panel_test.dart`

- [ ] **Step 1: 写 CoachPanel 测试**

```dart
// app/test/widgets/coach_panel_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_ai_app/widgets/coach_panel.dart';

void main() {
  testWidgets('shows progress bar and current question', (tester) async {
    final coachState = {
      'active': true,
      'current_question': 3,
      'answers': {
        'goal_picture': '减到70kg',
        'baseline': '现在80kg，每周跑2次',
      },
      'follow_up_count': 0,
      'started_at': '2026-06-17T10:00:00Z',
    };

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CoachPanel(coachState: coachState),
        ),
      ),
    );

    // 进度条应显示 3/6
    expect(find.text('3'), findsOneWidget);
    expect(find.text('6'), findsOneWidget);
  });

  testWidgets('shows nothing when state is null', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: CoachPanel(coachState: null),
        ),
      ),
    );

    expect(find.byType(CoachPanel), findsOneWidget);
    expect(find.text('教练模式'), findsNothing);
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/widgets/coach_panel_test.dart
```

预期：FAIL

- [ ] **Step 3: 写 CoachPanel**

```dart
// app/lib/widgets/coach_panel.dart
import 'package:flutter/material.dart';

class CoachPanel extends StatelessWidget {
  final Map<String, dynamic>? coachState;

  const CoachPanel({super.key, this.coachState});

  @override
  Widget build(BuildContext context) {
    if (coachState == null || coachState!['active'] != true) {
      return const SizedBox.shrink();
    }

    final currentQ = (coachState!['current_question'] as int?) ?? 1;
    final followUpCount = (coachState!['follow_up_count'] as int?) ?? 0;
    final totalQuestions = 6;
    final progress = (currentQ - 1) / totalQuestions;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF6366F1).withAlpha(15),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF6366F1).withAlpha(50)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // 标题行
          Row(
            children: [
              const Icon(Icons.psychology, size: 16, color: Color(0xFF6366F1)),
              const SizedBox(width: 6),
              const Text(
                '教练模式',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF6366F1),
                ),
              ),
              if (followUpCount > 0) ...[
                const SizedBox(width: 8),
                Text(
                  '(追问第$followUpCount次)',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey.shade500,
                  ),
                ),
              ],
              const Spacer(),
              Text(
                '$currentQ / $totalQuestions',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          // 进度条
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              minHeight: 4,
              backgroundColor: const Color(0xFF6366F1).withAlpha(30),
              valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF6366F1)),
            ),
          ),
          const SizedBox(height: 6),
          // 已完成问题标记
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: List.generate(totalQuestions, (i) {
              final answered = coachState!['answers'] is Map &&
                  (coachState!['answers'] as Map).containsKey(
                    ['goal_picture', 'baseline', 'resources', 'constraints', 'motivation', 'milestones'][i],
                  );
              return Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: i < currentQ - 1
                      ? (answered
                          ? const Color(0xFF10B981)
                          : const Color(0xFFF59E0B))
                      : Colors.grey.shade200,
                ),
                child: Center(
                  child: i < currentQ - 1
                      ? const Icon(Icons.check, size: 14, color: Colors.white)
                      : Text(
                          '${i + 1}',
                          style: TextStyle(
                            fontSize: 11,
                            color: i == currentQ - 1
                                ? const Color(0xFF6366F1)
                                : Colors.grey.shade500,
                            fontWeight: i == currentQ - 1
                                ? FontWeight.bold
                                : FontWeight.normal,
                          ),
                        ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4: 运行 CoachPanel 测试**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test test/widgets/coach_panel_test.dart
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/widgets/coach_panel.dart app/test/widgets/coach_panel_test.dart && git commit -m "feat: add CoachPanel widget with tests"
```

---

### Task 9: GoalCard + MilestoneTile

**Files:**
- Create: `app/lib/widgets/goal_card.dart`
- Create: `app/lib/widgets/milestone_tile.dart`

- [ ] **Step 1: 写 GoalCard**

```dart
// app/lib/widgets/goal_card.dart
import 'package:flutter/material.dart';
import '../models/goal.dart';

class GoalCard extends StatelessWidget {
  final Goal goal;
  final VoidCallback? onTap;

  const GoalCard({super.key, required this.goal, this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = Color(goal.statusColor);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 标题 + 状态标签
              Row(
                children: [
                  Expanded(
                    child: Text(
                      goal.title,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: color.withAlpha(25),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      goal.statusLabel,
                      style: TextStyle(
                        fontSize: 12,
                        color: color,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
              if (goal.description.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  goal.description,
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey.shade600,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const SizedBox(height: 10),
              // 里程碑进度
              Row(
                children: [
                  Icon(Icons.checklist, size: 14, color: Colors.grey.shade400),
                  const SizedBox(width: 4),
                  Text(
                    '${goal.completedMilestoneCount}/${goal.milestones.length} 个里程碑',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade500,
                    ),
                  ),
                  if (goal.reviveCount > 0) ...[
                    const Spacer(),
                    Icon(Icons.replay, size: 14, color: Colors.grey.shade400),
                    const SizedBox(width: 4),
                    Text(
                      '复活赛第 ${goal.reviveCount} 轮',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.orange.shade400,
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: 写 MilestoneTile**

```dart
// app/lib/widgets/milestone_tile.dart
import 'package:flutter/material.dart';

class MilestoneTile extends StatelessWidget {
  final int index;
  final Map<String, dynamic> milestone;
  final bool isDone;
  final ValueChanged<bool>? onToggle;

  const MilestoneTile({
    super.key,
    required this.index,
    required this.milestone,
    this.isDone = false,
    this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final text = milestone['text'] as String? ?? '';
    final criteria = milestone['criteria'] as String?;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDone
            ? const Color(0xFF10B981).withAlpha(15)
            : Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDone
              ? const Color(0xFF10B981).withAlpha(50)
              : Colors.grey.shade200,
        ),
      ),
      child: Row(
        children: [
          // 序号/勾选
          GestureDetector(
            onTap: onToggle != null ? () => onToggle!(!isDone) : null,
            child: Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isDone ? const Color(0xFF10B981) : Colors.white,
                border: Border.all(
                  color: isDone ? const Color(0xFF10B981) : Colors.grey.shade300,
                  width: 2,
                ),
              ),
              child: isDone
                  ? const Icon(Icons.check, size: 16, color: Colors.white)
                  : Center(
                      child: Text(
                        '${index + 1}',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade500,
                        ),
                      ),
                    ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  text,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    decoration: isDone ? TextDecoration.lineThrough : null,
                    color: isDone ? Colors.grey : null,
                  ),
                ),
                if (criteria != null && criteria.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    '通过标准: $criteria',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade500,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 3: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/widgets/goal_card.dart lib/widgets/milestone_tile.dart
```

预期：no issues found

- [ ] **Step 4: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/widgets/goal_card.dart app/lib/widgets/milestone_tile.dart && git commit -m "feat: add GoalCard and MilestoneTile widgets"
```

---

### Task 10: MemeCard

**Files:**
- Create: `app/lib/widgets/meme_card.dart`

- [ ] **Step 1: 写 MemeCard**

```dart
// app/lib/widgets/meme_card.dart
import 'package:flutter/material.dart';
import '../models/meme.dart';

class MemeCard extends StatelessWidget {
  final Meme meme;
  final VoidCallback? onKeep;
  final VoidCallback? onDiscard;

  const MemeCard({
    super.key,
    required this.meme,
    this.onKeep,
    this.onDiscard,
  });

  @override
  Widget build(BuildContext context) {
    final isKept = meme.kept;
    final isDiscarded = meme.discarded;
    final isDecided = isKept || isDiscarded;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isKept
              ? const Color(0xFF10B981).withAlpha(80)
              : isDiscarded
                  ? Colors.grey.shade300
                  : Colors.grey.shade200,
          width: isKept ? 2 : 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 标题行
            Row(
              children: [
                const Icon(Icons.local_fire_department, size: 18, color: Color(0xFFEF4444)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    meme.title,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            if (meme.summary != null && meme.summary!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                meme.summary!,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.grey.shade600,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 10),
            // 标签 + 操作区
            Row(
              children: [
                if (meme.tags != null) ...[
                  ...meme.tags!.split(',').take(3).map(
                        (tag) => Container(
                          margin: const EdgeInsets.only(right: 4),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            tag.trim(),
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                      ),
                  const Spacer(),
                ] else
                  const Spacer(),
                // 保留/删除按钮
                if (!isDecided) ...[
                  _ActionButton(
                    label: '删',
                    icon: Icons.close,
                    color: Colors.grey,
                    onTap: onDiscard,
                  ),
                  const SizedBox(width: 8),
                  _ActionButton(
                    label: '留',
                    icon: Icons.favorite,
                    color: const Color(0xFFEF4444),
                    onTap: onKeep,
                  ),
                ] else if (isKept)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withAlpha(25),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Text(
                      '已保留',
                      style: TextStyle(
                        fontSize: 12,
                        color: Color(0xFF10B981),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  )
                else
                  Text(
                    '已删除',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade400,
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  const _ActionButton({
    required this.label,
    required this.icon,
    required this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: color.withAlpha(20),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withAlpha(50)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: color,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/widgets/meme_card.dart
```

预期：no issues found

- [ ] **Step 3: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/widgets/meme_card.dart && git commit -m "feat: add MemeCard widget"
```

---

### Task 11: GoalsScreen — 任务列表页

**Files:**
- Create: `app/lib/screens/goals_screen.dart`

- [ ] **Step 1: 写 GoalsScreen**

```dart
// app/lib/screens/goals_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/goal_provider.dart';
import '../widgets/goal_card.dart';
import 'goal_detail_screen.dart';

class GoalsScreen extends ConsumerStatefulWidget {
  const GoalsScreen({super.key});

  @override
  ConsumerState<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends ConsumerState<GoalsScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(goalProvider.notifier).loadGoals());
  }

  @override
  Widget build(BuildContext context) {
    final goals = ref.watch(goalProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('任务'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(goalProvider.notifier).loadGoals(),
          ),
        ],
      ),
      body: goals.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.flag_outlined, size: 48, color: Colors.grey.shade300),
                  const SizedBox(height: 12),
                  Text(
                    '还没有任务\n去和阿玖聊聊你想做什么吧',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade500,
                    ),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              onRefresh: () => ref.read(goalProvider.notifier).loadGoals(),
              child: ListView.builder(
                padding: const EdgeInsets.only(top: 8, bottom: 80),
                itemCount: goals.length,
                itemBuilder: (context, index) {
                  final goal = goals[index];
                  return GoalCard(
                    goal: goal,
                    onTap: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => GoalDetailScreen(goalId: goal.id),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
    );
  }
}
```

- [ ] **Step 2: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/screens/goals_screen.dart
```

预期：no issues found（可能会因为 GoalDetailScreen 还没创建而报错，预期行为，Task 12 修复）

- [ ] **Step 3: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/screens/goals_screen.dart && git commit -m "feat: add GoalsScreen"
```

---

### Task 12: GoalDetailScreen — 任务详情页

**Files:**
- Create: `app/lib/screens/goal_detail_screen.dart`

- [ ] **Step 1: 写 GoalDetailScreen**

```dart
// app/lib/screens/goal_detail_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/goal.dart';
import '../providers/goal_provider.dart';
import '../widgets/milestone_tile.dart';

class GoalDetailScreen extends ConsumerStatefulWidget {
  final String goalId;

  const GoalDetailScreen({super.key, required this.goalId});

  @override
  ConsumerState<GoalDetailScreen> createState() => _GoalDetailScreenState();
}

class _GoalDetailScreenState extends ConsumerState<GoalDetailScreen> {
  Goal? _goal;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final goal = await ref.read(goalProvider.notifier).getGoalDetail(widget.goalId);
    if (mounted) {
      setState(() {
        _goal = goal;
        _loading = false;
      });
    }
  }

  Future<void> _toggleMilestone(int index) async {
    if (_goal == null) return;
    final ms = _goal!.milestones[index];
    final isDone = ms['done'] == true;
    final updated = List<Map<String, dynamic>>.from(_goal!.milestones);
    updated[index] = {...ms, 'done': !isDone};

    // 乐观更新本地状态
    setState(() {
      _goal = Goal(
        id: _goal!.id,
        conversationId: _goal!.conversationId,
        title: _goal!.title,
        description: _goal!.description,
        milestones: updated,
        status: _goal!.status,
        reviveCount: _goal!.reviveCount,
        createdAt: _goal!.createdAt,
        completedAt: _goal!.completedAt,
        checks: _goal!.checks,
      );
    });

    // 提交打卡
    await ref.read(goalProvider.notifier).addCheck(
          widget.goalId,
          status: isDone ? 'missed' : 'done',
          note: '${updated[index]['text']} ${isDone ? "取消勾选" : "完成"}',
        );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('任务详情')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final goal = _goal;
    if (goal == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('任务详情')),
        body: const Center(child: Text('任务不存在或已删除')),
      );
    }

    final color = Color(goal.statusColor);

    return Scaffold(
      appBar: AppBar(
        title: const Text('任务详情'),
        actions: [
          if (goal.status == 'active') ...[
            TextButton(
              onPressed: () => _showStatusDialog('completed'),
              child: const Text('完成'),
            ),
            TextButton(
              onPressed: () => _showStatusDialog('abandoned'),
              child: Text('放弃', style: TextStyle(color: Colors.red.shade400)),
            ),
          ],
          if (goal.status == 'abandoned')
            TextButton.icon(
              onPressed: () async {
                await ref.read(goalProvider.notifier).revive(goal.id);
                _load();
              },
              icon: const Icon(Icons.replay, size: 18),
              label: const Text('复活'),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 标题 + 状态
          Row(
            children: [
              Expanded(
                child: Text(
                  goal.title,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: color.withAlpha(25),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  goal.statusLabel,
                  style: TextStyle(color: color, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          // 描述
          if (goal.description.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              goal.description,
              style: TextStyle(fontSize: 14, color: Colors.grey.shade700),
            ),
          ],
          // 复活次数
          if (goal.reviveCount > 0) ...[
            const SizedBox(height: 8),
            Text(
              '已复活 ${goal.reviveCount} 次',
              style: TextStyle(fontSize: 13, color: Colors.orange.shade400),
            ),
          ],
          // 进度条
          const SizedBox(height: 20),
          Row(
            children: [
              const Text('进度', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(width: 8),
              Text(
                '${goal.completedMilestoneCount}/${goal.milestones.length}',
                style: TextStyle(fontSize: 14, color: Colors.grey.shade500),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: goal.progress,
              minHeight: 6,
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
          // 里程碑列表
          const SizedBox(height: 20),
          const Text('里程碑', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          ...List.generate(goal.milestones.length, (i) {
            final ms = goal.milestones[i];
            return MilestoneTile(
              index: i,
              milestone: ms,
              isDone: ms['done'] == true,
              onToggle: goal.status == 'active' ? (_) => _toggleMilestone(i) : null,
            );
          }),
          // 打卡历史
          if (goal.checks.isNotEmpty) ...[
            const SizedBox(height: 24),
            const Text('打卡记录', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            ...goal.checks.take(10).map((check) => ListTile(
                  dense: true,
                  leading: Icon(
                    check.status == 'done'
                        ? Icons.check_circle
                        : check.status == 'missed'
                            ? Icons.cancel
                            : Icons.skip_next,
                    size: 20,
                    color: check.status == 'done'
                        ? const Color(0xFF10B981)
                        : Colors.grey,
                  ),
                  title: Text(
                    check.note ?? check.status,
                    style: const TextStyle(fontSize: 13),
                  ),
                  subtitle: Text(
                    '${check.checkTime.month}/${check.checkTime.day} ${check.checkTime.hour}:${check.checkTime.minute.toString().padLeft(2, '0')}',
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
                  ),
                )),
          ],
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  void _showStatusDialog(String newStatus) {
    final label = newStatus == 'completed' ? '完成' : '放弃';
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('确认$label'),
        content: Text('确定要$label这个任务吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await ref.read(goalProvider.notifier).updateStatus(widget.goalId, newStatus);
              _load();
            },
            child: Text(label),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/screens/goal_detail_screen.dart lib/screens/goals_screen.dart
```

预期：no issues found

- [ ] **Step 3: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/screens/goal_detail_screen.dart && git commit -m "feat: add GoalDetailScreen with milestone tracking"
```

---

### Task 13: MemesScreen — 梗列表页

**Files:**
- Create: `app/lib/screens/memes_screen.dart`

- [ ] **Step 1: 写 MemesScreen**

```dart
// app/lib/screens/memes_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/meme_provider.dart';
import '../widgets/meme_card.dart';

class MemesScreen extends ConsumerStatefulWidget {
  const MemesScreen({super.key});

  @override
  ConsumerState<MemesScreen> createState() => _MemesScreenState();
}

class _MemesScreenState extends ConsumerState<MemesScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(memeProvider.notifier).loadTodayMemes());
  }

  @override
  Widget build(BuildContext context) {
    final memes = ref.watch(memeProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('今日梗'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(memeProvider.notifier).loadTodayMemes(),
          ),
        ],
      ),
      body: memes.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.local_fire_department, size: 48, color: Colors.grey.shade300),
                  const SizedBox(height: 12),
                  Text(
                    '今日无梗\n阿玖 22:00 帮你捞新的',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade500,
                    ),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              onRefresh: () => ref.read(memeProvider.notifier).loadTodayMemes(),
              child: ListView.builder(
                padding: const EdgeInsets.only(top: 8, bottom: 80),
                itemCount: memes.length,
                itemBuilder: (context, index) {
                  final meme = memes[index];
                  return MemeCard(
                    meme: meme,
                    onKeep: () => ref.read(memeProvider.notifier).keep(meme.id),
                    onDiscard: () => ref.read(memeProvider.notifier).discard(meme.id),
                  );
                },
              ),
            ),
    );
  }
}
```

- [ ] **Step 2: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/screens/memes_screen.dart
```

预期：no issues found

- [ ] **Step 3: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/screens/memes_screen.dart && git commit -m "feat: add MemesScreen"
```

---

### Task 14: ChatScreen 增强 — 集成 CoachPanel + ModeIndicator

**Files:**
- Modify: `app/lib/screens/chat_screen.dart`

- [ ] **Step 1: 在 ChatScreen 头部添加 ModeIndicator**

修改 `chat_screen.dart`，在现有头部区域（阿玖 + 在线状态那行上面或旁边）添加 ModeIndicator：

在原 `_buildHeader` 或相应的 `Column` children 中，在消息列表上方、输入框上方插入：

```dart
  // 读取当前模式 — 在 build 方法中：
  final chatNotifier = ref.watch(chatProvider.notifier);
  final currentMode = chatNotifier.currentMode;
  final coachState = chatNotifier.coachState;
```

然后在 Scaffold body 的 Column children 中，在 ListView 和 MessageInput 之间插入 CoachPanel：

```dart
  // 在 Expanded(ListView) 和 MessageInput 之间：
  CoachPanel(coachState: coachState),
  // ...然后才是 MessageInput
```

- [ ] **Step 2: 在头部添加 ModeIndicator**

在 AppBar 或头部的 Row 中加入 ModeIndicator：

```dart
  // 在头部 Row 的 children 中加入：
  const SizedBox(width: 8),
  ModeIndicator(mode: currentMode),
```

- [ ] **Step 3: 添加必要的 import**

```dart
  import '../widgets/mode_indicator.dart';
  import '../widgets/coach_panel.dart';
```

- [ ] **Step 4: 验证编译**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze lib/screens/chat_screen.dart
```

预期：no issues found

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add app/lib/screens/chat_screen.dart && git commit -m "feat: integrate CoachPanel and ModeIndicator into ChatScreen"
```

---

### Task 15: 集成测试 + 端到端验证

**Files:**
- Modify: 无（验证阶段）

- [ ] **Step 1: 确认后端运行**

```bash
cd "D:\Claude code\个人API应用\backend" && curl http://localhost:8000/health
```

预期：`{"status":"ok","version":"0.1.0"}`

如果后端未运行，启动：
```bash
cd "D:\Claude code\个人API应用\backend" && docker compose up -d db && .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] **Step 2: 运行所有 Flutter 测试**

```bash
cd "D:\Claude code\个人API应用\app" && flutter test
```

预期：全部 PASS

- [ ] **Step 3: 运行 Flutter analyze**

```bash
cd "D:\Claude code\个人API应用\app" && flutter analyze
```

预期：no issues found

- [ ] **Step 4: 运行后端测试确认未破坏**

```bash
cd "D:\Claude code\个人API应用\backend" && $env:APP_ENV='development'; $env:DEVICE_SECRET='local-dev-secret'; $env:PYTHONPATH='backend'; $env:DATABASE_URL='postgresql+asyncpg://aitest:aitest@localhost:5432/aitest'; $env:TEST_DATABASE_URL='postgresql+asyncpg://aitest:aitest@localhost:5432/aitest'; .venv\Scripts\python.exe -m pytest tests -q
```

预期：51 passed（或更多）

- [ ] **Step 5: 提交**

```bash
cd "D:\Claude code\个人API应用" && git add -A && git commit -m "chore: final V1.0 alpha integration checks"
```

---

## 实施顺序

```
Task 1 (Models) → Task 2 (ApiClient) → Task 3,4,5 (Providers)  (并行)
                                       ↓
                     Task 6 (MainScaffold) → Task 7-10 (Widgets)  (并行)
                                              ↓
                               Task 11,12,13 (Screens) → Task 14 (ChatScreen) → Task 15 (验证)
```

**可并行组：**
- Task 7 (ModeIndicator), Task 8 (CoachPanel), Task 9 (GoalCard), Task 10 (MemeCard) 可同时做
- Task 11 (GoalsScreen), Task 12 (GoalDetailScreen), Task 13 (MemesScreen) 可同时做

## 预期最终效果

- 底部 4 Tab：阿玖 / 任务 / 梗 / 设置
- 聊天页：顶部模式标识，教练模式下显示问答面板
- 任务页：列表 + 详情（里程碑勾选、打卡记录）
- 梗页：今日梗列表，保留/删除
- 所有页面调用现有后端 API，无需后端改动

## 已知未覆盖

- 聊天页 ModeIndicator / CoachPanel 的具体 layout 集成（需要看实际效果微调，留给 GPT 做 UI 精调）
- 设置页的模式信息展示（轻量改动，可选）
- 管家模式主动推送 UI（需要后台定时任务 + 通知通道，alpha 不入）
- 教练流程的动画效果（交 GPT 设计）
