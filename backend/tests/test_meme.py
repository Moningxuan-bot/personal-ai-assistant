import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from app.main import app
from app.models.database import get_db
from app.models.memory import Memory
from app.models.meme import Meme
from app.services.chat import ChatService
from app.services.meme import MemeService
from app.services.memory import MemoryService


@pytest.mark.anyio
async def test_meme_model_can_store_bilibili_item(db_session):
    """Meme 模型应能保存 B 站梗的基础信息和处理状态。"""
    meme = Meme(
        title="测试热梗",
        source="bilibili",
        url="https://www.bilibili.com/video/BV123",
        summary="阿玖版解释",
        tags="游戏,科技",
    )
    db_session.add(meme)
    await db_session.commit()

    assert meme.id is not None
    assert meme.kept is False
    assert meme.discarded is False
    assert meme.asked is False


@pytest.mark.anyio
async def test_get_preference_tags_extracts_unique_tags(db_session):
    """MemoryService 应从 preference 记忆中提取去重后的偏好标签。"""
    db_session.add_all(
        [
            Memory(content="用户喜欢游戏、科技和动漫", category="preference", embedding=[0.1] * 512),
            Memory(content="偏好标签：游戏, 鬼畜", category="preference", embedding=[0.2] * 512),
            Memory(content="用户住在北京", category="fact", embedding=[0.3] * 512),
        ]
    )
    await db_session.commit()

    service = MemoryService(db_session, embed_provider=None)
    tags = await service.get_preference_tags()

    assert "游戏" in tags
    assert "科技" in tags
    assert "动漫" in tags
    assert "鬼畜" in tags
    assert tags.count("游戏") == 1


@pytest.mark.anyio
async def test_fetch_bilibili_hot_parses_popular_api(db_session, monkeypatch):
    """MemeService 应解析 B 站热门 API，且测试不能真实联网。"""

    class FakeResponse:
        def json(self):
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "title": "赛博猫猫突然爆火",
                            "bvid": "BV1abc",
                            "tname": "科技",
                            "desc": "这是一段很长的简介",
                        }
                    ]
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.services.meme.httpx.AsyncClient", FakeClient)

    service = MemeService(db_session, llm=AsyncMock())
    memes = await service.fetch_bilibili_hot(limit=1)

    assert memes == [
        {
            "title": "赛博猫猫突然爆火",
            "url": "https://www.bilibili.com/video/BV1abc",
            "tags": "科技",
            "summary": "这是一段很长的简介",
        }
    ]


@pytest.mark.anyio
async def test_filter_rewrite_and_store_skips_discarded_memes(db_session):
    """LLM 过滤改写后应入库，并跳过用户已永久丢弃的梗。"""
    db_session.add(
        Meme(
            title="不想再看到的梗",
            source="bilibili",
            discarded=True,
            asked=True,
        )
    )
    await db_session.commit()

    llm = AsyncMock()
    llm.chat.return_value = """
[
  {"title": "赛博猫猫突然爆火", "url": "https://www.bilibili.com/video/BV1abc", "tags": "科技,游戏", "summary": "阿玖版：这猫火得比你计划坚持得久。"},
  {"title": "不想再看到的梗", "url": "https://www.bilibili.com/video/BVold", "tags": "其他", "summary": "应该被跳过"}
]
"""
    service = MemeService(db_session, llm=llm)

    saved = await service.filter_rewrite_and_store(
        [
            {"title": "赛博猫猫突然爆火", "url": "https://www.bilibili.com/video/BV1abc", "tags": "科技", "summary": "原始简介"},
            {"title": "不想再看到的梗", "url": "https://www.bilibili.com/video/BVold", "tags": "其他", "summary": "原始简介"},
        ],
        prefs=["科技", "游戏"],
    )

    assert len(saved) == 1
    assert saved[0].title == "赛博猫猫突然爆火"
    assert saved[0].asked is False
    assert saved[0].discarded is False


@pytest.mark.anyio
async def test_meme_keep_and_discard_api(db_session):
    """梗清理 API 应能保留或永久丢弃当天待处理梗。"""
    keep = Meme(title="留下的梗", source="bilibili")
    discard = Meme(title="丢掉的梗", source="bilibili")
    db_session.add_all([keep, discard])
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            today = await client.get(
                "/api/memes/today",
                headers={"X-Device-Token": "local-dev-secret"},
            )
            assert today.status_code == 200
            assert len(today.json()) == 2

            kept_resp = await client.post(
                f"/api/memes/{keep.id}/keep",
                headers={"X-Device-Token": "local-dev-secret"},
            )
            discarded_resp = await client.post(
                f"/api/memes/{discard.id}/discard",
                headers={"X-Device-Token": "local-dev-secret"},
            )

            assert kept_resp.status_code == 200
            assert kept_resp.json()["kept"] is True
            assert kept_resp.json()["asked"] is True
            assert discarded_resp.status_code == 200
            assert discarded_resp.json()["discarded"] is True
            assert discarded_resp.json()["asked"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_kept_memes_are_injected_into_casual_chat_prompt(db_session):
    """闲聊模式应把当天已保留的热梗注入 system prompt。"""
    db_session.add(
        Meme(
            title="赛博猫猫突然爆火",
            source="bilibili",
            summary="阿玖版：这猫火得比你计划坚持得久。",
            tags="科技,游戏",
            kept=True,
            asked=True,
        )
    )
    await db_session.commit()

    class FakeLLM:
        def __init__(self):
            self.stream_messages = None

        async def chat(self, messages, stream=False):
            if stream:
                self.stream_messages = messages

                async def gen():
                    yield "知道啦。"

                return gen()
            return ""

    llm = FakeLLM()
    embed = AsyncMock()
    embed.embed.return_value = [0.1] * 512
    service = ChatService(db_session, llm, MemoryService(db_session, embed))

    events = []
    async for event in service.chat("今天有什么好玩的？", None):
        events.append(event)

    system_prompt = llm.stream_messages[0].content
    assert "## 今天的热梗" in system_prompt
    assert "赛博猫猫突然爆火" in system_prompt
    assert "不要生硬地背诵" in system_prompt
    assert "热梗模式" in system_prompt  # MEME_PROMPT 已注入
