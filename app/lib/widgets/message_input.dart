import 'package:flutter/material.dart';
import '../core/theme.dart';

class MessageInput extends StatefulWidget {
  final void Function(String) onSubmit;

  const MessageInput({super.key, required this.onSubmit});

  @override
  State<MessageInput> createState() => _MessageInputState();
}

class _MessageInputState extends State<MessageInput> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      setState(() => _hasText = _controller.text.trim().isNotEmpty);
    });
  }

  void _send() {
    if (!_hasText) return;
    widget.onSubmit(_controller.text.trim());
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.border),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        padding: const EdgeInsets.only(left: 4),
        child: Row(
          children: [
            IconButton(
              icon: const Icon(Icons.attach_file, size: 20),
              color: AppTheme.textSecondary,
              onPressed: () {},
            ),
            Expanded(
              child: TextField(
                controller: _controller,
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textPrimary),
                decoration: const InputDecoration(
                  hintText: '输入消息...',
                  hintStyle:
                      TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(vertical: 8),
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                maxLines: null,
              ),
            ),
            IconButton(
              icon: const Icon(Icons.mic, size: 20),
              color: AppTheme.textSecondary,
              onPressed: () {},
            ),
            if (_hasText)
              Container(
                margin: const EdgeInsets.only(right: 4),
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      AppTheme.primaryGradientStart,
                      AppTheme.primaryGradientEnd,
                    ],
                  ),
                  borderRadius: BorderRadius.all(Radius.circular(12)),
                ),
                child: IconButton(
                  icon: const Icon(Icons.arrow_upward, size: 18),
                  color: Colors.white,
                  onPressed: _send,
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
