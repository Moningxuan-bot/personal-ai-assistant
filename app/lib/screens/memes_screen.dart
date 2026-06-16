import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/meme_provider.dart';
import '../widgets/meme_card.dart';

class MemesScreen extends ConsumerStatefulWidget {
  const MemesScreen({super.key});

  @override
  ConsumerState<MemesScreen> createState() => _MemesScreenState();
}

class _MemesScreenState extends ConsumerState<MemesScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(memeProvider.notifier).loadTodayMemes());
  }

  @override
  Widget build(BuildContext context) {
    final memes = ref.watch(memeProvider);

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('今日梗', style: TextStyle(color: AppTheme.textPrimary)),
        actions: [
          IconButton(
            tooltip: '抓取',
            icon: const Icon(Icons.cloud_download_outlined),
            onPressed: () => ref.read(memeProvider.notifier).fetchLatest(),
          ),
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(memeProvider.notifier).loadTodayMemes(),
          ),
        ],
      ),
      body: memes.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.local_fire_department_outlined,
                    size: 48,
                    color: Colors.grey.shade300,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '今日无梗\n阿玖 22:00 帮你捞新的',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 14, color: Colors.grey.shade500),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              onRefresh: () => ref.read(memeProvider.notifier).loadTodayMemes(),
              child: ListView.builder(
                padding: const EdgeInsets.only(top: 8, bottom: 88),
                itemCount: memes.length,
                itemBuilder: (context, index) {
                  final meme = memes[index];
                  return MemeCard(
                    meme: meme,
                    onKeep: () => ref.read(memeProvider.notifier).keep(meme.id),
                    onDiscard: () => ref.read(memeProvider.notifier).discard(meme.id),
                  );
                },
              ),
            ),
    );
  }
}
