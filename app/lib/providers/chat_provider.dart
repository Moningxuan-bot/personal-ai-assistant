import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';
import '../core/api_client.dart';
import '../models/chat_message.dart';

const _defaultDevUrl = 'http://10.0.2.2:8000'; // Android emulator

final apiClientProvider = FutureProvider<ApiClient>((ref) async {
  final storage = const FlutterSecureStorage();
  final baseUrl = await storage.read(key: 'server_url') ?? _defaultDevUrl;
  return ApiClient(baseUrl: baseUrl);
});

final chatProvider =
    StateNotifierProvider<ChatNotifier, List<ChatMessage>>((ref) {
  final apiClientAsync = ref.watch(apiClientProvider);
  return ChatNotifier(
    apiClientAsync.valueOrNull ?? ApiClient(baseUrl: _defaultDevUrl),
  );
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

      await for (final event in stream) {
        switch (event.type) {
          case 'meta':
            if (event.conversationId != null) {
              _conversationId = event.conversationId;
            }
            break;
          case 'delta':
            if (event.content != null) {
              buffer.write(event.content);
              state = state.map((m) {
                if (m.id == assistantId) {
                  return m.copyWith(content: buffer.toString());
                }
                return m;
              }).toList();
            }
            break;
          case 'done':
            state = state.map((m) {
              if (m.id == assistantId) {
                return m.copyWith(isStreaming: false);
              }
              return m;
            }).toList();
            break;
          case 'error':
            state = state.map((m) {
              if (m.id == assistantId) {
                return m.copyWith(
                  content: '错误: ${event.message ?? "未知错误"}',
                  isStreaming: false,
                );
              }
              return m;
            }).toList();
            break;
        }
      }
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
