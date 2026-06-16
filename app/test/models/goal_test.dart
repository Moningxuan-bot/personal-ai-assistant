import 'package:flutter_test/flutter_test.dart';
import 'package:ai_assistant/models/goal.dart';

void main() {
  group('Goal', () {
    final sampleJson = {
      'id': '550e8400-e29b-41d4-a716-446655440000',
      'conversation_id': '660e8400-e29b-41d4-a716-446655440001',
      'title': '减重到70kg',
      'description': '通过饮食和运动在3个月内减重10kg',
      'milestones': [
        {'text': '第一周：每天跑步30分钟', 'criteria': '连续7天完成'},
        {'text': '第一个月：减重3kg', 'criteria': '体重秤显示<77kg'},
      ],
      'status': 'active',
      'revive_count': 2,
      'created_at': '2026-06-17T10:00:00Z',
      'completed_at': null,
    };

    test('fromJson parses all fields', () {
      final goal = Goal.fromJson(sampleJson);
      expect(goal.id, '550e8400-e29b-41d4-a716-446655440000');
      expect(goal.title, '减重到70kg');
      expect(goal.status, 'active');
      expect(goal.reviveCount, 2);
      expect(goal.milestones.length, 2);
      expect(goal.completedAt, isNull);
    });

    test('fromJson parses completed_at when present', () {
      final jsonWithCompleted = {
        ...sampleJson,
        'completed_at': '2026-09-17T10:00:00Z',
      };
      final goal = Goal.fromJson(jsonWithCompleted);
      expect(goal.completedAt, isNotNull);
    });

    test('statusLabel returns Chinese labels', () {
      expect(Goal.fromJson({...sampleJson, 'status': 'active'}).statusLabel, '进行中');
      expect(Goal.fromJson({...sampleJson, 'status': 'paused'}).statusLabel, '已暂停');
      expect(Goal.fromJson({...sampleJson, 'status': 'completed'}).statusLabel, '已完成');
      expect(Goal.fromJson({...sampleJson, 'status': 'abandoned'}).statusLabel, '已放弃');
    });

    test('statusColor returns correct colors', () {
      expect(Goal.fromJson({...sampleJson, 'status': 'active'}).statusColor, isNotNull);
    });
  });

  group('GoalCheck', () {
    test('fromJson parses all fields', () {
      final json = {
        'id': '770e8400-e29b-41d4-a716-446655440002',
        'goal_id': '550e8400-e29b-41d4-a716-446655440000',
        'check_time': '2026-06-18T08:00:00Z',
        'status': 'done',
        'note': '完成5km跑步',
      };
      final check = GoalCheck.fromJson(json);
      expect(check.status, 'done');
      expect(check.note, '完成5km跑步');
    });
  });
}
