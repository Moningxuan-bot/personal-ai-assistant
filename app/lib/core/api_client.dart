import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/spending.dart';

class ChatStreamEvent {
  final String type; // "meta", "delta", "done", "error"
  final String? conversationId;
  final String? content;
  final String? message; // error message

  const ChatStreamEvent({
    required this.type,
    this.conversationId,
    this.content,
    this.message,
  });

  factory ChatStreamEvent.fromJson(Map<String, dynamic> json) {
    return ChatStreamEvent(
      type: json['type'] as String? ?? 'unknown',
      conversationId: json['conversation_id'] as String?,
      content: json['content'] as String?,
      message: json['message'] as String?,
    );
  }
}

class ApiClient {
  late final Dio _dio;
  final _storage = const FlutterSecureStorage();

  ApiClient({required String baseUrl}) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 60),
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'device_token') ?? '';
        options.headers['X-Device-Token'] = token;
        handler.next(options);
      },
    ));
  }

  Future<String> get deviceToken async =>
      await _storage.read(key: 'device_token') ?? '';

  Future<void> setDeviceToken(String token) async =>
      await _storage.write(key: 'device_token', token);

  /// Returns a stream of structured chat events (meta / delta / done / error).
  /// Uses proper UTF-8 streaming decoder to avoid splitting multi-byte chars.
  Stream<ChatStreamEvent> chatStream(String message, String? conversationId) async* {
    final response = await _dio.post(
      '/api/chat',
      data: {
        'message': message,
        'conversation_id': conversationId,
        'stream': true,
      },
      options: Options(responseType: ResponseType.stream),
    );

    final lineBuffer = StringBuffer();
    await for (final text in response.data.stream.cast<List<int>>().transform(utf8.decoder)) {
      lineBuffer.write(text);

      // Process complete lines only (SSE lines end with \n\n)
      while (true) {
        final bufferStr = lineBuffer.toString();
        final doubleNewline = bufferStr.indexOf('\n\n');
        if (doubleNewline == -1) break;

        final line = bufferStr.substring(0, doubleNewline).trim();
        lineBuffer.clear();
        // Write back anything after the \n\n
        if (doubleNewline + 2 < bufferStr.length) {
          lineBuffer.write(bufferStr.substring(doubleNewline + 2));
        }

        if (line.startsWith('data: ')) {
          final jsonStr = line.substring(6);
          try {
            final json = jsonDecode(jsonStr) as Map<String, dynamic>;
            yield ChatStreamEvent.fromJson(json);
          } catch (_) {
            // Skip malformed JSON lines
          }
        }
      }
    }
  }

  Future<List<Map<String, dynamic>>> getMessages(String conversationId) async {
    final response =
        await _dio.get('/api/conversations/$conversationId/messages');
    return List<Map<String, dynamic>>.from(response.data);
  }

  Future<void> deleteConversation(String conversationId) async {
    await _dio.delete('/api/conversations/$conversationId');
  }

  Future<Spending> createSpending({
    required double amount, required String category,
    String? note, String? conversationId,
  }) async {
    final data = <String, dynamic>{'amount': amount, 'category': category};
    if (note != null) data['note'] = note;
    if (conversationId != null) data['conversation_id'] = conversationId;
    final resp = await _dio.post('/api/spendings', data: data);
    return Spending.fromJson(resp.data);
  }

  Future<List<Spending>> listSpendings({int page = 1, String? category}) async {
    final resp = await _dio.get('/api/spendings',
        queryParameters: {'page': page, if (category != null) 'category': category});
    return (resp.data as List).map((e) => Spending.fromJson(e)).toList();
  }

  Future<Map<String, dynamic>> getSpendingStats() async {
    final resp = await _dio.get('/api/spendings/stats');
    return resp.data;
  }
}
