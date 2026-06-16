import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_assistant/widgets/coach_panel.dart';

void main() {
  testWidgets('CoachPanel hides when inactive', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: CoachPanel(coachState: {'active': false})),
      ),
    );

    expect(find.text('教练模式'), findsNothing);
  });

  testWidgets('CoachPanel renders active state', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: CoachPanel(
            coachState: {
              'active': true,
              'current_step': 2,
              'current_question': '现在什么水平？',
            },
          ),
        ),
      ),
    );

    expect(find.text('教练模式'), findsOneWidget);
    expect(find.text('现在什么水平？'), findsOneWidget);
    expect(find.text('2/6'), findsOneWidget);
  });
}
