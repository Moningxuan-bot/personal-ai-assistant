# P1 支付监控 + 行为劝诫 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Spending tracker with two-tier Ajiu reaction — every entry gets a card-level quip, important ones trigger chat-level messages.

**Architecture:** Spending model → SpendingService (stats queries + LLM judgment) → FastAPI routes. Flutter: FAB → BottomSheet form → spending card in chat flow.

**Tech Stack:** SQLAlchemy async + DeepSeek LLM + FastAPI + Flutter Riverpod + Dio

**Spec:** `docs/superpowers/specs/2026-06-16-p1-spending-tracker-design.md`

---

### Task 1: Spending Model + Migration

**Files:**
- Create: `backend/app/models/spending.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Spending model**

```python
# backend/app/models/spending.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Numeric, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.database import Base


class Spending(Base):
    __tablename__ = "spendings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reaction: Mapped[str] = mapped_column(Text, nullable=False)
    chat_reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 2: Update models __init__.py**

```python
# backend/app/models/__init__.py
from app.models.database import Base
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.memory import Memory
from app.models.goal import Goal, GoalCheck
from app.models.spending import Spending

__all__ = ["Base", "Conversation", "Message", "Memory", "Goal", "GoalCheck", "Spending"]
```

- [ ] **Step 3: Generate and run migration**

```bash
cd backend
.venv/Scripts/alembic revision --autogenerate -m "add spendings table"
.venv/Scripts/alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/spending.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add Spending model and migration"
```

---

### Task 2: Spending Schemas

**Files:**
- Create: `backend/app/schemas/spending.py`

- [ ] **Step 1: Write schemas**

```python
# backend/app/schemas/spending.py
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

SPENDING_CATEGORIES = Literal["餐饮", "交通", "烟酒", "购物", "娱乐", "其他"]


class SpendingCreate(BaseModel):
    amount: float
    category: SPENDING_CATEGORIES
    note: str | None = None
    conversation_id: uuid.UUID | None = None


class SpendingResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID | None
    amount: float
    category: str
    note: str | None
    reaction: str
    chat_reaction: str | None
    chat_delivered: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SpendingStats(BaseModel):
    month: str
    total: float
    by_category: dict[str, float]
    ajiu_comment: str
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/spending.py
git commit -m "feat: add Spending Pydantic schemas"
```

---

### Task 3: Spending Service with LLM Judgment

**Files:**
- Create: `backend/app/services/spending.py`

- [ ] **Step 1: Write SpendingService**

```python
# backend/app/services/spending.py
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.spending import Spending
from app.models.message import Message
from app.providers.llm import LLMProvider, ChatMessage


class SpendingService:
    def __init__(self, db: AsyncSession, llm: LLMProvider):
        self.db = db
        self.llm = llm

    async def create_spending(
        self, amount: float, category: str, note: str | None,
        conversation_id: uuid.UUID | None,
    ) -> dict:
        stats = await self._gather_stats(category)
        judgment = await self._judge_spending(amount, category, note, stats)

        spending = Spending(
            conversation_id=conversation_id,
            amount=amount, category=category, note=note,
            reaction=judgment["reaction"],
            chat_reaction=judgment.get("chat_reaction") if judgment.get("needs_chat") else None,
            chat_delivered=False,
        )
        self.db.add(spending)
        await self.db.commit()

        if spending.chat_reaction and conversation_id:
            await self._deliver_chat_reaction(spending)

        return self._to_dict(spending)

    async def list_spendings(
        self, page: int = 1, category: str | None = None, limit: int = 20
    ) -> list[dict]:
        stmt = select(Spending).order_by(Spending.created_at.desc())
        if category:
            stmt = stmt.where(Spending.category == category)
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_dict(s) for s in result.scalars().all()]

    async def get_stats(self) -> dict:
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Spending).where(Spending.created_at >= month_start)
        result = await self.db.execute(stmt)
        month_spendings = result.scalars().all()

        total = float(sum(s.amount for s in month_spendings))
        by_category: dict[str, float] = {}
        for s in month_spendings:
            by_category[s.category] = by_category.get(s.category, 0) + float(s.amount)

        ajiu_comment = await self._monthly_comment(total, by_category)
        return {
            "month": now.strftime("%Y-%m"), "total": total,
            "by_category": by_category, "ajiu_comment": ajiu_comment,
        }

    # ---- internal ----

    async def _gather_stats(self, category: str) -> dict:
        now = datetime.now()
        day_ago = now - timedelta(hours=24)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        r = await self.db.execute(
            select(func.count(Spending.id)).where(
                Spending.category == category, Spending.created_at >= day_ago))
        same_24h = r.scalar() or 0

        r = await self.db.execute(
            select(func.count(Spending.id), func.coalesce(func.sum(Spending.amount), 0))
            .where(Spending.category == category, Spending.created_at >= month_start))
        row = r.one()
        same_month, same_total = row[0] or 0, float(row[1] or 0)

        r = await self.db.execute(
            select(func.coalesce(func.sum(Spending.amount), 0))
            .where(Spending.created_at >= month_start))
        monthly_total = float(r.scalar() or 0)

        return {"same_category_count_24h": same_24h, "same_category_count_month": same_month,
                "same_category_total": same_total, "monthly_total": monthly_total}

    async def _judge_spending(self, amount: float, category: str, note: str | None, stats: dict) -> dict:
        system_prompt = f"""你是阿玖——毒舌但关心用户的AI伴侣。用户刚记了一笔消费。

【上下文】当月同类{stats['same_category_count_month']}次/¥{stats['same_category_total']:.0f} | 本月总计¥{stats['monthly_total']:.0f} | 24h同类{stats['same_category_count_24h']}次

【消费】{category} ¥{amount} | 备注：{note or '无'}

返回JSON：
{{"reaction":"卡片级吐槽(1-2句，阿玖语气，必填)","needs_chat":true/false,"chat_reaction":"聊天级长篇(3-5句，needs_chat=true时必填)"}}

needs_chat=ture 条件：烟酒类 | 24h≥3次 | 金额>月均2倍 | 备注含冲动/忍不住/又买了/剁手"""

        messages = [ChatMessage(role="system", content=system_prompt)]
        try:
            response = await self.llm.chat(messages, stream=False)
            text = response.strip()
            if text.startswith("```"): text = text.split("\n", 1)[1].rstrip("```")
            result = json.loads(text)
            return {"reaction": result.get("reaction", "记下了。"),
                    "needs_chat": result.get("needs_chat", False),
                    "chat_reaction": result.get("chat_reaction", "")}
        except (json.JSONDecodeError, Exception):
            return {"reaction": self._default_reaction(category, amount),
                    "needs_chat": category == "烟酒", "chat_reaction": ""}

    async def _deliver_chat_reaction(self, spending: Spending) -> None:
        msg = Message(conversation_id=spending.conversation_id,
                      role="assistant", content=spending.chat_reaction)
        self.db.add(msg)
        spending.chat_delivered = True
        await self.db.commit()

    async def _monthly_comment(self, total: float, by_category: dict[str, float]) -> str:
        top = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        detail = "\n".join(f"  {c}: ¥{a:.0f}" for c, a in top)
        prompt = f"""你是阿玖。本月消费 ¥{total:.0f}：\n{detail}\n点评(2-3句，阿玖语气)。"""
        messages = [ChatMessage(role="system", content=prompt)]
        try:
            return (await self.llm.chat(messages, stream=False)).strip()
        except Exception:
            return f"这个月花了{total:.0f}。你自己看着办吧。"

    @staticmethod
    def _default_reaction(category: str, amount: float) -> str:
        return {"餐饮": f"又花了{amount:.0f}？行吧。","交通": "出行费记下了。",
                "烟酒": f"{amount:.0f}块。……算了不说了。","购物": f"买了{amount:.0f}。开心就好。",
                "娱乐": "玩得开心~","其他": f"记下了，{amount:.0f}元。"}.get(category, f"记下了。")

    @staticmethod
    def _to_dict(s: Spending) -> dict:
        return {"id": str(s.id), "conversation_id": str(s.conversation_id) if s.conversation_id else None,
                "amount": float(s.amount), "category": s.category, "note": s.note,
                "reaction": s.reaction, "chat_reaction": s.chat_reaction,
                "chat_delivered": s.chat_delivered, "created_at": s.created_at.isoformat()}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/spending.py
git commit -m "feat: add SpendingService with LLM two-tier reaction"
```

---

### Task 4: Spending Routes + Wire Up

**Files:**
- Create: `backend/app/routes/spendings.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write routes**

```python
# backend/app/routes/spendings.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.schemas.spending import SpendingCreate, SpendingResponse, SpendingStats
from app.services.spending import SpendingService
from app.providers.llm import DeepSeekProvider
from app.config import settings

router = APIRouter(tags=["spendings"], prefix="/spendings")

llm = DeepSeekProvider(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def get_service(db: AsyncSession = Depends(get_db)) -> SpendingService:
    return SpendingService(db, llm)


@router.post("", response_model=SpendingResponse)
async def create_spending(body: SpendingCreate, svc=Depends(get_service)):
    return await svc.create_spending(body.amount, body.category, body.note, body.conversation_id)


@router.get("", response_model=list[SpendingResponse])
async def list_spendings(page: int = Query(1, ge=1), category: str | None = None,
                         svc=Depends(get_service)):
    return await svc.list_spendings(page=page, category=category)


@router.get("/stats", response_model=SpendingStats)
async def spending_stats(svc=Depends(get_service)):
    return await svc.get_stats()
```

- [ ] **Step 2: Wire in main.py** — add after goals router import:

```python
from app.routes import chat, health, goals, spendings
# ...
app.include_router(spendings.router, prefix="/api")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/spendings.py backend/app/main.py
git commit -m "feat: add Spending API routes (POST/GET/GET stats)"
```

---

### Task 5: Backend Tests

**Files:**
- Create: `backend/tests/test_spending.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_spending.py
import json
import pytest
from unittest.mock import AsyncMock
from app.services.spending import SpendingService
from app.models.spending import Spending
from app.providers.llm import LLMProvider


@pytest.mark.anyio
async def test_create_spending_with_reaction(db_session):
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = json.dumps({"reaction":"又吃麻辣烫？","needs_chat":False,"chat_reaction":""})
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(35.5, "餐饮", "麻辣烫", None)
    assert r["amount"] == 35.5
    assert "麻辣烫" in r["reaction"]
    assert r["chat_reaction"] is None


@pytest.mark.anyio
async def test_cigarette_triggers_chat():
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = json.dumps(
        {"reaction":"又买烟？","needs_chat":True,"chat_reaction":"这个月第N次了。你的肺不是我的。"})
    svc = SpendingService(None, mock_llm)
    r = await svc._judge_spending(25, "烟酒", "买烟",
        {"same_category_count_24h":2,"same_category_count_month":5,"same_category_total":125,"monthly_total":2000})
    assert r["needs_chat"] is True
    assert len(r["chat_reaction"]) > 10


@pytest.mark.anyio
async def test_normal_spending_no_chat(db_session):
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = json.dumps({"reaction":"4块地铁，记下了。","needs_chat":False,"chat_reaction":""})
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(4, "交通", "地铁", None)
    assert r["chat_reaction"] is None


@pytest.mark.anyio
async def test_list_spendings(db_session):
    db_session.add(Spending(amount=10, category="餐饮", note="早", reaction="嗯。"))
    db_session.add(Spending(amount=50, category="购物", note="书", reaction="行。"))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    r = await SpendingService(db_session, mock_llm).list_spendings()
    assert len(r) >= 2


@pytest.mark.anyio
async def test_category_filter(db_session):
    db_session.add(Spending(amount=10, category="餐饮", note="早", reaction="嗯。"))
    db_session.add(Spending(amount=50, category="购物", note="书", reaction="行。"))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    r = await SpendingService(db_session, mock_llm).list_spendings(category="餐饮")
    assert len(r) == 1 and r[0]["category"] == "餐饮"


@pytest.mark.anyio
async def test_stats(db_session):
    from datetime import datetime
    db_session.add_all([
        Spending(amount=100, category="餐饮", note="", reaction="嗯", created_at=datetime.now()),
        Spending(amount=200, category="购物", note="", reaction="嗯", created_at=datetime.now()),
    ])
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "还行。"
    s = await SpendingService(db_session, mock_llm).get_stats()
    assert s["total"] == 300.0
    assert s["by_category"]["餐饮"] == 100.0


@pytest.mark.anyio
async def test_llm_failure_fallback(db_session):
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.side_effect = Exception("down")
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(25, "烟酒", "买烟", None)
    assert r["reaction"]
    assert len(r["reaction"]) > 0
```

- [ ] **Step 2: Run tests**

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -v
```
Expected: 34 tests pass (27 previous + 7 new)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_spending.py
git commit -m "test: add SpendingService tests (7 cases)"
```

---

### Task 6: Flutter — Model + API Client + Provider

**Files:**
- Create: `app/lib/models/spending.dart`
- Modify: `app/lib/core/api_client.dart`
- Create: `app/lib/providers/spending_provider.dart`

- [ ] **Step 1: Spending model**

```dart
// app/lib/models/spending.dart
class Spending {
  final String id;
  final String? conversationId;
  final double amount;
  final String category;
  final String? note;
  final String reaction;
  final String? chatReaction;
  final bool chatDelivered;
  final DateTime createdAt;

  const Spending({
    required this.id, this.conversationId, required this.amount,
    required this.category, this.note, required this.reaction,
    this.chatReaction, required this.chatDelivered, required this.createdAt,
  });

  factory Spending.fromJson(Map<String, dynamic> json) => Spending(
    id: json['id'], conversationId: json['conversation_id'],
    amount: (json['amount'] as num).toDouble(), category: json['category'],
    note: json['note'], reaction: json['reaction'],
    chatReaction: json['chat_reaction'], chatDelivered: json['chat_delivered'] ?? false,
    createdAt: DateTime.parse(json['created_at']),
  );
}
```

- [ ] **Step 2: Add to ApiClient** (inside class, after existing methods)

```dart
// Add import at top: import '../models/spending.dart';

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
```

- [ ] **Step 3: Spending provider**

```dart
// app/lib/providers/spending_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/spending.dart';
import 'chat_provider.dart';

final spendingProvider = StateNotifierProvider<SpendingNotifier, List<Spending>>((ref) {
  final apiAsync = ref.watch(apiClientProvider);
  return apiAsync.when(
    data: (api) => SpendingNotifier(api),
    loading: () => SpendingNotifier.loading(),
    error: (e, _) => SpendingNotifier.error(e),
  );
});

class SpendingNotifier extends StateNotifier<List<Spending>> {
  final ApiClient? _api;
  bool _submitting = false;
  bool get isSubmitting => _submitting;

  SpendingNotifier(ApiClient api) : _api = api, super([]);
  SpendingNotifier.loading() : _api = null, super([]);
  SpendingNotifier.error(Object e) : _api = null, super([]);

  Future<Spending?> submit({
    required double amount, required String category,
    String? note, String? conversationId,
  }) async {
    if (_submitting || _api == null) return null;
    _submitting = true;
    try {
      final s = await _api!.createSpending(
          amount: amount, category: category, note: note, conversationId: conversationId);
      state = [s, ...state];
      return s;
    } finally { _submitting = false; }
  }

  Future<void> load({int page = 1, String? category}) async {
    if (_api == null) return;
    state = await _api!.listSpendings(page: page, category: category);
  }

  Future<Map<String, dynamic>?> stats() async {
    if (_api == null) return null;
    return await _api!.getSpendingStats();
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add app/lib/models/spending.dart app/lib/core/api_client.dart app/lib/providers/spending_provider.dart
git commit -m "feat: add Flutter spending model + API + provider"
```

---

### Task 7: Flutter — Spending Card + Entry Sheet

**Files:**
- Create: `app/lib/widgets/spending_card.dart`
- Create: `app/lib/widgets/spending_entry_sheet.dart`

- [ ] **Step 1: Spending card widget**

```dart
// app/lib/widgets/spending_card.dart
import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../models/spending.dart';

class SpendingCard extends StatelessWidget {
  final Spending spending;
  const SpendingCard({super.key, required this.spending});

  static const _icons = {'餐饮':'🍜','交通':'🚇','烟酒':'🚬','购物':'🛒','娱乐':'🎮','其他':'💰'};

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    child: Container(
      decoration: BoxDecoration(color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14), border: Border.all(color: AppTheme.border)),
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(_icons[spending.category] ?? '💰', style: const TextStyle(fontSize: 20)),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(spending.category, style: const TextStyle(fontSize:13, fontWeight:FontWeight.w600, color:AppTheme.textPrimary)),
            if (spending.note != null && spending.note!.isNotEmpty)
              Text(spending.note!, style: const TextStyle(fontSize:11, color:AppTheme.textSecondary), maxLines:1, overflow:TextOverflow.ellipsis),
          ])),
          Text('¥${spending.amount.toStringAsFixed(2)}',
              style: const TextStyle(fontSize:16, fontWeight:FontWeight.w700, color:AppTheme.textPrimary)),
        ]),
        const SizedBox(height: 8),
        Container(padding: const EdgeInsets.symmetric(horizontal:8, vertical:6),
          decoration: BoxDecoration(color: AppTheme.primaryGradientStart.withOpacity(0.08), borderRadius: BorderRadius.circular(8)),
          child: Text(spending.reaction, style: const TextStyle(fontSize:12, color:AppTheme.textSecondary, fontStyle:FontStyle.italic))),
      ]),
    ),
  );
}
```

- [ ] **Step 2: Spending entry BottomSheet**

```dart
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
  static const _cats = ['餐饮','交通','烟酒','购物','娱乐','其他'];

  @override
  void dispose() { _amountCtrl.dispose(); _noteCtrl.dispose(); super.dispose(); }

  Future<void> _submit() async {
    final a = double.tryParse(_amountCtrl.text);
    if (a == null || a <= 0) return;
    final notifier = ref.read(spendingProvider.notifier);
    await notifier.submit(amount: a, category: _cat,
        note: _noteCtrl.text.isNotEmpty ? _noteCtrl.text : null,
        conversationId: widget.conversationId);
    if (mounted) Navigator.of(context).pop();
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
          onPressed: _submit,
          style: FilledButton.styleFrom(backgroundColor:AppTheme.primaryGradientStart,
              padding: const EdgeInsets.symmetric(vertical:14),
              shape: RoundedRectangleBorder(borderRadius:BorderRadius.circular(12))),
          child: const Text('记下')),
      ),
      const SizedBox(height:8),
    ]));
}
```

- [ ] **Step 3: Commit**

```bash
git add app/lib/widgets/spending_card.dart app/lib/widgets/spending_entry_sheet.dart
git commit -m "feat: add SpendingCard and SpendingEntrySheet widgets"
```

---

### Task 8: Flutter — Chat Screen FAB + Settings Link

**Files:**
- Modify: `app/lib/screens/chat_screen.dart`
- Modify: `app/lib/screens/settings_screen.dart`
- Create: `app/lib/screens/spending_stats_screen.dart`

- [ ] **Step 1: Add FAB + spending card rendering to chat_screen**

In `chat_screen.dart`, add to Scaffold:
```dart
      floatingActionButton: FloatingActionButton(
        onPressed: () => showModalBottomSheet(
          context: context, isScrollControlled: true,
          shape: const RoundedRectangleBorder(
              borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
          builder: (_) => const SpendingEntrySheet(),
        ),
        backgroundColor: AppTheme.primaryGradientStart,
        child: const Icon(Icons.add, color: Colors.white),
      ),
```

Add imports at top:
```dart
import '../widgets/spending_entry_sheet.dart';
```

- [ ] **Step 2: Add stats screen**

```dart
// app/lib/screens/spending_stats_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/spending_provider.dart';

class SpendingStatsScreen extends ConsumerStatefulWidget {
  const SpendingStatsScreen({super.key});
  @override
  ConsumerState<SpendingStatsScreen> createState() => _SpendingStatsScreenState();
}

class _SpendingStatsScreenState extends ConsumerState<SpendingStatsScreen> {
  Map<String, dynamic>? _stats;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    final s = await ref.read(spendingProvider.notifier).stats();
    if (mounted) setState(() => _stats = s);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppTheme.background,
    appBar: AppBar(title: const Text('消费记录', style: TextStyle(color: AppTheme.textPrimary))),
    body: _stats == null
      ? const Center(child: CircularProgressIndicator())
      : ListView(padding: const EdgeInsets.all(16), children: [
          _infoCard('本月总消费', '¥${(_stats!['total'] as num).toStringAsFixed(0)}'),
          const SizedBox(height:8),
          _infoCard('阿玖点评', _stats!['ajiu_comment'] ?? ''),
          const SizedBox(height:16),
          const Text('分类明细', style: TextStyle(fontSize:15, fontWeight:FontWeight.w600)),
          const SizedBox(height:8),
          ...(_stats!['by_category'] as Map<String,dynamic>).entries.map((e) =>
            _catRow(e.key, (e.value as num).toDouble())),
        ]),
  );

  Widget _infoCard(String title, String content) => Container(
    width: double.infinity, padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontSize:11, color:AppTheme.textSecondary)),
      const SizedBox(height:4),
      Text(content, style: const TextStyle(fontSize:15, color:AppTheme.textPrimary)),
    ]));

  Widget _catRow(String cat, double amt) => Padding(
    padding: const EdgeInsets.symmetric(vertical:6),
    child: Row(children: [
      Expanded(child: Text(cat, style: const TextStyle(fontSize:13, color:AppTheme.textPrimary))),
      Text('¥${amt.toStringAsFixed(0)}',
          style: const TextStyle(fontSize:13, fontWeight:FontWeight.w600, color:AppTheme.textPrimary)),
    ]));
}
```

- [ ] **Step 3: Add link in settings_screen**

In `settings_screen.dart`, add import:
```dart
import 'spending_stats_screen.dart';
```

Add a ListTile before the existing fields:
```dart
            ListTile(
              leading: const Icon(Icons.receipt_long),
              title: const Text('消费记录'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SpendingStatsScreen()),
              ),
            ),
            const Divider(),
```

- [ ] **Step 4: Commit**

```bash
git add app/lib/screens/chat_screen.dart app/lib/screens/settings_screen.dart app/lib/screens/spending_stats_screen.dart
git commit -m "feat: add FAB + spending card + stats screen + settings link"
```

---

### Task 9: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -v
```
Expected: 34 tests pass (27 previous + 7 spending)

- [ ] **Step 2: Verify API manually**

```bash
# Start backend if not running
curl -X POST http://localhost:8000/api/spendings \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: local-dev-secret" \
  -d '{"amount":35.5,"category":"餐饮","note":"麻辣烫"}'
# Expected: JSON with id, amount, reaction, etc.

curl http://localhost:8000/api/spendings/stats \
  -H "X-Device-Token: local-dev-secret"
# Expected: JSON with month, total, by_category, ajiu_comment
```

- [ ] **Step 3: Final commit + push**

```bash
git push
```
