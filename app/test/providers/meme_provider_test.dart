import 'package:flutter_test/flutter_test.dart';
import 'package:ai_assistant/providers/meme_provider.dart';

void main() {
  test('MemeNotifier.loading creates empty state', () {
    final notifier = MemeNotifier.loading();
    expect(notifier.state, isEmpty);
  });

  test('MemeNotifier.error creates empty state', () {
    final notifier = MemeNotifier.error(Exception('test error'));
    expect(notifier.state, isEmpty);
  });
}
