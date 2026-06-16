import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/goal.dart';
import 'chat_provider.dart';

final goalProvider = StateNotifierProvider<GoalNotifier, List<Goal>>((ref) {
  final apiClientAsync = ref.watch(apiClientProvider);
  return apiClientAsync.when(
    data: (api) => GoalNotifier(api),
    loading: () => GoalNotifier.loading(),
    error: (error, _) => GoalNotifier.error(error),
  );
});

class GoalNotifier extends StateNotifier<List<Goal>> {
  final ApiClient? _api;

  GoalNotifier(this._api) : super([]);

  GoalNotifier.loading()
      : _api = null,
        super([]);

  GoalNotifier.error(Object error)
      : _api = null,
        super([]);

  Future<void> loadGoals() async {
    if (_api == null) return;
    try {
      final data = await _api!.getGoals();
      state = data.map(Goal.fromJson).toList();
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

  Future<void> addCheck(
    String goalId, {
    String status = 'done',
    String? note,
  }) async {
    if (_api == null) return;
    try {
      await _api!.addGoalCheck(goalId, status: status, note: note);
      await loadGoals();
    } catch (_) {}
  }

  List<Goal> get activeGoals =>
      state.where((goal) => goal.status == 'active').toList();

  List<Goal> get completedGoals =>
      state.where((goal) => goal.status == 'completed').toList();
}
