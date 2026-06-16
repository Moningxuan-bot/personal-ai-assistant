import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../core/api_client.dart';
import '../models/chat_message.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  // During dev, use localhost. In prod, configure via settings.
  return ApiClient(baseUrl: 'http://10.0.2.2:8000'); // Android emulator
});

final chatProvider =
    StateNotifierProvider<ChatNotifier, List<ChatMessage>>((ref) {
  return ChatNotifier(ref.watch(apiClientProvider));
});

class ChatNotifier extends StateNotifier<List<ChatMessage>> {
  final ApiClient _api;
  final _uuid = const Uuid();
  String? _conversationId;

  ChatNotifier(this._api) : super([]);

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    // Add user message
    final userMsg = ChatMessage(
      id: _uuid.v4(),
      role: 'user',
      content: text,
      createdAt: DateTime.now(),
    );
    state = [...state, userMsg];

    // Add placeholder for assistant
    final assistantId = _uuid.v4();
    final assistantMsg = ChatMessage(
      id: assistantId,
      role: 'assistant',
      content: '',
      createdAt: DateTime.now(),
      isStreaming: true,
    );
    state = [...state, assistantMsg];

    try {
      final buffer = StringBuffer();
      final stream = _api.chatStream(text, _conversationId);

      await for (final chunk in stream) {
        buffer.write(chunk);
        state = state.map((m) {
          if (m.id == assistantId) {
            return m.copyWith(content: buffer.toString());
          }
          return m;
        }).toList();
      }

      // Mark streaming complete
      state = state.map((m) {
        if (m.id == assistantId) {
          return m.copyWith(isStreaming: false);
        }
        return m;
      }).toList();
    } catch (e) {
      state = state.map((m) {
        if (m.id == assistantId) {
          return m.copyWith(content: '错误: $e', isStreaming: false);
        }
        return m;
      }).toList();
    }
  }

  void clearChat() {
    state = [];
    _conversationId = null;
  }
}
