class Goal {
  final String id;
  final String conversationId;
  final String title;
  final String description;
  final List<Map<String, dynamic>> milestones;
  final String status;
  final int reviveCount;
  final DateTime createdAt;
  final DateTime? completedAt;
  final List<GoalCheck> checks;

  const Goal({
    required this.id,
    required this.conversationId,
    required this.title,
    required this.description,
    this.milestones = const [],
    this.status = 'active',
    this.reviveCount = 0,
    required this.createdAt,
    this.completedAt,
    this.checks = const [],
  });

  factory Goal.fromJson(Map<String, dynamic> json) {
    return Goal(
      id: json['id'] as String,
      conversationId: json['conversation_id'] as String,
      title: json['title'] as String,
      description: (json['description'] as String?) ?? '',
      milestones: (json['milestones'] as List<dynamic>?)
              ?.map((item) => Map<String, dynamic>.from(item as Map))
              .toList() ??
          [],
      status: (json['status'] as String?) ?? 'active',
      reviveCount: (json['revive_count'] as int?) ?? 0,
      createdAt: DateTime.parse(json['created_at'] as String),
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
      checks: (json['checks'] as List<dynamic>?)
              ?.map((item) => GoalCheck.fromJson(Map<String, dynamic>.from(item as Map)))
              .toList() ??
          [],
    );
  }

  String get statusLabel {
    switch (status) {
      case 'active':
        return '进行中';
      case 'paused':
        return '已暂停';
      case 'completed':
        return '已完成';
      case 'abandoned':
        return '已放弃';
      default:
        return status;
    }
  }

  int get statusColor {
    switch (status) {
      case 'active':
        return 0xFF6366F1;
      case 'paused':
        return 0xFFF59E0B;
      case 'completed':
        return 0xFF10B981;
      case 'abandoned':
        return 0xFF9CA3AF;
      default:
        return 0xFF9CA3AF;
    }
  }

  int get completedMilestoneCount =>
      milestones.where((item) => item['done'] == true).length;

  double get progress =>
      milestones.isEmpty ? 0.0 : completedMilestoneCount / milestones.length;

  Goal copyWith({
    String? id,
    String? conversationId,
    String? title,
    String? description,
    List<Map<String, dynamic>>? milestones,
    String? status,
    int? reviveCount,
    DateTime? createdAt,
    DateTime? completedAt,
    List<GoalCheck>? checks,
  }) {
    return Goal(
      id: id ?? this.id,
      conversationId: conversationId ?? this.conversationId,
      title: title ?? this.title,
      description: description ?? this.description,
      milestones: milestones ?? this.milestones,
      status: status ?? this.status,
      reviveCount: reviveCount ?? this.reviveCount,
      createdAt: createdAt ?? this.createdAt,
      completedAt: completedAt ?? this.completedAt,
      checks: checks ?? this.checks,
    );
  }
}

class GoalCheck {
  final String id;
  final String goalId;
  final DateTime checkTime;
  final String status;
  final String? note;

  const GoalCheck({
    required this.id,
    required this.goalId,
    required this.checkTime,
    this.status = 'pending',
    this.note,
  });

  factory GoalCheck.fromJson(Map<String, dynamic> json) {
    return GoalCheck(
      id: json['id'] as String,
      goalId: json['goal_id'] as String,
      checkTime: DateTime.parse(json['check_time'] as String),
      status: (json['status'] as String?) ?? 'pending',
      note: json['note'] as String?,
    );
  }
}
