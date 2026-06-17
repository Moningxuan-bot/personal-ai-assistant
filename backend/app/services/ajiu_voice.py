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
import re
from dataclasses import dataclass, field
from enum import StrEnum

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
        # 客服语气
        "很高兴为您服务",
        "请问还有什么可以帮您",
        "请问有什么需要帮助的吗",
        "有什么可以帮助您的",
        "您的问题已记录",
        "已收到您的请求",
        # 非阿玖自称
        "我是AI",
        "我是人工智能",
        "我是AI助手",
        "作为AI",
        "作为一个人工智能",
        # 记账场景禁词
        "算笔账",
        "储蓄账户",
        "存进储蓄",
        "联名",
        "VIP",
        "建议您",
        "已记录您的消费",
        "消费流水号",
        "确认收到",
    }

    # 额外检查子串：包含以下任意词即标记
    BANNED_SUBSTRINGS: list[str] = [
        "您", "算笔账", "储蓄", "联名", "VIP",
        "建议您", "消费流水", "已记录",
        "宝贝", "亲爱的", "主人",
        "肺癌", "折寿", "减寿", "短命",
        "你配吗", "慢性自残", "烟渍", "破风箱", "止咳糖浆",
    ]

    MAX_LENGTH = 600
    MAX_SPENDING_LENGTH = 80
    MAX_SPENDING_SENTENCES = 2
    MIN_LENGTH = 2
    MAX_QUESTION_RATIO = 0.35

    @classmethod
    def validate(cls, text: str, event_type: AjiuEventType | None = None) -> ValidationResult:
        issues: list[str] = []

        # 1. 禁止用词（客服语气 / 非阿玖式自称 / 记账场景禁词）
        for phrase in cls.BANNED_PHRASES:
            if phrase in text:
                issues.append(f"包含客服/非阿玖语气: 「{phrase}」")

        # 1b. 禁止子串（更短的关键词）
        for sub in cls.BANNED_SUBSTRINGS:
            if sub in text:
                issues.append(f"包含禁止词: 「{sub}」")

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
            has_confirm = any(w in text for w in ("记下", "记上", "记了", "记住", "知道了", "行吧", "行了", "好嘞"))
            if not has_confirm:
                issues.append("记账回复缺少确认词（应含：记下了/行吧/知道了 等）")
            if len(text) > cls.MAX_SPENDING_LENGTH:
                issues.append(
                    f"记账回复过长: {len(text)} 字 (上限 {cls.MAX_SPENDING_LENGTH})"
                )
            sentence_count = len(
                [s for s in re.split(r"[。！？!?]+", text) if s.strip()]
            )
            if sentence_count > cls.MAX_SPENDING_SENTENCES:
                issues.append(
                    f"记账回复句子过多: {sentence_count} 句 "
                    f"(上限 {cls.MAX_SPENDING_SENTENCES})"
                )

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
            return self._get_fallback(event)

        # 输出校验
        result = self.validator.validate(text, event.event_type)
        if not result.passed:
            logger.warning(
                f"Validation FAILED for {event.event_type.value}: "
                f"{'; '.join(result.issues)} | text={text[:120]}..."
                f" → falling back to safe template"
            )
            return self._get_fallback(event)

        return text

    def _get_renderer(self, event_type: AjiuEventType):
        """事件类型 → 渲染器映射。"""
        renderers = {
            AjiuEventType.SPENDING_REACTION: self._render_spending_reaction,
            AjiuEventType.SPENDING_MONTHLY_COMMENT: self._render_spending_monthly,
        }
        if event_type in renderers:
            return renderers[event_type]
        raise ValueError(f"Unknown event type: {event_type}")

    def _get_fallback(self, event: VoiceEvent) -> str:
        """LLM 不可用时的兜底模板。"""
        fallbacks = {
            AjiuEventType.SPENDING_REACTION: self._default_reaction,
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

    # 记账确认的硬约束。所有记账反应统一走这里——短确认，不写小作文。
    _SPENDING_STYLE_RULES = (
        "## 铁律——违反一条就不是阿玖\n\n"
        "### 绝对禁止词（出现即失败）：\n"
        "您、宝贝、亲爱的、主人、算笔账、储蓄、账户、投资、年化、联名、VIP、"
        "肺癌、死亡、折寿、减寿、短命、救命、你配吗、建议您、消费流水、确认收到、已记录、"
        "肺、奖励、老猫、奶茶\n\n"
        "### 格式硬约束：\n"
        "1. 最多 2 句，总共不超过 80 字\n"
        "2. 必须包含确认词：「记下了」「行吧」「知道了」「嗯记了」至少一个\n"
        "3. 用「你」不用「您」。口语化短句\n"
        "4. 这不是聊天、不是说教、不是写段子——就是记账确认，带一点阿玖味道\n\n"
        "### 反面教材（永远别这么写）：\n"
        "❌ 我真想给您额头贴个联名VIP贴纸\n"
        "❌ 咱算笔账：一天一包20，一年7300\n"
        "❌ 建议您把这钱存进储蓄账户\n"
        "❌ 我每天发你张肺癌警示图\n"
        "❌ 这频率你肺在喊救命\n"
        "❌ 你是想把肺腌入味还是给烟草公司冲业绩\n\n"
        "### 正确范例：\n"
        "✅ 又买烟了。行吧，记下了。\n"
        "✅ 啧，又抽。上次不是说要戒吗？算了，记了。\n"
        "✅ 烟酒88。这个月第5次了……知道了，月底自己看。\n"
    )

    async def _render_spending_reaction(self, event: VoiceEvent) -> str:
        """卡片级消费吐槽（1-2 句）。"""
        p = event.payload
        stats = p.get("stats", {})

        scene = (
            f"用户刚记了一笔消费：{p['category']} ¥{p['amount']:.0f}"
            f"{'，备注：' + p['note'] if p.get('note') else ''}\n"
            f"（当月同类 {stats.get('same_category_count_month', 0)} 次"
            f" / 本月累计 ¥{stats.get('monthly_total', 0):.0f}）\n\n"
            f"给一个简短吐槽，1-2 句，不超过 80 字，必须包含确认词。\n"
            + self._SPENDING_STYLE_RULES
        )

        system = self._build_system_prompt_for_event(event, scene)
        messages = [ChatMessage(role="system", content=system)]
        text = (await self.llm.chat(messages, stream=False)).strip()
        return text or self._default_reaction(p)

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
            "烟酒": f"烟酒{amount:.0f}块，记下了。……算了不说了。",
            "购物": f"买了{amount:.0f}。开心就好。",
            "娱乐": "玩得开心~",
            "其他": f"记下了，{amount:.0f}元。",
        }
        return templates.get(category, f"记下了。")

    @staticmethod
    def _default_monthly_comment(payload: dict) -> str:
        total = payload.get("total", 0)
        return f"这个月花了{total:.0f}。你自己看着办吧。"
