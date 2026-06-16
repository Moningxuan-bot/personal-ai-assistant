import 'package:flutter/material.dart';
import '../core/theme.dart';

class MilestoneTile extends StatelessWidget {
  final int index;
  final Map<String, dynamic> milestone;
  final bool isDone;
  final ValueChanged<bool?>? onToggle;

  const MilestoneTile({
    super.key,
    required this.index,
    required this.milestone,
    required this.isDone,
    this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final text = (milestone['text'] ?? milestone['title'] ?? '里程碑 ${index + 1}').toString();
    final criteria = milestone['criteria']?.toString();

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Checkbox(value: isDone, onChanged: onToggle),
          const SizedBox(width: 4),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  text,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    decoration: isDone ? TextDecoration.lineThrough : null,
                    color: isDone ? AppTheme.textSecondary : AppTheme.textPrimary,
                  ),
                ),
                if (criteria != null && criteria.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    criteria,
                    style: const TextStyle(
                      fontSize: 12,
                      height: 1.35,
                      color: AppTheme.textSecondary,
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
