from __future__ import annotations

import copy
import sys
import types


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class _MessageChain:
    def __init__(self):
        self.messages: list[str] = []

    def message(self, text: str):
        self.messages.append(text)
        return self


class _Filter:
    @staticmethod
    def command(_name: str):
        return lambda function: function


class _Context:
    pass


class _Star:
    def __init__(self, context):
        self.context = context
        self._test_kv: dict[str, object] = {}

    async def get_kv_data(self, key: str, default=None):
        return copy.deepcopy(self._test_kv.get(key, default))

    async def put_kv_data(self, key: str, value):
        self._test_kv[key] = copy.deepcopy(value)


astrbot_module = types.ModuleType("astrbot")
api_module = types.ModuleType("astrbot.api")
event_module = types.ModuleType("astrbot.api.event")
star_module = types.ModuleType("astrbot.api.star")

api_module.logger = _Logger()
event_module.AstrMessageEvent = type("AstrMessageEvent", (), {})
event_module.MessageChain = _MessageChain
event_module.filter = _Filter()
star_module.Context = _Context
star_module.Star = _Star

sys.modules["astrbot"] = astrbot_module
sys.modules["astrbot.api"] = api_module
sys.modules["astrbot.api.event"] = event_module
sys.modules["astrbot.api.star"] = star_module
