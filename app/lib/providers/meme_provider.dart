import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/meme.dart';
import 'chat_provider.dart';

final memeProvider = StateNotifierProvider<MemeNotifier, List<Meme>>((ref) {
  final apiClientAsync = ref.watch(apiClientProvider);
  return apiClientAsync.when(
    data: (api) => MemeNotifier(api),
    loading: () => MemeNotifier.loading(),
    error: (error, _) => MemeNotifier.error(error),
  );
});

class MemeNotifier extends StateNotifier<List<Meme>> {
  final ApiClient? _api;

  MemeNotifier(this._api) : super([]);

  MemeNotifier.loading()
      : _api = null,
        super([]);

  MemeNotifier.error(Object error)
      : _api = null,
        super([]);

  Future<void> loadTodayMemes() async {
    if (_api == null) return;
    try {
      final data = await _api!.getTodayMemes();
      state = data.map(Meme.fromJson).toList();
    } catch (_) {}
  }

  Future<void> fetchLatest() async {
    if (_api == null) return;
    try {
      final data = await _api!.fetchMemes();
      state = data.map(Meme.fromJson).toList();
    } catch (_) {}
  }

  Future<void> keep(String id) async {
    if (_api == null) return;
    try {
      final data = await _api!.keepMeme(id);
      final updated = Meme.fromJson(data);
      state = state.map((meme) => meme.id == id ? updated : meme).toList();
    } catch (_) {}
  }

  Future<void> discard(String id) async {
    if (_api == null) return;
    try {
      await _api!.discardMeme(id);
      state = state.where((meme) => meme.id != id).toList();
    } catch (_) {}
  }

  List<Meme> get keptMemes => state.where((meme) => meme.kept).toList();
}
