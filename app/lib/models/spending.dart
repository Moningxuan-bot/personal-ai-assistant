// app/lib/models/spending.dart
class Spending {
  final String id;
  final String? conversationId;
  final double amount;
  final String category;
  final String? note;
  final String reaction;
  final String? chatReaction;
  final bool chatDelivered;
  final DateTime createdAt;

  const Spending({
    required this.id, this.conversationId, required this.amount,
    required this.category, this.note, required this.reaction,
    this.chatReaction, required this.chatDelivered, required this.createdAt,
  });

  factory Spending.fromJson(Map<String, dynamic> json) => Spending(
    id: json['id'], conversationId: json['conversation_id'],
    amount: (json['amount'] as num).toDouble(), category: json['category'],
    note: json['note'], reaction: json['reaction'],
    chatReaction: json['chat_reaction'], chatDelivered: json['chat_delivered'] ?? false,
    createdAt: DateTime.parse(json['created_at']),
  );
}
