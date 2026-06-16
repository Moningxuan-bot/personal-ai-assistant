import 'package:flutter/material.dart';
import '../core/theme.dart';
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
    final keptColor = meme.kept ? const Color(0xFF10B981) : AppTheme.border;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: keptColor, width: meme.kept ? 1.5 : 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  meme.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              _SourceChip(source: meme.source),
            ],
          ),
          if (meme.summary != null && meme.summary!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              meme.summary!,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 13,
                height: 1.35,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
          if (meme.tags != null && meme.tags!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: meme.tags!
                  .split(',')
                  .where((tag) => tag.trim().isNotEmpty)
                  .map((tag) => _TagChip(label: tag.trim()))
                  .toList(),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onDiscard,
                  icon: const Icon(Icons.close, size: 16),
                  label: const Text('丢掉'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFFEF4444),
                    side: const BorderSide(color: Color(0x33EF4444)),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  onPressed: meme.kept ? null : onKeep,
                  icon: Icon(meme.kept ? Icons.check : Icons.bookmark_add_outlined, size: 16),
                  label: Text(meme.kept ? '已保留' : '保留'),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SourceChip extends StatelessWidget {
  final String source;

  const _SourceChip({required this.source});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFFF6B6B).withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        source,
        style: const TextStyle(
          fontSize: 11,
          color: Color(0xFFFF6B6B),
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _TagChip extends StatelessWidget {
  final String label;

  const _TagChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
      ),
    );
  }
}
