"""
阿玖统一人格层 —— AjiuVoiceService

所有用户可见的自然语言文本，都必须经过这一层生成。
业务模块只产出结构化事件，不写阿玖话术。

设计原则：
- 核心人格 AJIU_SYSTEM_PROMPT 是所有文案的必经底座
- 每个场景叠加场景规则，但不重新定义"阿玖是谁"
- OutputValidator 校验输出质量，第一阶段只记日志不阻断
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from app.prompts.ajiu import AJIU_SYSTEM_PROMPT
from app.providers.llm import LLMProvider, ChatMessage

logger = logging.getLogger("ajiu_voice")


# ============================================================
# 事件类型
# ============================================================


class AjiuEventType(StrEnum):
    """阿玖需要处理的事件类型。"""
    # --- 消费事件 ---
    SPENDING_REACTION = "spending_reaction"           # 卡片级 1-2 句吐槽
    SPENDING_CHAT_REACTION = "spending_chat_reaction" # 聊天级 3-5 句
    SPENDING_MONTHLY_COMMENT = "spending_monthly_comment"  # 月度点评

    # --- 教练事件（预留） ---
    COACH_FIRST_ASK = "coach_first_ask"
    COACH_ANSWER_PASS = "coach_answer_pass"
    COACH_ANSWER_FAIL = "coach_answer_fail"
    COACH_SIGH_MOVE_ON = "coach_sigh_move_on"
    COACH_PLAN_READY = "coach_plan_ready"
    COACH_REVISE = "coach_revise"
    COACH_CONFIRMED = "coach_confirmed"
    COACH_REJECTED = "coach_rejected"

    # --- 梗事件（预留） ---
    MEME_REWRITE = "meme_rewrite"

    # --- 记忆事件（预留） ---
    CONTRADICTION_MOCKERY = "contradiction_mockery"


# ============================================================
# 数据结构
# ============================================================


@dataclass
class VoiceEvent:
    """业务模块产出的结构化事件。"""
    event_type: AjiuEventType
    payload: dict
    intensity: float = 1.0            # 0.0=极简  1.0=全阿玖
    conversation_context: str = ""    # 可选：最近对话上下文

    # ---- 消费 payload 结构 ----
    # spending_reaction / spending_chat_reaction:
    #   amount: float
    #   category: str        (餐饮/交通/烟酒/购物/娱乐/其他)
    #   note: str | None
    #   stats: dict          {same_category_count_24h, same_category_count_month,
    #                          same_category_total, monthly_total}
    #   risk_level: str      ("low" | "medium" | "high")
    #   risk_reason: str     (触发关注的原因，如 "smoking_frequent")
    #
    # spending_monthly_comment:
    #   month: str           ("2026-06")
    #   total: float
    #   by_category: dict[str, float]


@dataclass
class ValidationResult:
    """OutputValidator 的校验结果。"""
    passed: bool
    issues: list[str] = field(default_factory=list)


# ============================================================
# 输出校验器
# ============================================================


class OutputValidator:
    """检查生成的文本是否符合阿玖人格标准。

    第一阶段（当前）：仅记录问题，不阻断输出。
    第二阶段（后续）：不合格时自动重试或降级到安全模板。
    """

    BANNED_PHRASES: set[str] = {
        "很高兴为您服务",
        "请问还有什么可以帮您",
        "请问有什么需要帮助的吗",
        "有什么可以帮助您的",
        "我是AI",
        "我是人工智能",
        "我是AI助手",
        "作为AI",
        "作为一个人工智能",
        "您的问题已记录",
        "已收到您的请求",
    }

    MAX_LENGTH = 600
    MIN_LENGTH = 2
    MAX_QUESTION_RATIO = 0.35

    @classmethod
    def validate(cls, text: str, event_type: AjiuEventType | None = None) -> ValidationResult:
        issues: list[str] = []

        # 1. 禁止用词（客服语气 / 非阿玖式自称）
        for phrase in cls.BANNED_PHRASES:
            if phrase in text:
                issues.append(f"包含客服/非阿玖语气: 「{phrase}」")

        # 2. 长度限制
        if len(text) > cls.MAX_LENGTH:
            issues.append(f"过长: {len(text)} 字 (上限 {cls.MAX_LENGTH})")
        elif len(text) < cls.MIN_LENGTH:
            issues.append(f"过短: {len(text)} 字 (下限 {cls.MIN_LENGTH})")

        # 3. 问号密度（排除太短的文本）
        if len(text) > 10:
            q_count = text.count("？") + text.count("?")
            if q_count / len(text) > cls.MAX_QUESTION_RATIO:
                issues.append(f"问号过多: {q_count} 个 / {len(text)} 字")

        # 4. 禁止以客服式开头
        if text.startswith("您好") or text.startswith("你好"):
            issues.append("以'您好/你好'开头（非阿玖式问好）")

        # 5. 记账事件专属规则
        if event_type in (AjiuEventType.SPENDING_REACTION, AjiuEventType.SPENDING_CHAT_REACTION):
            # 必须包含记账确认词
            has_confirm = any(w in text for w in ("记下", "记上", "记了", "知道了", "行吧", "行了", "好嘞"))
            if not has_confirm:
                issues.append("记账回复缺少确认词（应含：记下了/行吧/知道了 等）")

        return ValidationResult(passed=len(issues) == 0, issues=issues)


# ============================================================
# 阿玖统一人格服务
# ============================================================


class AjiuVoiceService:
    """统一人格层——所有阿玖文本生成均通过此服务。

    业务模块只产出 VoiceEvent，AjiuVoiceService 负责将其渲染
    为阿玖语气的用户可见文本。核心人格 AJIU_SYSTEM_PROMPT 是
    所有渲染的必经底座。
    """

    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.validator = OutputValidator()

    # ---- 主入口 ----

    async def render_event(self, event: VoiceEvent) -> str:
        """将结构化事件渲染为阿玖语气的文本。"""
        renderer = self._get_renderer(event.event_type)
        try:
            text = await renderer(event)
        except Exception:
            logger.warning(f"LLM render failed for {event.event_type}, using fallback", exc_info=True)
            text = self._get_fallback(event)

        # 输出校验（第一阶段——仅日志，不阻断）
        result = self.validator.validate(text, event.event_type)
        if not result.passed:
            logger.info(
                f"Validation issues for {event.event_type.value}: "
                f"{'; '.join(result.issues)} | text={text[:100]}..."
            )

        return text

    def _get_renderer(self, event_type: AjiuEventType):
        """事件类型 → 渲染器映射。"""
        renderers = {
            AjiuEventType.SPENDING_REACTION: self._render_spending_reaction,
            AjiuEventType.SPENDING_CHAT_REACTION: self._render_spending_chat_reaction,
            AjiuEventType.SPENDING_MONTHLY_COMMENT: self._render_spending_monthly,
        }
        if event_type in renderers:
            return renderers[event_type]
        raise ValueError(f"Unknown event type: {event_type}")

    def _get_fallback(self, event: VoiceEvent) -> str:
        """LLM 不可用时的兜底模板。"""
        fallbacks = {
            AjiuEventType.SPENDING_REACTION: self._default_reaction,
            AjiuEventType.SPENDING_CHAT_REACTION: self._default_chat_reaction,
            AjiuEventType.SPENDING_MONTHLY_COMMENT: self._default_monthly_comment,
        }
        if event.event_type in fallbacks:
            return fallbacks[event.event_type](event.payload)
        return "……嗯，知道了。"  # 终极兜底

    # ---- 系统提示构建 ----

    def _build_system_prompt_for_event(self, event: VoiceEvent, scene_prompt: str) -> str:
        """所有渲染器的提示词都必须以核心人格为底座，叠加场景规则。"""
        parts = [AJIU_SYSTEM_PROMPT]
        parts.append(scene_prompt)
        parts.append("记住：你是阿玖。保持你的语气——口语化、不做作、不客服。")
        return "\n\n".join(parts)

    # ---- 消费事件渲染 ----

    async def _render_spending_reaction(self, event: VoiceEvent) -> str:
        """卡片级消费吐槽（1-2 句）。"""
        p = event.payload
        stats = p.get("stats", {})

        scene = (
            f"## 当前场景：用户刚记了一笔消费\n\n"
            f"用阿玖的语气给一个简短吐槽（1-2 句，不超过 80 字）。"
            f"这是卡片级反应，要短而精，不需要长篇大论。\n\n"
            f"消费信息：{p['category']} ¥{p['amount']:.0f}"
            f"{'，备注：' + p['note'] if p.get('note') else ''}\n"
            f"背景：当月同类 {stats.get('same_category_count_month', 0)} 次"
            f" / ¥{stats.get('same_category_total', 0):.0f}"
            f" | 本月累计 ¥{stats.get('monthly_total', 0):.0f}"
            f" | 24h 同类 {stats.get('same_category_count_24h', 0)} 次"
        )

        system = self._build_system_prompt_for_event(event, scene)
        messages = [ChatMessage(role="system", content=system)]
        text = (await self.llm.chat(messages, stream=False)).strip()
        return text or self._default_reaction(p)

    async def _render_spending_chat_reaction(self, event: VoiceEvent) -> str:
        """聊天级消费反应（3-5 句，注入到对话中）。"""
        p = event.payload
        stats = p.get("stats", {})
        risk_level = p.get("risk_level", "low")
        risk_reason = p.get("risk_reason", "")

        # 根据风险等级调整语气强度提示
        intensity_hints = {
            "high": "这笔消费触发了高危关注（烟酒/高频/大额），语气可以更重一点，"
                    "带上担心和念叨。但不超过 5 句，不要审判和说教。",
            "medium": "这笔消费值得注意，随口念叨一下。",
            "low": "这笔消费很普通，自然地带过即可。",
        }

        scene = (
            f"## 当前场景：用户记了一笔消费，你需要在聊天里回应\n\n"
            f"用阿玖的语气自然地聊这件事（3-5 句）。\n"
            f"不要像系统通知，要像朋友看到你花钱后念叨两句。\n"
            f"{intensity_hints.get(risk_level, intensity_hints['low'])}\n\n"
            f"消费信息：{p['category']} ¥{p['amount']:.0f}"
            f"{'，备注：' + p['note'] if p.get('note') else ''}\n"
            f"关注原因：{risk_reason or '无特殊原因'}\n"
            f"背景：当月同类 {stats.get('same_category_count_month', 0)} 次"
            f" / ¥{stats.get('same_category_total', 0):.0f}"
            f" | 本月累计 ¥{stats.get('monthly_total', 0):.0f}"
            f" | 24h 同类 {stats.get('same_category_count_24h', 0)} 次"
        )

        system = self._build_system_prompt_for_event(event, scene)
        messages = [ChatMessage(role="system", content=system)]
        text = (await self.llm.chat(messages, stream=False)).strip()
        return text or self._default_chat_reaction(p)

    async def _render_spending_monthly(self, event: VoiceEvent) -> str:
        """月度消费点评（2-3 句）。"""
        p = event.payload
        total = p.get("total", 0)
        by_category = p.get("by_category", {})
        top_items = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        detail_lines = [f"  {cat}: ¥{amt:.0f}" for cat, amt in top_items]

        scene = (
            f"## 当前场景：月度消费统计\n\n"
            f"用阿玖的语气点评一下本月消费（2-3 句）。\n\n"
            f"本月总额：¥{total:.0f}\n"
            f"分类明细：\n" + "\n".join(detail_lines)
        )

        system = self._build_system_prompt_for_event(event, scene)
        messages = [ChatMessage(role="system", content=system)]
        text = (await self.llm.chat(messages, stream=False)).strip()
        return text or self._default_monthly_comment(p)

    # ---- 兜底模板 ----

    @staticmethod
    def _default_reaction(payload: dict) -> str:
        category = payload.get("category", "其他")
        amount = payload.get("amount", 0)
        templates = {
            "餐饮": f"又花了{amount:.0f}？行吧。",
            "交通": "出行费记下了。",
            "烟酒": f"{amount:.0f}块。……算了不说了。",
            "购物": f"买了{amount:.0f}。开心就好。",
            "娱乐": "玩得开心~",
            "其他": f"记下了，{amount:.0f}元。",
        }
        return templates.get(category, f"记下了。")

    @staticmethod
    def _default_chat_reaction(payload: dict) -> str:
        category = payload.get("category", "其他")
        amount = payload.get("amount", 0)
        templates = {
            "烟酒": (
                f"又买烟酒花了{amount:.0f}块……上个月你在这上面花的钱都快能买Switch了。"
                f"不是说不买了嘛？算了，我记下了，你自己看着办。"
            ),
            "购物": (
                f"买了{amount:.0f}。不过你最近买东西有点频繁哦，"
                f"要不要看看这个月账单？"
            ),
            "娱乐": f"{amount:.0f}块娱乐消费。玩得开心就好，不过别忘了正事。",
            "餐饮": f"又吃了{amount:.0f}。吃好喝好，别老吃外卖。",
            "交通": f"出行花了{amount:.0f}。记下了。",
            "其他": f"花了{amount:.0f}，记上啦。不过这笔是什么？说清楚点。",
        }
        return templates.get(category, f"记下了{amount:.0f}元。记得看看这个月花多少了。")

    @staticmethod
    def _default_monthly_comment(payload: dict) -> str:
        total = payload.get("total", 0)
        return f"这个月花了{total:.0f}。你自己看着办吧。"
