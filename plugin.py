"""按需路由写作规则，普通聊天不注入任何额外提示。"""

from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from typing import Any

from maibot_sdk import Field, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder


class PluginSectionConfig(PluginConfigBase):
    enabled: bool = Field(default=True, description="是否启用写作风格路由")
    config_version: str = Field(default="1.0.0", description="配置版本")


class RoutingConfig(PluginConfigBase):
    max_prompt_characters: int = Field(default=5200, ge=1000, le=10000, description="本轮最多注入的规则字数")
    default_mode: str = Field(default="auto", description="自动识别模式")


class SemanticConfig(PluginConfigBase):
    enabled: bool = Field(default=True, description="对疑似写作请求启用 AI 语义补判")
    model: str = Field(default="utils", description="语义分类使用的模型任务")
    timeout_seconds: float = Field(default=4.0, ge=1.0, le=10.0, description="语义分类最长等待时间")


class HumanizerConfig(PluginConfigBase):
    enabled: bool = Field(default=True, description="回复后启用活人感审核")
    model: str = Field(default="utils", description="活人感审核使用的模型任务")
    timeout_seconds: float = Field(default=125.0, ge=2.0, le=125.0, description="活人感审核最长等待时间")
    min_characters: int = Field(default=12, ge=4, le=100, description="低于此长度的回复直接跳过审核")


class StylesConfig(PluginConfigBase):
    modern: bool = Field(default=True, description="启用现代口语写作规则")
    comedy_web: bool = Field(default=True, description="启用搞笑网文规则")
    acg_light_novel: bool = Field(default=True, description="启用日系 ACG 轻小说规则")
    anti_cliche: bool = Field(default=True, description="启用反八股规则")
    character_lifelike: bool = Field(default=True, description="启用人物生活化规则")
    review: bool = Field(default=True, description="启用评文规则")


class PluginConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    humanizer: HumanizerConfig = Field(default_factory=HumanizerConfig)
    styles: StylesConfig = Field(default_factory=StylesConfig)


BASE = """当前请求进入写作专用模式。只把下面规则用于本轮输出，不要复述规则本身。
先确认题材、视角、人物关系和目标，再直接写或评，不把所有风格硬套在一起。
优先让对白和具体细节呈现人物，长短句自然交替；少用模板化的情绪标签、语气解释和空泛总结。描写只记录对内容有用的现场信息，避免重复套路动作和机器式分点。人物先是完整的人，职业只是背景，只有情境需要时才使用职业术语。
"""

STYLES = {
    "modern": """现代口语与对白驱动：表达松弛、具体、有生活感，允许停顿、找补、岔题和自我修正。让角色通过自己说的话显出性格，少写长篇环境说明；对白占主要篇幅，但句子完整自然，不为追求网感强行堆梗。""",
    "comedy_web": """搞笑网文：保持事件推进清楚，用反差、夸张结果和接地气的吐槽制造笑点。梗、网络词和轻度自嘲按角色声纹适量使用，笑点服务人物与情节，不把每句话都写成段子，也不让旁白解释对白的笑点。""",
    "acg_light_novel": """日系 ACG 轻小说：仅在用户明确点名时使用高对白密度、漫画式节奏、适量漫符、脑内吐槽和二次元词汇。可以单句成段和快速切镜，但不强制夸张肢体、不机械添加弹幕、不混入与题材冲突的词库；优先保持角色辨识度和场景连贯。""",
    "anti_cliche": """反八股：避免套话、空泛比喻、诗化情绪、重复的咬唇攥拳指尖泛白等动作，以及“带着某种语气”“仿佛……如同……”式解释。情绪用角色当下说的话、选择和可见反应呈现；不要用否定句绕弯强调，不写提示词、变量名或幕后分析。""",
    "character_lifelike": """人物生活化：角色首先是普通人，有疲惫、偏好、常识、缺点和偶尔失误。职业和身份只在相关场景影响表达，日常聊天说人话，不把生活写成流程图、客服话术或专业报告；强势、理智、病娇等特质都通过具体关系和选择表现，不升级成控制或暴力模板。""",
    "review": """评文模式：不要改写成故事，也不要角色扮演。先限定当前看到的材料，再指出具体有效之处；随后按影响程度指出对白、节奏、视角、人物声纹、逻辑或陈词滥调问题，每条配一条可执行改法。区分确定问题与个人偏好，结论简洁但要有文本依据。""",
}

WRITE_MARKERS = ("写一段", "写几段", "写个", "创作", "续写", "改写", "改成", "改为", "写成", "变成", "重写", "润色", "扩写", "仿写", "生成片段", "文风示例", "示例文本", "小说")
REVIEW_MARKERS = ("评文", "点评", "看看这段", "这段有什么问题", "哪里有问题", "分析文风", "帮我看文", "帮我看看文")
SESSION_CACHE_LIMIT = 512
SEMANTIC_CANDIDATE_MARKERS = ("这段", "文章", "正文", "小说", "文风", "写", "改", "续", "润色", "示例", "看看", "评")
HUMANIZER_SYSTEM_PROMPT = """你是群聊回复的活人感审核助手。只改措辞，不改原回复表达的事实、结论、数字、时间、人名、专有名词、链接、路径、代码、命令或茶茶的核心态度。
去掉明显的客服腔、模板化开场、过度礼貌、机械总结、重复句式、空泛拔高、假装深刻和生硬的过渡。保留自然的口语、停顿、轻微不完整、网络表达和适度玩笑，但不要强行加梗、emoji、第一人称或新信息。
如果原文已经自然，原样输出。只输出最终回复，不要解释、引号、前缀或代码块。"""


def _flatten(value: Any, limit: int = 6000) -> str:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, dict):
        return " ".join(_flatten(v, 800) for v in value.values())[:limit]
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v, 800) for v in value)[:limit]
    try:
        return json.dumps(value, ensure_ascii=False)[:limit]
    except (TypeError, ValueError):
        return str(value)[:limit]


def _message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    for key in ("processed_plain_text", "plain_text", "text"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:6000]
    return ""


class WritingStyleRouterPlugin(MaiBotPlugin):
    config_model = PluginConfig

    async def on_load(self) -> None:
        self._session_queries: OrderedDict[str, str] = OrderedDict()
        self._semantic_tasks: dict[str, asyncio.Task[Any]] = {}
        self.ctx.logger.info("写作风格路由插件已加载")

    async def on_unload(self) -> None:
        self._session_queries.clear()
        for task in self._semantic_tasks.values():
            task.cancel()
        self._semantic_tasks.clear()

    async def on_config_update(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self._session_queries.clear()
        for task in self._semantic_tasks.values():
            task.cancel()
        self._semantic_tasks.clear()

    @HookHandler(
        "chat.receive.before_process",
        name="observe_writing_request",
        description="缓存本轮用户原消息，供写作风格路由识别。",
        mode=HookMode.OBSERVE,
        order=HookOrder.EARLY,
        timeout_ms=500,
        error_policy=ErrorPolicy.SKIP,
    )
    async def observe_writing_request(self, message: Any = None, **kwargs: Any) -> None:
        del kwargs
        if not self.config.plugin.enabled or not isinstance(message, dict):
            return None
        session_id = str(message.get("session_id") or "").strip()
        text = _message_text(message)
        if not session_id or not text or text.startswith("/"):
            return None
        self._session_queries[session_id] = text
        self._session_queries.move_to_end(session_id)
        if self.config.semantic.enabled and any(marker in text for marker in SEMANTIC_CANDIDATE_MARKERS):
            old_task = self._semantic_tasks.pop(session_id, None)
            if old_task is not None:
                old_task.cancel()
            self._semantic_tasks[session_id] = asyncio.create_task(self._classify_semantically(text))
        while len(self._session_queries) > SESSION_CACHE_LIMIT:
            self._session_queries.popitem(last=False)
        return None

    @HookHandler(
        "maisaka.replyer.before_request",
        name="route_writing_style",
        description="按明确的写作或评文意图注入对应规则。",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
        timeout_ms=800,
        error_policy=ErrorPolicy.SKIP,
    )
    async def route_writing_style(
        self,
        session_id: str = "",
        extra_prompt: str = "",
        reply_reason: str = "",
        reply_tool_args: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        del kwargs
        if not self.config.plugin.enabled:
            return None
        user_query = self._session_queries.get(session_id, "")
        query = _flatten((user_query, reply_reason, reply_tool_args))
        if not query:
            return None
        is_review = any(marker in query for marker in REVIEW_MARKERS) and self.config.styles.review
        is_writing = any(marker in query for marker in WRITE_MARKERS)
        semantic = None if is_review or is_writing else await self._get_semantic_result(session_id)
        if not is_review and not is_writing and semantic is not None:
            is_review = semantic.get("intent") == "review" and self.config.styles.review
            is_writing = semantic.get("intent") == "write"
        if not is_review and not is_writing:
            return None

        selected: list[str] = []
        if is_review:
            selected.append("review")
        else:
            selected.append("modern")
        if any(marker in query for marker in ("搞笑网文", "梗小鬼", "网感", "沙雕", "反差搞笑")) and self.config.styles.comedy_web:
            selected.append("comedy_web")
        if any(marker in query for marker in ("轻小说", "日系", "ACG", "二次元", "漫画感", "瀑布流")) and self.config.styles.acg_light_novel:
            selected.append("acg_light_novel")
        if semantic is not None:
            for style_name in semantic.get("styles", []):
                if style_name in {"comedy_web", "acg_light_novel"} and style_name not in selected:
                    if style_name == "comedy_web" and self.config.styles.comedy_web:
                        selected.append(style_name)
                    if style_name == "acg_light_novel" and self.config.styles.acg_light_novel:
                        selected.append(style_name)
        if self.config.styles.anti_cliche:
            selected.append("anti_cliche")
        if self.config.styles.character_lifelike:
            selected.append("character_lifelike")

        prompt = BASE + "\n".join(STYLES[name] for name in selected if name in STYLES)
        prompt = prompt[: self.config.routing.max_prompt_characters]
        combined = "\n\n".join(item for item in (str(extra_prompt or "").strip(), prompt) if item)
        self.ctx.logger.debug("写作风格路由命中：mode=%s styles=%s chars=%s", "review" if is_review else "write", selected, len(prompt))
        return {"action": "continue", "modified_kwargs": {"extra_prompt": combined}}

    async def _classify_semantically(self, text: str) -> dict[str, Any] | None:
        prompt = (
            "你是写作请求路由器。只分析下面这条用户消息，不回答它。\n"
            "返回严格 JSON：{\"intent\":\"write|review|none\",\"styles\":[\"comedy_web\"或\"acg_light_novel\"]}。\n"
            "write 仅表示用户要创作、续写、改写、润色或示例；review 表示用户要点评、评文或分析文本。"
            "普通聊天、技术排错、泛泛讨论返回 none。只有用户明确要求时才填 style。\n"
            f"用户消息：{text[:3000]}"
        )
        try:
            result = await self.ctx.llm.generate(
                prompt=prompt,
                model=self.config.semantic.model,
                temperature=0.0,
                max_tokens=120,
            )
            if isinstance(result, dict) and isinstance(result.get("result"), dict):
                result = result["result"]
            response = str(result.get("response", "") if isinstance(result, dict) else "").strip()
            start, end = response.find("{"), response.rfind("}")
            if start < 0 or end <= start:
                return None
            data = json.loads(response[start : end + 1])
            intent = data.get("intent")
            if intent not in {"write", "review", "none"}:
                return None
            styles = data.get("styles", [])
            return {"intent": intent, "styles": [s for s in styles if s in {"comedy_web", "acg_light_novel"}]}
        except (asyncio.TimeoutError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.ctx.logger.debug("写作语义分类跳过：%s", exc)
            return None

    async def _get_semantic_result(self, session_id: str) -> dict[str, Any] | None:
        task = self._semantic_tasks.pop(session_id, None)
        if task is None:
            return None
        try:
            return await asyncio.wait_for(task, timeout=self.config.semantic.timeout_seconds)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
            return None

    @HookHandler(
        "maisaka.replyer.after_response",
        name="humanize_response",
        description="回复发送前用小模型清理明显 AI 腔，保持原意和事实不变。",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
        timeout_ms=10000,
        error_policy=ErrorPolicy.SKIP,
    )
    async def humanize_response(self, response: str = "", **kwargs: Any) -> dict[str, Any] | None:
        del kwargs
        if not self.config.plugin.enabled or not self.config.humanizer.enabled:
            return None
        original = str(response or "").strip()
        if len(original) < self.config.humanizer.min_characters or "```" in original:
            return None
        try:
            result = await asyncio.wait_for(
                self.ctx.llm.generate(
                    [
                        {"role": "system", "content": HUMANIZER_SYSTEM_PROMPT},
                        {"role": "user", "content": f"原回复：\n{original[:6000]}"},
                    ],
                    model=self.config.humanizer.model,
                    temperature=0.15,
                    max_tokens=min(12000, max(160, len(original) * 2)),
                ),
                timeout=self.config.humanizer.timeout_seconds,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError, OSError, TypeError, ValueError) as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            self.ctx.logger.debug("活人感审核跳过：%s", exc)
            return None
        if isinstance(result, dict) and isinstance(result.get("result"), dict):
            result = result["result"]
        if not isinstance(result, dict) or not result.get("success"):
            return None
        rewritten = str(result.get("response") or "").strip()
        if not rewritten or "```" in rewritten:
            return None
        ratio = len(rewritten) / len(original)
        if ratio < 0.55 or ratio > 1.45:
            self.ctx.logger.debug("活人感审核输出长度异常，保留原回复：%.2f", ratio)
            return None
        if rewritten == original:
            return None
        return {"action": "continue", "modified_kwargs": {"response": rewritten}}


def create_plugin() -> WritingStyleRouterPlugin:
    return WritingStyleRouterPlugin()
