import 'package:flutter/material.dart';
import '../core/theme.dart';

class CoachPanel extends StatelessWidget {
  final Map<String, dynamic>? coachState;

  const CoachPanel({super.key, this.coachState});

  @override
  Widget build(BuildContext context) {
    final state = coachState;
    if (state == null || state['active'] != true) {
      return const SizedBox.shrink();
    }

    final currentStep = (state['current_step'] as int?) ?? 0;
    final pendingPlan = state['pending_plan'];
    final question = (state['current_question'] as String?) ??
        (pendingPlan != null ? '计划已经整理好了，要不要就按这个来？' : '说清楚点，不然我怎么帮你？');

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF2563EB).withAlpha(56)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Icon(Icons.flag_outlined, size: 16, color: Color(0xFF2563EB)),
              const SizedBox(width: 6),
              const Text(
                '教练模式',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
              ),
              const Spacer(),
              Text(
                '${currentStep.clamp(0, 6)}/6',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _StepDots(currentStep: currentStep),
          const SizedBox(height: 10),
          Text(
            question,
            style: const TextStyle(
              fontSize: 13,
              height: 1.45,
              color: AppTheme.textPrimary,
            ),
          ),
          if (pendingPlan != null) ...[
            const SizedBox(height: 10),
            _PlanPreview(plan: pendingPlan),
          ],
        ],
      ),
    );
  }
}

class _StepDots extends StatelessWidget {
  final int currentStep;

  const _StepDots({required this.currentStep});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(6, (index) {
        final done = index < currentStep;
        return Expanded(
          child: Container(
            height: 5,
            margin: EdgeInsets.only(right: index == 5 ? 0 : 5),
            decoration: BoxDecoration(
              color: done ? const Color(0xFF2563EB) : Colors.grey.shade200,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
        );
      }),
    );
  }
}

class _PlanPreview extends StatelessWidget {
  final Object plan;

  const _PlanPreview({required this.plan});

  @override
  Widget build(BuildContext context) {
    final text = plan is Map ? (plan as Map)['title']?.toString() ?? plan.toString() : plan.toString();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF2563EB).withAlpha(12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontSize: 12, height: 1.35),
      ),
    );
  }
}
