// app/lib/widgets/spending_entry_sheet.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/spending_provider.dart';

class SpendingEntrySheet extends ConsumerStatefulWidget {
  final String? conversationId;
  const SpendingEntrySheet({super.key, this.conversationId});

  @override
  ConsumerState<SpendingEntrySheet> createState() => _SpendingEntrySheetState();
}

class _SpendingEntrySheetState extends ConsumerState<SpendingEntrySheet> {
  final _amountCtrl = TextEditingController(), _noteCtrl = TextEditingController();
  String _cat = '餐饮';
  bool _submitting = false;
  static const _cats = ['餐饮','交通','烟酒','购物','娱乐','其他'];

  @override
  void dispose() { _amountCtrl.dispose(); _noteCtrl.dispose(); super.dispose(); }

  Future<void> _submit() async {
    final raw = _amountCtrl.text.trim().replaceAll('，', '.').replaceAll('¥', '').replaceAll('￥', '');
    final a = double.tryParse(raw);
    if (a == null || a <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入有效金额')),
      );
      return;
    }
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      final spending = await ref.read(spendingProvider.notifier).submit(
        amount: a, category: _cat,
        note: _noteCtrl.text.isNotEmpty ? _noteCtrl.text : null,
        conversationId: widget.conversationId,
      );
      if (!mounted) return;
      if (spending == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('还没连上后端')),
        );
        return;
      }
      Navigator.of(context).pop(spending);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('记账失败：$e')),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(padding: EdgeInsets.only(
    bottom: MediaQuery.of(context).viewInsets.bottom, left: 16, right: 16, top: 16),
    child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('记一笔', style: TextStyle(fontSize:17, fontWeight:FontWeight.w600)),
      const SizedBox(height:12),
      Row(children: [
        const Text('¥', style: TextStyle(fontSize:20, color:AppTheme.textSecondary)),
        const SizedBox(width:8),
        Expanded(child: TextField(controller: _amountCtrl, autofocus: true,
            keyboardType: TextInputType.numberWithOptions(decimal:true),
            decoration: const InputDecoration(hintText:'金额', border:OutlineInputBorder()))),
      ]),
      const SizedBox(height:12),
      DropdownButtonFormField<String>(value:_cat,
        decoration: const InputDecoration(labelText:'分类', border:OutlineInputBorder()),
        items: _cats.map((c) => DropdownMenuItem(value:c, child:Text(c))).toList(),
        onChanged: (v) => setState(() => _cat = v!)),
      const SizedBox(height:12),
      TextField(controller: _noteCtrl,
          decoration: const InputDecoration(hintText:'备注（给阿玖点线索）', border:OutlineInputBorder())),
      const SizedBox(height:16),
      SizedBox(width:double.infinity,
        child: FilledButton(
          onPressed: _submitting ? null : _submit,
          style: FilledButton.styleFrom(backgroundColor:AppTheme.primaryGradientStart,
              padding: const EdgeInsets.symmetric(vertical:14),
              shape: RoundedRectangleBorder(borderRadius:BorderRadius.circular(12))),
          child: Text(_submitting ? '记下中...' : '记下')),
      ),
      const SizedBox(height:8),
    ]));
}
