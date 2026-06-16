import 'package:flutter/material.dart';

class ModeIndicator extends StatelessWidget {
  final String mode;

  const ModeIndicator({super.key, required this.mode});

  String get _label {
    switch (mode) {
      case 'coach':
        return '教练';
      case 'butler':
        return '管家';
      case 'casual':
      default:
        return '闲聊';
    }
  }

  Color get _color {
    switch (mode) {
      case 'coach':
        return const Color(0xFF2563EB);
      case 'butler':
        return const Color(0xFF059669);
      case 'casual':
      default:
        return const Color(0xFF7C3AED);
    }
  }

  IconData get _icon {
    switch (mode) {
      case 'coach':
        return Icons.flag_outlined;
      case 'butler':
        return Icons.event_available_outlined;
      case 'casual':
      default:
        return Icons.forum_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: _color.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _color.withAlpha(54)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icon, size: 14, color: _color),
          const SizedBox(width: 4),
          Text(
            _label,
            style: TextStyle(
              color: _color,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
