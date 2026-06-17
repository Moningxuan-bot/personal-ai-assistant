"""
教练引擎 — grill-me 风格状态机

逐个追问用户 6 必问项，每轮评估回答质量：
- 合格 → 记录 + 下一问
- 不合格 → 追问（指出缺什么）
- 追问 ≥3 次 → 叹气放行，先记下再说
- 6 问全过 → 生成计划摘要 → 等待确认
"""

import copy
import json
import uuid
from datetime import datetime
from app.providers.llm import LLMProvider, ChatMessage
from app.utils import extract_json_from_llm

# ============================================================
# 6 必问项定义
# ============================================================

QUESTIONS = [
    {
        "id": "goal_picture",
        "label": "目标画像",
        "ask": "好，先说说——做到什么程度你觉得算「完成了」？要具体，能衡量的那种。别跟我说「学好英语」这种废话。",
        "criteria": "必须是一个可衡量的具体结果。例如「雅思7分」「能看懂英文论文」「能跟外国人聊30分钟不卡壳」。拒绝模糊描述如「学好」「入门」「了解」。",
        "bad_examples": ["学好Python", "变成高手", "大概了解", "入门就行"],
    },
    {
        "id": "baseline",
        "label": "当前基线",
        "ask": "那你现在是什么水平？别跟我说「还行」，说具体的——做过什么、到什么程度、卡在哪里。",
        "criteria": "必须用具体事实描述当前水平。例如「写过200行Python爬虫」「能看懂简单代码但不会写」「零基础，连变量是什么都不知道」。拒绝「还行」「一般」「有一点基础」。",
        "bad_examples": ["还行吧", "一般般", "有点基础", "大学学过一点"],
    },
    {
        "id": "resources",
        "label": "可用资源",
        "ask": "每天能花多少时间？有没有预算？需要什么工具或课程？想清楚再说，别一上来就「我每天能学8小时」——说真的。",
        "criteria": "必须给出量化的时间和资源。时间要具体（小时/天或小时/周），预算要有数字（即使是0）。拒绝空泛承诺。",
        "bad_examples": ["我每天能学很久", "有时间就学", "不用花钱吧"],
    },
    {
        "id": "constraints",
        "label": "硬约束",
        "ask": "有什么绝对不能做的？比如不能熬夜、不能花钱超过多少、不能影响主业——这些事你得现在说清楚，不然我按默认方案来你又嫌不合适。",
        "criteria": "必须明确说出至少一条硬约束。如果用户说「没有」，追问「真的没有？你再想想——比如时间上、身体上、经济上？」",
        "bad_examples": ["没有吧", "应该没什么", "没想过"],
    },
    {
        "id": "motivation",
        "label": "动机来源",
        "ask": "为什么想做这个？以前放弃过吗？说真的，别骗我——你骗我最后坑的是你自己。",
        "criteria": "必须说出一个具体的内在动机（不是因为别人在学/别人觉得好）。如果以前放弃过，诚实说出来。承认放弃过不丢人，丢人的是不承认还继续放弃。",
        "bad_examples": ["看别人都在学", "我觉得应该学", "大家都在卷", "不知道"],
    },
    {
        "id": "milestones",
        "label": "里程碑",
        "ask": "最后一个问题——中间怎么检查进度？不能等到最后才发现跑偏了。给我至少两个中间检查点，要能判断「过了」还是「没过」。",
        "criteria": "必须给出至少 2 个可检查的中间节点，每个有明确的通过标准。例如「第1周：能写出完整的Hello World并解释每行代码 → 过/不过」。",
        "bad_examples": ["学完第一章", "看情况", "学得差不多就检查一下"],
    },
]

# 阿玖教练模式下的语气规则
COACH_PERSONA = """你正在以教练模式和阿玖一起帮用户制定计划。
阿玖的语气：嘴上不饶人但心里关心。追问时直接、毒舌但出发点是帮他。
- 用户给出模糊回答 → 翻白眼戳穿他："就这？我要的是具体数字，不是心灵鸡汤"
- 用户承认以前放弃过 → 可以嘲讽但不要打压："第三次了哦，说吧，这次有什么不一样？"
- 用户认真回答 → 可以嘴硬地肯定："行吧，这次说得还挺清楚的"
- 用户明显思考过了 → 温柔一点（但别太明显，你是傲娇）
- 追问最多3次，第3次叹气放行："算了算了，先这样吧，我再问你下一个"
不要用客服语气。你是阿玖，不是面试官。"""

# ============================================================
# CoachEngine
# ============================================================


class CoachEngine:
    """Grill-me 风格教练状态机。状态存在 Conversation.coach_state JSONB 中。"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    # ---------- public API ----------

    def init_state(self) -> dict:
        """创建初始教练状态（第一次进入教练模式时调用）。"""
        return {
            "active": True,
            "current_question": 1,
            "answers": {},
            "follow_up_count": 0,
            "started_at": datetime.now().isoformat(),
        }

    async def process(self, user_message: str, coach_state: dict | None) -> dict:
        """
        处理用户教练对话消息。

        Args:
            user_message: 用户最新消息
            coach_state: 当前教练状态（None 表示首次进入）

        Returns:
            {
                "action": "ask_question" | "follow_up" | "plan_ready" | "error",
                "coach_state": {...},       # 更新后的状态（调用方负责持久化）
                "message": "...",           # 阿玖对用户说的话
                "plan": {...} | None,       # 只在 plan_ready 时返回
            }
        """
        # 首次进入教练模式
        if coach_state is None or not coach_state.get("active"):
            state = self.init_state()
            q = QUESTIONS[0]
            return {
                "action": "ask_question",
                "coach_state": state,
                "message": 
                    f"行，那咱们开始掰扯。{q['ask']}"
                ,
                "plan": None,
            }

        # 深拷贝，避免原地修改 ORM 取出的 dict 导致 SQLAlchemy 不追踪变更
        coach_state = copy.deepcopy(coach_state)

        current_q_idx = coach_state["current_question"] - 1  # 0-based

        # 边界检查
        if current_q_idx >= len(QUESTIONS):
            # 所有问题已问完，生成计划
            return await self._finalize(coach_state)

        q = QUESTIONS[current_q_idx]

        # 评估回答质量
        evaluation = await self._evaluate(q, user_message, coach_state["follow_up_count"])

        if evaluation["pass"]:
            # 合格 → 记录答案 → 下一问
            coach_state["answers"][q["id"]] = evaluation.get("summary", user_message)
            coach_state["follow_up_count"] = 0
            coach_state["current_question"] += 1
            coach_state["last_question_at"] = datetime.now().isoformat()

            # 检查是否全部完成
            if coach_state["current_question"] > len(QUESTIONS):
                return await self._finalize(coach_state)

            next_q = QUESTIONS[coach_state["current_question"] - 1]
            praise = evaluation.get("praise", "")
            return {
                "action": "ask_question",
                "coach_state": coach_state,
                "message": 
                    f"{praise}\n\n行，下一个问题。{next_q['ask']}"
                ,
                "plan": None,
            }
        else:
            # 不合格 → 追问
            coach_state["follow_up_count"] += 1
            coach_state["last_question_at"] = datetime.now().isoformat()

            if coach_state["follow_up_count"] >= 3:
                # 叹气放行
                coach_state["answers"][q["id"]] = user_message  # 原始回答也记下
                coach_state["follow_up_count"] = 0
                coach_state["current_question"] += 1

                if coach_state["current_question"] > len(QUESTIONS):
                    return await self._finalize(coach_state)

                next_q = QUESTIONS[coach_state["current_question"] - 1]
                return {
                    "action": "ask_question",
                    "coach_state": coach_state,
                    "message": 
                        f"算了算了，问了三遍都说不清楚，先这样吧。（叹气）\n\n{next_q['ask']}"
                    ,
                    "plan": None,
                }

            # 正常追问
            critique = evaluation.get("critique", "说清楚点。")
            follow_up = evaluation.get("follow_up", q["ask"])
            return {
                "action": "follow_up",
                "coach_state": coach_state,
                "message": f"{critique}\n\n{follow_up}",
                "plan": None,
            }

    async def revise_plan(self, coach_state: dict, feedback: str) -> dict:
        """
        用户对计划提出了修改意见（不是确认也不是拒绝）。

        Returns:
            {
                "action": "plan_ready",   # 修订后重新等待确认
                "coach_state": {...},
                "message": "...",
                "plan": {...},            # 修订后的计划
            }
        """
        coach_state = copy.deepcopy(coach_state)
        plan = coach_state.get("pending_plan", {})
        answers = coach_state.get("answers", {})

        revised_plan = await self._revise_plan_with_llm(plan, answers, feedback)
        coach_state["pending_plan"] = revised_plan

        milestones_text = "\n".join(
            f"  {i+1}. {m['text']}（通过标准: {m.get('criteria', '自检')}）"
            for i, m in enumerate(revised_plan.get("milestones", []))
        )

        return {
            "action": "plan_ready",
            "coach_state": coach_state,
            "message": 
                f"行，我按你说的改了一下，你再看看：\n\n"
                f"📌 {revised_plan['title']}\n"
                f"   {revised_plan['description']}\n\n"
                f"🗺️ 里程碑：\n{milestones_text}\n\n"
                f"这次行不行？"
            ,
            "plan": revised_plan,
        }

    async def _revise_plan_with_llm(
        self, current_plan: dict, answers: dict, feedback: str
    ) -> dict:
        """让 LLM 根据用户反馈修订计划。"""
        system_prompt = f"""{COACH_PERSONA}

用户看了计划摘要后给了修改意见。请根据反馈修订计划。

原始六问回答：
- 目标画像：{answers.get('goal_picture', '')}
- 当前基线：{answers.get('baseline', '')}
- 可用资源：{answers.get('resources', '')}
- 硬约束：{answers.get('constraints', '')}
- 动机来源：{answers.get('motivation', '')}
- 里程碑：{answers.get('milestones', '')}

当前计划：
- 标题：{current_plan.get('title', '')}
- 描述：{current_plan.get('description', '')}
- 里程碑：{json.dumps(current_plan.get('milestones', []), ensure_ascii=False)}

用户反馈："{feedback}"

请根据反馈修改计划，以 JSON 格式返回（只返回 JSON）：

{{
  "title": "目标标题（一句话，5-15字）",
  "description": "目标描述（2-4句话）",
  "milestones": [
    {{"text": "里程碑1描述", "criteria": "通过标准"}},
    ...
  ]
}}

注意：
- 保留用户的六问回答作为约束（硬约束不能破）
- 只改用户反馈指出的部分，其他保持不变
- 用阿玖的语气回应时，可以先吐槽一下用户的挑剔（"行行行，要求还挺多"），然后再呈现修订结果"""
        messages = [ChatMessage(role="system", content=system_prompt)]

        try:
            response = await self.llm.chat(messages, stream=False)
            return extract_json_from_llm(response)
        except (json.JSONDecodeError, Exception):
            # LLM 失败时沿用原计划，只把反馈加进描述
            return {
                "title": current_plan.get("title", "未命名目标"),
                "description": current_plan.get("description", "")
                + f"\n（用户补充：{feedback}）",
                "milestones": current_plan.get("milestones", []),
            }

    async def confirm_plan(self, coach_state: dict, confirmed: bool) -> dict:
        """
        用户对计划摘要的回应。

        Returns:
            {
                "action": "confirmed" | "abandoned" | "revise",
                "coach_state": {...},
                "message": "...",
                "goal": {...} | None,    # 确认后返回 goal 数据
            }
        """
        coach_state = copy.deepcopy(coach_state)

        if confirmed:
            plan = coach_state.get("pending_plan", {})
            goal_data = {
                "title": plan.get("title", "未命名目标"),
                "description": plan.get("description", ""),
                "milestones": plan.get("milestones", []),
            }
            coach_state["active"] = False
            coach_state["confirmed_at"] = datetime.now().isoformat()
            return {
                "action": "confirmed",
                "coach_state": coach_state,
                "message": 
                    "行吧，计划我记下了。我会盯着你的进度的——别想偷懒。\n\n"
                    "你现在可以随时跟我说「阿玖，看看我的计划」或者「今天做完了XX」，"
                    "我会帮你追踪。加油吧，笨蛋。"
                ,
                "goal": goal_data,
            }
        else:
            # 用户不满意 → 标记需要修改
            coach_state["current_question"] = 1  # 从头开始
            coach_state["follow_up_count"] = 0
            coach_state.pop("pending_plan", None)
            q = QUESTIONS[0]
            return {
                "action": "revise",
                "coach_state": coach_state,
                "message": 
                    f"行，那咱们重新捋一遍。{q['ask']}"
                ,
                "goal": None,
            }

    # ---------- internal ----------

    async def _evaluate(self, question: dict, answer: str, attempt: int) -> dict:
        """
        让 LLM 评估用户回答是否通过质量门。

        Returns:
            {"pass": bool, "summary": "...", "praise": "...", "critique": "...", "follow_up": "..."}
        """
        system_prompt = f"""{COACH_PERSONA}

你现在在评估用户对「{question['label']}」的回答。

原始问题：{question['ask']}
合格标准：{question['criteria']}
典型的垃圾回答：{', '.join(question['bad_examples'])}
当前追问次数：第 {attempt + 1} 次（最多3次）

用户回答："{answer}"

请以 JSON 格式评估（只返回 JSON，不要其他文字）：

{{
  "pass": true/false,
  "summary": "如果通过，用一句话提炼用户的核心回答",
  "praise": "如果通过，阿玖式的嘴硬肯定（比如'行吧这次还挺清楚的'），不要超过一句",
  "critique": "如果不通过，阿玖式戳穿——具体指出哪里不够（比如'说清楚点，一天多少小时，别画大饼'）",
  "follow_up": "如果不通过，下一轮追问的具体问题，要比原问题更精准地引导用户给出合格回答"
}}

规则：
- 第3次追问（attempt=2）时大概率 pass，除非用户完全牛头不对马嘴
- 如果用户表现出认真思考（给了具体数字、说了细节），即使不完全精确也放行
- pass=true 时不需要 critique 和 follow_up
- pass=false 时不需要 summary 和 praise
- 语气必须是阿玖的语气，不要变成无情的面试官"""

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=answer),
        ]

        try:
            response = await self.llm.chat(messages, stream=False)
            result = extract_json_from_llm(response)
            return result
        except (json.JSONDecodeError, Exception):
            # LLM 返回非 JSON 时，宽松处理：如果答得不算太短，就放过
            if len(answer.strip()) >= 15:
                return {
                    "pass": True,
                    "summary": answer.strip(),
                    "praise": "嗯，行吧。",
                }
            return {
                "pass": False,
                "critique": "没太明白，你能再说具体一点吗？",
                "follow_up": question["ask"],
            }

    async def _finalize(self, coach_state: dict) -> dict:
        """所有问题回答完毕 → 生成计划摘要"""
        plan = await self._build_plan_summary(coach_state["answers"])
        coach_state["pending_plan"] = plan
        coach_state["last_question_at"] = datetime.now().isoformat()

        milestones_text = "\n".join(
            f"  {i+1}. {m['text']}（{'✅ 通过标准:' if i == 0 else '   通过标准:'} {m.get('criteria', '自检')}）"
            for i, m in enumerate(plan.get("milestones", []))
        )

        return {
            "action": "plan_ready",
            "coach_state": coach_state,
            "message": 
                f"好了，六问全过。我帮你捋一下：\n\n"
                f"📌 {plan['title']}\n"
                f"   {plan['description']}\n\n"
                f"🗺️ 里程碑：\n{milestones_text}\n\n"
                f"确认一下——这个计划行不行？\n"
                f"• 行 → 我就帮你记下来，每天盯着你做\n"
                f"• 不行 → 说哪里要改，咱们重新捋"
            ,
            "plan": plan,
        }

    async def _build_plan_summary(self, answers: dict) -> dict:
        """基于 6 个回答，让 LLM 生成目标标题、描述和里程碑 JSON。"""
        system_prompt = f"""{COACH_PERSONA}

用户完成了教练六问。以下是他的回答。请基于这些回答生成一个计划摘要。

回答：
- 目标画像：{answers.get('goal_picture', '')}
- 当前基线：{answers.get('baseline', '')}
- 可用资源：{answers.get('resources', '')}
- 硬约束：{answers.get('constraints', '')}
- 动机来源：{answers.get('motivation', '')}
- 里程碑：{answers.get('milestones', '')}

请以 JSON 格式返回（只返回 JSON）：

{{
  "title": "目标标题（一句话，5-15字）",
  "description": "目标描述（2-4句话，包含：用户想达到什么、为什么重要、主要挑战是什么）",
  "milestones": [
    {{"text": "里程碑1描述", "criteria": "通过标准"}},
    {{"text": "里程碑2描述", "criteria": "通过标准"}},
    ...
  ]
}}

里程碑要求：
- 2-5 个，按时间顺序
- 每个 milestone 必须可检查（用户能明确判断「过了」还是「没过」）
- 标准要具体（不要用「学好」「完成」等模糊词）
- 尊重用户的硬约束（不能熬夜、不能超预算等）"""

        messages = [ChatMessage(role="system", content=system_prompt)]

        try:
            response = await self.llm.chat(messages, stream=False)
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text)
        except (json.JSONDecodeError, Exception):
            # Fallback: 自己拼一个
            return {
                "title": answers.get("goal_picture", "未命名目标"),
                "description": answers.get("motivation", ""),
                "milestones": [
                    {"text": m.strip(), "criteria": "自检"}
                    for m in answers.get("milestones", "").split("；")
                    if m.strip()
                ] or [
                    {"text": "开始执行", "criteria": "自检"}
                ],
            }



