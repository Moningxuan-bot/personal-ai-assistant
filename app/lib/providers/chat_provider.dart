import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';
import '../core/api_client.dart';
import '../models/chat_message.dart';

const _defaultDevUrl = 'http://localhost:8000';

final apiClientProvider = FutureProvider<ApiClient>((ref) async {
  final storage = const FlutterSecureStorage();
  final baseUrl = await storage.read(key: 'server_url') ?? _defaultDevUrl;
  return ApiClient(baseUrl: baseUrl);
});

final chatProvider =
    StateNotifierProvider<ChatNotifier, List<ChatMessage>>((ref) {
  final apiClientAsync = ref.watch(apiClientProvider);
  return apiClientAsync.when(
    data: (api) => ChatNotifier(api),
    loading: () => ChatNotifier.loading(),
    error: (e, _) => ChatNotifier.error(e),
  );
});

class ChatNotifier extends StateNotifier<List<ChatMessage>> {
  final ApiClient? _api;
  final _uuid = const Uuid();
  String? _conversationId;
  String _currentMode = 'casual';
  Map<String, dynamic>? _coachState;
  String? _coachAction;

  /// Public getter so other providers can read the current conversation ID.
  String? get conversationId => _conversationId;
  String get currentMode => _currentMode;
  Map<String, dynamic>? get coachState => _coachState;
  String? get coachAction => _coachAction;

  /// Normal constructor with a real API client.
  ChatNotifier(ApiClient api)
      : _api = api,
        super([]);

  /// Loading state — config not yet loaded, API client not ready.
  ChatNotifier.loading()
      : _api = null,
        super([]);

  /// Error state — config failed to load.
  ChatNotifier.error(Object error)
      : _api = null,
        super([]);

  bool _isSending = false;

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    if (_isSending) return;
    if (_api == null) return; // Not ready yet
    _isSending = true;

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
            if (event.mode != null) {
              _currentMode = event.mode!;
            }
            if (event.coachState != null) {
              _coachState = event.coachState;
            }
            state = [...state];
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
            if (event.coachState != null) {
              _coachState = event.coachState;
            }
            if (event.coachAction != null) {
              _coachAction = event.coachAction;
            }
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
    } finally {
      _isSending = false;
    }
  }

  /// Inject an assistant message into the chat (used when spending triggers a
  /// chat reaction — the backend delivers it to the same conversation and we
  /// need to show it in the local message list without a full reload).
  void injectSpendingReaction(String conversationId, String content) {
    // Adopt the conversation if we don't have one yet (first interaction).
    if (_conversationId == null) {
      _conversationId = conversationId;
    }
    // Only inject if it belongs to the same conversation we're viewing.
    if (_conversationId != conversationId) return;

    final msg = ChatMessage(
      id: _uuid.v4(),
      role: 'assistant',
      content: content,
      createdAt: DateTime.now(),
    );
    state = [...state, msg];
  }

  void clearChat() {
    state = [];
    _conversationId = null;
    _currentMode = 'casual';
    _coachState = null;
    _coachAction = null;
  }
}
