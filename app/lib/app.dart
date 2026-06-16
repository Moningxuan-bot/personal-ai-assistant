import 'package:flutter/material.dart';
import 'core/theme.dart';
import 'screens/chat_screen.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '阿玖',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const ChatScreen(),
    );
  }
}
