# tibo雷达

`tibo雷达` 固定获取 X 账号 `@thsottiaux` 本人发布的原推文。外语内容会翻译成中文并保留原文，转推、回复、置顶旧推文和非目标作者内容会被过滤。插件还可分析近期推文中是否出现 Codex 额度重置信息。


## 支持范围

- AstrBot `>=4.27,<5`。
- 声明支持主动推送的消息平台：`aiocqhttp`、AstrBot ChatUI（`webchat`）。
- 其他平台仍可尝试被动指令回复，但插件不会为其建立主动推送订阅。

## 认证方式

插件仅使用浏览器 Cookie 请求 X 网页端内部 GraphQL。至少需要 `auth_token`，建议同时提供 `ct0`；可以粘贴 X 请求中的 Cookie Header，也可以分别填写两个值。

Cookie 是高敏感登录凭证，存在账号风控、封禁和泄露风险。请尽可能使用小号，切勿使用或分享主账号 Cookie。插件只会保留并发送 `auth_token` 和 `ct0`；浏览器列表导出中的 Cookie 必须精确属于 `x.com`、`.x.com`、`twitter.com` 或 `.twitter.com`，其他域名和其他 Cookie 名称都会被丢弃。Cookie 不会写入日志、推文消息或错误详情。

## 指令

- `/tibo` 或 `/tibo 1`：获取最新一条推文。
- `/tibo 2`：获取上一条推文；数字越大越早。
- `/tibo +2`：等同于 `/tibo 2`。
- `/newreset`：分析近期原推文，判断 Codex 使用额度是否已经重置，并按北京时间报告证据时间。
- `/tibo_stop`：停止当前会话的新推文自动推送。

## 权限与限流

- `/tibo` 和 `/newreset` 允许普通用户调用，但各自全局只执行一个请求。
- `/tibo` 默认按“命令 + 会话 + 用户”冷却 15 秒；`/newreset` 默认冷却 120 秒，均可在设置中调整。
- `aiocqhttp` 私聊与 AstrBot ChatUI 会话用户可以管理自己的订阅。
- 群聊只有 AstrBot 管理员可以通过 `/tibo` 建立订阅或通过 `/tibo_stop` 取消订阅；普通成员查询推文不会改变群级订阅。

## 主动推送可靠性

插件为每个订阅会话分别保存投递游标。只有 `context.send_message()` 明确返回成功后才推进对应会话的游标；返回 `False`、抛出异常或部分会话失败时，失败会话会在下一轮继续重试，其他成功会话不受影响。每条成功投递后都会更新 AstrBot KV，因此重启后仍能继续处理未成功送达的内容。

## 配置要点

- 监控目标固定为 `@thsottiaux`，配置页面不提供账号修改入口。
- `poll_interval_seconds` 默认为 60 秒，允许 15-3600 秒。
- `reset_analysis_tweet_count` 默认为 20，允许 1-50 条，仅在执行 `/newreset` 时分页抓取。
- `tibo_cooldown_seconds` 默认为 15 秒；`newreset_cooldown_seconds` 默认为 120 秒。
- `translation_enabled` 默认开启；翻译和 `/newreset` 分析使用当前会话聊天模型，也可以通过模型选择器指定 `translation_provider_id`。
- Cookie 模式的 `graphql_query_id` 和 `graphql_user_query_id` 是可覆盖项，X 更新网页端接口后可按浏览器 Network 请求中的实际值更新。

## 开发检查

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff format --check .
ruff check --no-cache .
python -m pytest
```
