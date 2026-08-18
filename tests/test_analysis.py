from __future__ import annotations

import pytest

import main


def test_analysis_json_normal():
    result = main._parse_reset_analysis_result(
        '{"reset_detected":true,"evidence_tweet_id":"2",'
        '"confidence":"high","reason":"明确重置"}',
        {"1", "2"},
    )
    assert result["reset_detected"] is True
    assert result["evidence_tweet_id"] == "2"


def test_analysis_json_code_fence():
    result = main._parse_reset_analysis_result(
        "```json\n"
        '{"reset_detected":false,"evidence_tweet_id":null,'
        '"confidence":"high","reason":"没有证据"}'
        "\n```",
        {"1"},
    )
    assert result["reset_detected"] is False
    assert result["evidence_tweet_id"] == ""


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        '{"reset_detected":"yes"}',
        '{"reset_detected":true,"evidence_tweet_id":"999"}',
    ],
)
def test_analysis_rejects_invalid_results(payload):
    with pytest.raises(main.ResetAnalysisError):
        main._parse_reset_analysis_result(payload, {"1", "2"})


def test_reset_report_uses_evidence_tweet_time_in_beijing_timezone():
    plugin = main.TiboPlugin(object(), {"translation_enabled": False})
    tweets = [
        {
            "id": "2",
            "text": "Codex limits have reset.",
            "created_at": "Sun Aug 16 07:28:38 +0000 2026",
        },
        {
            "id": "1",
            "text": "Earlier post.",
            "created_at": "Sun Aug 16 06:00:00 +0000 2026",
        },
    ]

    report = plugin._format_reset_analysis(
        tweets,
        {
            "reset_detected": True,
            "evidence_tweet_id": "2",
            "confidence": "high",
            "reason": "推文明示额度已经重置。",
        },
    )

    assert "额度重置时间：最晚可确认于 2026-08-16 15:28（北京时间）" in report
    assert "https://x.com/thsottiaux/status/2" in report
