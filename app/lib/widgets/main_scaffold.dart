import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../models/spending.dart';
import '../providers/chat_provider.dart';
import '../screens/chat_screen.dart';
import '../screens/goals_screen.dart';
import '../screens/memes_screen.dart';
import '../screens/settings_screen.dart';
import 'spending_entry_sheet.dart';

class MainScaffold extends ConsumerStatefulWidget {
  const MainScaffold({super.key});

  @override
  ConsumerState<MainScaffold> createState() => _MainScaffoldState();
}

class _MainScaffoldState extends ConsumerState<MainScaffold> {
  int _index = 0;

  static const _screens = [
    ChatScreen(),
    GoalsScreen(),
    MemesScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      floatingActionButton: _index == 0
          ? FloatingActionButton(
              onPressed: () async {
                final convId = ref.read(chatProvider.notifier).conversationId;
                final result = await showModalBottomSheet<Spending>(
                  context: context,
                  isScrollControlled: true,
                  shape: const RoundedRectangleBorder(
                    borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
                  ),
                  builder: (_) => SpendingEntrySheet(conversationId: convId),
                );
                if (result != null &&
                    result.chatReaction != null &&
                    result.chatReaction!.isNotEmpty &&
                    result.conversationId != null) {
                  ref.read(chatProvider.notifier).injectSpendingReaction(
                        result.conversationId!,
                        result.chatReaction!,
                      );
                }
              },
              backgroundColor: AppTheme.primaryGradientStart,
              child: const Icon(Icons.receipt_long, color: Colors.white),
            )
          : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: '阿玖',
          ),
          NavigationDestination(
            icon: Icon(Icons.flag_outlined),
            selectedIcon: Icon(Icons.flag),
            label: '任务',
          ),
          NavigationDestination(
            icon: Icon(Icons.local_fire_department_outlined),
            selectedIcon: Icon(Icons.local_fire_department),
            label: '梗',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: '设置',
          ),
        ],
      ),
    );
  }
}
