from __future__ import annotations

import pytest

import main


@pytest.mark.parametrize(
    "value, expected", [(None, 1), ("", 1), ("+2", 2), (3200, 3200)]
)
def test_parse_position_valid(value, expected):
    assert main.parse_position(value) == expected


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5", "3201"])
def test_parse_position_invalid(value):
    with pytest.raises(ValueError):
        main.parse_position(value)


def test_cookie_header_keeps_only_required_names():
    parsed = main._parse_cookie_values(
        "auth_token=fake-auth; ct0=fake-csrf; guest_id=drop-me"
    )
    assert parsed == {"auth_token": "fake-auth", "ct0": "fake-csrf"}


def test_cookie_mapping_keeps_only_required_names_case_insensitively():
    parsed = main._parse_cookie_values(
        {"AUTH_TOKEN": "fake-auth", "ct0": "fake-csrf", "other": "drop"}
    )
    assert parsed == {"auth_token": "fake-auth", "ct0": "fake-csrf"}


def test_cookie_list_requires_exact_x_domain():
    parsed = main._parse_cookie_values(
        [
            {"name": "auth_token", "value": "good", "domain": ".x.com"},
            {"name": "ct0", "value": "good-csrf", "domain": "twitter.com"},
            {"name": "auth_token", "value": "evil", "domain": "evilx.com"},
            {"name": "ct0", "value": "evil", "domain": "not-twitter.com"},
            {"name": "auth_token", "value": "unknown", "domain": ""},
            {"name": "guest_id", "value": "drop", "domain": "x.com"},
        ]
    )
    assert parsed == {"auth_token": "good", "ct0": "good-csrf"}


@pytest.mark.asyncio
async def test_graphql_client_sends_only_required_cookies():
    client = main.XGraphQLClient(
        username="thsottiaux",
        cookie_header="auth_token=fake; ct0=csrf; guest_id=drop",
    )
    try:
        assert client.cookies == {"auth_token": "fake", "ct0": "csrf"}
        assert "guest_id" not in client._client.headers["cookie"]
    finally:
        await client.close()


def test_translation_output_strips_outer_tweet_tags():
    assert (
        main._sanitize_translation_output("<tweet>\n中文译文\n</tweet>") == "中文译文"
    )


def test_translation_output_strips_fence_and_tweet_tags():
    raw = "```text\n<tweet>\n中文译文\n</tweet>\n```"
    assert main._sanitize_translation_output(raw) == "中文译文"


def test_translation_output_preserves_non_wrapper_tags():
    raw = "译文中提到了 <tweet> 标签，但它不是外层包装。"
    assert main._sanitize_translation_output(raw) == raw
