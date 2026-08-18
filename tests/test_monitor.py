from __future__ import annotations

from collections import defaultdict

import pytest

import main


class DeliveryContext:
    def __init__(self, outcomes=None):
        self.outcomes = defaultdict(list, outcomes or {})
        self.calls: list[str] = []

    async def send_message(self, umo, _chain):
        self.calls.append(umo)
        outcome = self.outcomes[umo].pop(0) if self.outcomes[umo] else True
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TimelineClient:
    def __init__(self, tweets):
        self.tweets = tweets
        self.closed = False

    async def get_recent_tweets(self, limit=100):
        return self.tweets[:limit]

    async def close(self):
        self.closed = True


class QueryClient:
    latest_tweet_id = "10"

    async def get_tweet(self, _position):
        return {
            "id": "10",
            "text": "test tweet",
            "created_at": "Sun Aug 16 07:28:38 +0000 2026",
            "lang": "zh",
        }

    async def get_recent_tweets(self, limit=1):
        return [{"id": "10"}][:limit]


class Event:
    def __init__(
        self,
        *,
        umo="session",
        sender="user",
        group="",
        admin=False,
        platform="aiocqhttp",
    ):
        self.unified_msg_origin = umo
        self._sender = sender
        self._group = group
        self._admin = admin
        self._platform = platform

    def get_sender_id(self):
        return self._sender

    def get_group_id(self):
        return self._group

    def is_admin(self):
        return self._admin

    def get_platform_name(self):
        return self._platform

    def plain_result(self, text):
        return text


def _plugin(context, **config):
    return main.TiboPlugin(
        context,
        {
            "translation_enabled": False,
            "push_enabled": True,
            **config,
        },
    )


@pytest.mark.asyncio
async def test_partial_delivery_advances_only_successful_session_and_retries():
    context = DeliveryContext(
        {
            "a": [True, True],
            "b": [False, True, True],
        }
    )
    plugin = _plugin(context)
    plugin._subscribers = {"a", "b"}
    plugin._subscriber_cursors = {"a": "1", "b": "1"}
    plugin._x_client = TimelineClient(
        [{"id": "3", "text": "three"}, {"id": "2", "text": "two"}, {"id": "1"}]
    )

    await plugin._poll_for_updates()
    assert plugin._subscriber_cursors == {"a": "3", "b": "1"}
    assert context.calls == ["a", "a", "b"]

    await plugin._poll_for_updates()
    assert plugin._subscriber_cursors == {"a": "3", "b": "3"}
    assert context.calls[-2:] == ["b", "b"]


@pytest.mark.asyncio
async def test_failed_second_message_persists_first_success_for_restart():
    context = DeliveryContext({"a": [True, RuntimeError("send failed")]})
    plugin = _plugin(context)
    plugin._subscribers = {"a"}
    plugin._subscriber_cursors = {"a": "1"}
    plugin._x_client = TimelineClient(
        [{"id": "3", "text": "three"}, {"id": "2", "text": "two"}, {"id": "1"}]
    )

    await plugin._poll_for_updates()
    assert plugin._subscriber_cursors["a"] == "2"

    restarted = _plugin(DeliveryContext())
    restarted._test_kv = plugin._test_kv.copy()
    await restarted._load_monitor_state()
    assert restarted._subscribers == {"a"}
    assert restarted._subscriber_cursors == {"a": "2"}


@pytest.mark.asyncio
async def test_broadcast_reports_false_and_exception():
    plugin = _plugin(
        DeliveryContext({"false": [False], "error": [RuntimeError("failed")]})
    )
    result = await plugin._broadcast("message", ("false", "error", "ok"))
    assert result == {"false": False, "error": False, "ok": True}


@pytest.mark.asyncio
async def test_missing_cursor_sets_baseline_without_sending_old_tweets():
    context = DeliveryContext()
    plugin = _plugin(context)
    plugin._subscribers = {"a"}
    plugin._subscriber_cursors = {"a": None}
    plugin._x_client = TimelineClient(
        [{"id": "3", "text": "three"}, {"id": "2", "text": "two"}]
    )

    await plugin._poll_for_updates()

    assert context.calls == []
    assert plugin._subscriber_cursors == {"a": "3"}
    assert plugin._test_kv[main.MONITOR_STATE_KEY]["subscriber_cursors"] == {"a": "3"}


@pytest.mark.asyncio
async def test_legacy_monitor_state_migrates_cursor_per_subscriber():
    plugin = _plugin(DeliveryContext())
    plugin._test_kv[main.MONITOR_STATE_KEY] = {
        "username": "thsottiaux",
        "subscribers": ["a", "b"],
        "last_seen_tweet_id": "42",
    }

    await plugin._load_monitor_state()

    assert plugin._subscribers == {"a", "b"}
    assert plugin._subscriber_cursors == {"a": "42", "b": "42"}


@pytest.mark.asyncio
async def test_group_subscription_requires_admin_and_cooldown_is_enforced():
    plugin = _plugin(DeliveryContext(), tibo_cooldown_seconds=30)
    member = Event(umo="group-session", sender="member", group="100", admin=False)
    admin = Event(umo="group-session", sender="admin", group="100", admin=True)

    assert plugin._can_manage_subscription(member) is False
    assert plugin._can_manage_subscription(admin) is True
    assert await plugin._command_cooldown_remaining("tibo", member, 30) == 0
    assert await plugin._command_cooldown_remaining("tibo", member, 30) > 0


@pytest.mark.asyncio
async def test_group_member_cannot_change_subscription_but_admin_can():
    plugin = _plugin(DeliveryContext())
    plugin._x_client = QueryClient()
    member = Event(umo="group-session", sender="member", group="100", admin=False)
    admin = Event(umo="group-session", sender="admin", group="100", admin=True)

    member_messages = [message async for message in plugin.tibo(member)]
    assert "群聊自动订阅仅允许 AstrBot 管理员开启" in member_messages[0]
    assert plugin._subscribers == set()

    admin_messages = [message async for message in plugin.tibo(admin)]
    assert "已为当前会话开启" in admin_messages[0]
    assert plugin._subscribers == {"group-session"}

    denied_stop = [message async for message in plugin.tibo_stop(member)]
    assert denied_stop == ["群聊自动订阅仅允许 AstrBot 管理员停止。"]
    assert plugin._subscribers == {"group-session"}

    allowed_stop = [message async for message in plugin.tibo_stop(admin)]
    assert allowed_stop == ["已停止当前会话的 @thsottiaux 新推文自动推送。"]
    assert plugin._subscribers == set()


@pytest.mark.asyncio
async def test_private_user_can_subscribe_and_stop():
    plugin = _plugin(DeliveryContext())
    plugin._x_client = QueryClient()
    event = Event(umo="private-session", sender="user")

    messages = [message async for message in plugin.tibo(event)]
    assert "已为当前会话开启" in messages[0]
    assert plugin._subscribers == {"private-session"}

    stopped = [message async for message in plugin.tibo_stop(event)]
    assert stopped == ["已停止当前会话的 @thsottiaux 新推文自动推送。"]
    assert plugin._subscribers == set()


@pytest.mark.asyncio
async def test_webchat_session_can_subscribe_and_stop():
    plugin = _plugin(DeliveryContext())
    plugin._x_client = QueryClient()
    event = Event(
        umo="webchat:FriendMessage:webchat!user!conversation",
        sender="user",
        platform="webchat",
    )

    messages = [message async for message in plugin.tibo(event)]
    assert "已为当前会话开启" in messages[0]
    assert "当前平台未声明支持主动推送" not in messages[0]
    assert plugin._subscribers == {event.unified_msg_origin}

    stopped = [message async for message in plugin.tibo_stop(event)]
    assert stopped == ["已停止当前会话的 @thsottiaux 新推文自动推送。"]
    assert plugin._subscribers == set()


@pytest.mark.asyncio
async def test_unsupported_platform_notice_appears_once_per_session():
    plugin = _plugin(DeliveryContext())
    plugin._x_client = QueryClient()
    first_event = Event(umo="discord-session", sender="first", platform="discord")
    same_session = Event(umo="discord-session", sender="second", platform="discord")
    other_session = Event(umo="other-session", sender="third", platform="discord")

    first_messages = [message async for message in plugin.tibo(first_event)]
    repeated_messages = [message async for message in plugin.tibo(same_session)]
    other_messages = [message async for message in plugin.tibo(other_session)]

    assert "当前平台未声明支持主动推送" in first_messages[0]
    assert "当前平台未声明支持主动推送" not in repeated_messages[0]
    assert "当前平台未声明支持主动推送" in other_messages[0]
    assert plugin._subscribers == set()


@pytest.mark.asyncio
async def test_busy_tibo_request_does_not_consume_cooldown():
    plugin = _plugin(DeliveryContext(), tibo_cooldown_seconds=30)
    plugin._x_client = QueryClient()
    event = Event()
    await plugin._tibo_command_lock.acquire()
    try:
        busy = [message async for message in plugin.tibo(event)]
    finally:
        plugin._tibo_command_lock.release()

    assert busy == ["已有推文查询正在执行，请稍后再试。"]
    available = [message async for message in plugin.tibo(event)]
    assert "【@thsottiaux 的 X 推文 #1】" in available[0]


@pytest.mark.asyncio
async def test_busy_newreset_request_does_not_consume_cooldown():
    plugin = _plugin(DeliveryContext())
    event = Event()
    await plugin._newreset_command_lock.acquire()
    try:
        busy = [message async for message in plugin.newreset(event)]
    finally:
        plugin._newreset_command_lock.release()

    assert busy == ["已有额度分析正在执行，请稍后再试。"]
    assert plugin._command_last_used == {}


def test_tweet_message_keeps_translation_and_original_text():
    plugin = _plugin(DeliveryContext())
    message = plugin._format_tweet(
        1,
        {
            "id": "10",
            "text": "Codex limits have reset.",
            "created_at": "Sun Aug 16 07:28:38 +0000 2026",
        },
        "Codex 额度已经重置。",
        True,
    )

    assert "中文翻译：\nCodex 额度已经重置。" in message
    assert "原文（Original）：\nCodex limits have reset." in message
    assert "原创推文" not in message


@pytest.mark.asyncio
async def test_initialize_and_terminate_clean_up_task_and_client():
    plugin = _plugin(DeliveryContext())
    client = TimelineClient([])
    plugin._x_client = client
    await plugin.initialize()
    assert plugin._monitor_task is not None
    monitor_task = plugin._monitor_task
    await plugin.initialize()
    assert plugin._monitor_task is monitor_task
    await plugin.terminate()
    assert plugin._monitor_task is None
    assert plugin._x_client is None
    assert client.closed is True
