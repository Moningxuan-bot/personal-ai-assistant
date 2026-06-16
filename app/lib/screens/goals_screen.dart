import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
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
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('任务', style: TextStyle(color: AppTheme.textPrimary)),
        actions: [
          IconButton(
            tooltip: '刷新',
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
                    style: TextStyle(fontSize: 14, color: Colors.grey.shade500),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              onRefresh: () => ref.read(goalProvider.notifier).loadGoals(),
              child: ListView.builder(
                padding: const EdgeInsets.only(top: 8, bottom: 88),
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
