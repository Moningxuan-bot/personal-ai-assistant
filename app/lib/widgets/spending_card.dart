// app/lib/widgets/spending_card.dart
import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../models/spending.dart';

class SpendingCard extends StatelessWidget {
  final Spending spending;
  const SpendingCard({super.key, required this.spending});

  static const _icons = {'餐饮':'🍜','交通':'🚇','烟酒':'🚬','购物':'🛒','娱乐':'🎮','其他':'💰'};

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    child: Container(
      decoration: BoxDecoration(color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14), border: Border.all(color: AppTheme.border)),
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(_icons[spending.category] ?? '💰', style: const TextStyle(fontSize: 20)),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(spending.category, style: const TextStyle(fontSize:13, fontWeight:FontWeight.w600, color:AppTheme.textPrimary)),
            if (spending.note != null && spending.note!.isNotEmpty)
              Text(spending.note!, style: const TextStyle(fontSize:11, color:AppTheme.textSecondary), maxLines:1, overflow:TextOverflow.ellipsis),
          ])),
          Text('¥${spending.amount.toStringAsFixed(2)}',
              style: const TextStyle(fontSize:16, fontWeight:FontWeight.w700, color:AppTheme.textPrimary)),
        ]),
        const SizedBox(height: 8),
        Container(padding: const EdgeInsets.symmetric(horizontal:8, vertical:6),
          decoration: BoxDecoration(color: AppTheme.primaryGradientStart.withOpacity(0.08), borderRadius: BorderRadius.circular(8)),
          child: Text(spending.reaction, style: const TextStyle(fontSize:12, color:AppTheme.textSecondary, fontStyle:FontStyle.italic))),
      ]),
    ),
  );
}
