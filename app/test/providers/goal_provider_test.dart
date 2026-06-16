import 'package:flutter_test/flutter_test.dart';
import 'package:ai_assistant/providers/goal_provider.dart';

void main() {
  test('GoalNotifier.loading creates empty state', () {
    final notifier = GoalNotifier.loading();
    expect(notifier.state, isEmpty);
  });

  test('GoalNotifier.error creates empty state', () {
    final notifier = GoalNotifier.error(Exception('test error'));
    expect(notifier.state, isEmpty);
  });
}
