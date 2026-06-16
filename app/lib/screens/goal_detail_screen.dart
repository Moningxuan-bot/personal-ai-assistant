import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
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
    if (!mounted) return;
    setState(() {
      _goal = goal;
      _loading = false;
    });
  }

  Future<void> _toggleMilestone(int index) async {
    final goal = _goal;
    if (goal == null) return;

    final milestone = goal.milestones[index];
    final isDone = milestone['done'] == true;
    final updated = List<Map<String, dynamic>>.from(goal.milestones);
    updated[index] = {...milestone, 'done': !isDone};

    setState(() {
      _goal = goal.copyWith(milestones: updated);
    });

    await ref.read(goalProvider.notifier).addCheck(
          widget.goalId,
          status: isDone ? 'missed' : 'done',
          note: '${updated[index]['text'] ?? updated[index]['title'] ?? "里程碑"} '
              '${isDone ? "取消勾选" : "完成"}',
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
      backgroundColor: AppTheme.background,
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
                await _load();
              },
              icon: const Icon(Icons.replay, size: 18),
              label: const Text('复活'),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    goal.title,
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: color.withAlpha(24),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    goal.statusLabel,
                    style: TextStyle(color: color, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            if (goal.description.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                goal.description,
                style: const TextStyle(
                  fontSize: 14,
                  height: 1.45,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
            if (goal.reviveCount > 0) ...[
              const SizedBox(height: 8),
              Text(
                '已复活 ${goal.reviveCount} 次',
                style: TextStyle(fontSize: 13, color: Colors.orange.shade700),
              ),
            ],
            const SizedBox(height: 20),
            Row(
              children: [
                const Text('进度', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(width: 8),
                Text(
                  '${goal.completedMilestoneCount}/${goal.milestones.length}',
                  style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
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
            const SizedBox(height: 20),
            const Text('里程碑', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (goal.milestones.isEmpty)
              const Text('这个任务还没有拆里程碑。', style: TextStyle(color: AppTheme.textSecondary))
            else
              ...List.generate(goal.milestones.length, (index) {
                final milestone = goal.milestones[index];
                return MilestoneTile(
                  index: index,
                  milestone: milestone,
                  isDone: milestone['done'] == true,
                  onToggle: goal.status == 'active' ? (_) => _toggleMilestone(index) : null,
                );
              }),
            if (goal.checks.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text('打卡记录', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              ...goal.checks.take(10).map((check) {
                return ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    check.status == 'done' ? Icons.check_circle : Icons.radio_button_unchecked,
                    color: check.status == 'done' ? const Color(0xFF10B981) : AppTheme.textSecondary,
                  ),
                  title: Text(check.note ?? check.status, style: const TextStyle(fontSize: 13)),
                  subtitle: Text(
                    '${check.checkTime.month}/${check.checkTime.day} '
                    '${check.checkTime.hour}:${check.checkTime.minute.toString().padLeft(2, '0')}',
                    style: const TextStyle(fontSize: 11),
                  ),
                );
              }),
            ],
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  void _showStatusDialog(String newStatus) {
    final label = newStatus == 'completed' ? '完成' : '放弃';
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('确认$label'),
        content: Text('确定要$label这个任务吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              await ref.read(goalProvider.notifier).updateStatus(widget.goalId, newStatus);
              await _load();
            },
            child: Text(label),
          ),
        ],
      ),
    );
  }
}
