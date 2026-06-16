import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

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

  Stream<String> chatStream(String message, String? conversationId) async* {
    final response = await _dio.post(
      '/api/chat',
      data: {
        'message': message,
        'conversation_id': conversationId,
        'stream': true,
      },
      options: Options(responseType: ResponseType.stream),
    );

    await for (final chunk in response.data.stream) {
      final text = String.fromCharCodes(chunk);
      for (final line in text.split('\n')) {
        if (line.startsWith('data: ') && !line.contains('[DONE]')) {
          yield line.substring(6);
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
}
