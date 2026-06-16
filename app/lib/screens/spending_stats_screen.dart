// app/lib/screens/spending_stats_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/spending_provider.dart';
import '../widgets/spending_card.dart';

class SpendingStatsScreen extends ConsumerStatefulWidget {
  const SpendingStatsScreen({super.key});
  @override
  ConsumerState<SpendingStatsScreen> createState() => _SpendingStatsScreenState();
}

class _SpendingStatsScreenState extends ConsumerState<SpendingStatsScreen> {
  Map<String, dynamic>? _stats;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    await ref.read(spendingProvider.notifier).load();
    final s = await ref.read(spendingProvider.notifier).stats();
    if (mounted) setState(() => _stats = s);
  }

  @override
  Widget build(BuildContext context) {
    final spendings = ref.watch(spendingProvider);
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(title: const Text('消费记录', style: TextStyle(color: AppTheme.textPrimary))),
      body: _stats == null
        ? const Center(child: CircularProgressIndicator())
        : ListView(padding: const EdgeInsets.all(16), children: [
            _infoCard('本月总消费', '¥${(_stats!['total'] as num).toStringAsFixed(0)}'),
            const SizedBox(height:8),
            _infoCard('阿玖点评', _stats!['ajiu_comment'] ?? ''),
            const SizedBox(height:16),
            const Text('分类明细', style: TextStyle(fontSize:15, fontWeight:FontWeight.w600)),
            const SizedBox(height:8),
            ...(_stats!['by_category'] as Map<String,dynamic>).entries.map((e) =>
              _catRow(e.key, (e.value as num).toDouble())),
            const SizedBox(height:20),
            const Text('最近记录', style: TextStyle(fontSize:15, fontWeight:FontWeight.w600)),
            const SizedBox(height:8),
            ...spendings.map((s) => SpendingCard(spending: s)),
          ]),
    );
  }
  );

  Widget _infoCard(String title, String content) => Container(
    width: double.infinity, padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontSize:11, color:AppTheme.textSecondary)),
      const SizedBox(height:4),
      Text(content, style: const TextStyle(fontSize:15, color:AppTheme.textPrimary)),
    ]));

  Widget _catRow(String cat, double amt) => Padding(
    padding: const EdgeInsets.symmetric(vertical:6),
    child: Row(children: [
      Expanded(child: Text(cat, style: const TextStyle(fontSize:13, color:AppTheme.textPrimary))),
      Text('¥${amt.toStringAsFixed(0)}',
          style: const TextStyle(fontSize:13, fontWeight:FontWeight.w600, color:AppTheme.textPrimary)),
    ]));
}
