from __future__ import annotations

import types

import pytest

import main


def _tweet_result(
    tweet_id: str,
    author_id: str = "42",
    *,
    reply: bool = False,
    retweet: bool = False,
    media_url: str | None = None,
):
    legacy = {
        "id_str": tweet_id,
        "full_text": f"tweet-{tweet_id}",
        "user_id_str": author_id,
        "created_at": "Sun Aug 16 07:28:38 +0000 2026",
        "lang": "en",
    }
    if reply:
        legacy["in_reply_to_status_id_str"] = "1"
    if retweet:
        legacy["retweeted_status_id_str"] = "1"
    if media_url:
        legacy["extended_entities"] = {"media": [{"media_url_https": media_url}]}
    return {"rest_id": tweet_id, "legacy": legacy}


def _timeline_payload():
    entries = [
        {"tweet_results": {"result": _tweet_result("105")}},
        {"tweet_results": {"result": _tweet_result("104", reply=True)}},
        {"tweet_results": {"result": _tweet_result("103", retweet=True)}},
        {"tweet_results": {"result": _tweet_result("102", author_id="99")}},
        {
            "tweet_results": {
                "result": _tweet_result("101", media_url="https://img/1.jpg")
            }
        },
    ]
    return {
        "data": {
            "timeline": {
                "instructions": [
                    {
                        "type": "TimelinePinEntry",
                        "content": {"tweet_results": {"result": _tweet_result("999")}},
                    },
                    {"entries": entries},
                    {"cursorType": "Bottom", "value": "next-cursor"},
                ]
            }
        }
    }


def test_user_id_and_cursor_extraction():
    assert (
        main._extract_graphql_user_id({"data": {"user": {"result": {"rest_id": "42"}}}})
        == "42"
    )
    assert main._extract_graphql_cursor(_timeline_payload()) == "next-cursor"


def test_tweet_extraction_skips_pin_and_keeps_media():
    tweets = main._extract_graphql_tweets(_timeline_payload())
    assert [tweet["id"] for tweet in tweets] == ["105", "104", "103", "102", "101"]
    assert tweets[-1]["_media_urls"] == ["https://img/1.jpg"]


@pytest.mark.asyncio
async def test_timeline_filters_replies_retweets_and_other_authors():
    client = object.__new__(main.XGraphQLClient)
    client._tweets_operation = "query/UserTweets"
    client.latest_tweet_id = None

    async def fake_get(self, operation, variables, **_kwargs):
        assert operation == "query/UserTweets"
        assert variables["userId"] == "42"
        return _timeline_payload()

    client._get = types.MethodType(fake_get, client)
    tweets, cursor = await client._get_timeline_page("42")
    assert [tweet["id"] for tweet in tweets] == ["105", "101"]
    assert cursor == "next-cursor"
    assert client.latest_tweet_id == "105"
