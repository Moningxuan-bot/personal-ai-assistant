// app/lib/providers/spending_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/spending.dart';
import 'chat_provider.dart';

final spendingProvider = StateNotifierProvider<SpendingNotifier, List<Spending>>((ref) {
  final apiAsync = ref.watch(apiClientProvider);
  return apiAsync.when(
    data: (api) => SpendingNotifier(api),
    loading: () => SpendingNotifier.loading(),
    error: (e, _) => SpendingNotifier.error(e),
  );
});

class SpendingNotifier extends StateNotifier<List<Spending>> {
  final ApiClient? _api;
  bool _submitting = false;
  bool get isSubmitting => _submitting;

  SpendingNotifier(ApiClient api) : _api = api, super([]);
  SpendingNotifier.loading() : _api = null, super([]);
  SpendingNotifier.error(Object e) : _api = null, super([]);

  Future<Spending?> submit({
    required double amount, required String category,
    String? note, String? conversationId,
  }) async {
    if (_submitting || _api == null) return null;
    _submitting = true;
    try {
      final s = await _api!.createSpending(
          amount: amount, category: category, note: note, conversationId: conversationId);
      state = [s, ...state];
      return s;
    } finally { _submitting = false; }
  }

  Future<void> load({int page = 1, String? category}) async {
    if (_api == null) return;
    state = await _api!.listSpendings(page: page, category: category);
  }

  Future<Map<String, dynamic>?> stats() async {
    if (_api == null) return null;
    return await _api!.getSpendingStats();
  }
}
