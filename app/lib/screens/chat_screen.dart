import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/chat_provider.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/message_input.dart';
import 'settings_screen.dart';
import '../widgets/spending_entry_sheet.dart';

class ChatScreen extends ConsumerWidget {
  const ChatScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final messages = ref.watch(chatProvider);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.surface.withOpacity(0.72),
                border:
                    Border(bottom: BorderSide(color: AppTheme.border)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          AppTheme.primaryGradientStart,
                          AppTheme.primaryGradientEnd,
                        ],
                      ),
                      borderRadius:
                          BorderRadius.all(Radius.circular(10)),
                    ),
                    child: const Center(
                      child: Text('✦',
                          style: TextStyle(
                              color: Colors.white, fontSize: 14)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '阿玖',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Row(
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: const BoxDecoration(
                              color: AppTheme.onlineGreen,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Text(
                            '在线',
                            style: TextStyle(
                                fontSize: 10,
                                color: AppTheme.onlineGreen),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const Spacer(),
                  // Settings
                  IconButton(
                    icon: const Icon(Icons.settings, size: 20),
                    color: AppTheme.textSecondary,
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const SettingsScreen()),
                    ),
                  ),
                  // Live2D placeholder
                  Container(
                    width: 36,
                    height: 44,
                    decoration: BoxDecoration(
                      border: Border.all(
                          color: AppTheme.border, width: 1.5),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Center(
                      child:
                          Text('🫧', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                ],
              ),
            ),

            // Messages
            Expanded(
              child: messages.isEmpty
                  ? Center(
                      child: Text(
                        '开始聊天吧',
                        style: TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 14,
                        ),
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 12),
                      itemCount: messages.length,
                      itemBuilder: (_, i) =>
                          ChatBubble(message: messages[i]),
                    ),
            ),

            // Input
            MessageInput(
              onSubmit: (text) {
                ref.read(chatProvider.notifier).sendMessage(text);
              },
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          final convId = ref.read(chatProvider.notifier).conversationId;
          showModalBottomSheet(
            context: context, isScrollControlled: true,
            shape: const RoundedRectangleBorder(
                borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
            builder: (_) => SpendingEntrySheet(conversationId: convId),
          );
        },
        backgroundColor: AppTheme.primaryGradientStart,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }
}
