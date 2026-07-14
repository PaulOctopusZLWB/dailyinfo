from dataclasses import replace

import pytest
import requests

from info_radar.config import Source
from info_radar.fetchers import (
    build_github_api_urls,
    build_reddit_rss_url,
    build_x_user_lookup_url,
    build_x_user_tweets_url,
    fetch_source,
    filter_source_items,
    parse_arxiv_feed,
    parse_github_items,
    parse_openalex_items,
    parse_reddit_items,
    parse_rss_feed,
    parse_web_list,
    parse_x_tweets,
    parse_x_username,
    request_with_retries,
)


def source(source_type: str, url: str = "https://example.com/feed") -> Source:
    return Source(
        id=f"{source_type}-source",
        name=f"{source_type} Source",
        type=source_type,
        url=url,
        directions=("macro_ai",),
        language_hint="en",
        priority=50,
        enabled=True,
        notes="fixture",
    )


def test_parse_rss_feed_fixture() -> None:
    xml = """
<rss version="2.0">
  <channel>
    <title>Feed</title>
    <item>
      <title>AI frontier argument</title>
      <link>https://example.com/ai</link>
      <pubDate>Tue, 30 Jun 2026 08:00:00 GMT</pubDate>
      <description>Important macro AI thesis.</description>
    </item>
  </channel>
</rss>
"""

    items = parse_rss_feed(xml, source("rss"))

    assert len(items) == 1
    assert items[0].title == "AI frontier argument"
    assert items[0].url == "https://example.com/ai"
    assert items[0].direction_hints == ("macro_ai",)


def test_parse_arxiv_feed_fixture() -> None:
    xml = """
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Time Series Foundation Models</title>
    <id>http://arxiv.org/abs/2606.12345v1</id>
    <published>2026-06-30T08:00:00Z</published>
    <summary>We study temporal reasoning and forecasting.</summary>
  </entry>
</feed>
"""

    items = parse_arxiv_feed(xml, source("arxiv"))

    assert len(items) == 1
    assert items[0].source_type == "arxiv"
    assert items[0].url == "http://arxiv.org/abs/2606.12345v1"


def test_github_token_does_not_enable_issue_collection(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    src = source("github", "https://github.com/example/agent-workflow")

    assert build_github_api_urls(src) == [
        "https://api.github.com/repos/example/agent-workflow/releases",
    ]

    issue_source = replace(src, github_include_issues=True)
    assert build_github_api_urls(issue_source) == [
        "https://api.github.com/repos/example/agent-workflow/releases",
        "https://api.github.com/repos/example/agent-workflow/issues?state=open&per_page=20",
    ]

    payload = [
        {
            "html_url": "https://github.com/example/agent-workflow/releases/tag/v1",
            "name": "v1 release",
            "published_at": "2026-06-30T08:00:00Z",
            "body": "Agent workflow benchmark release.",
        }
    ]

    items = parse_github_items(payload, src)

    assert len(items) == 1
    assert items[0].source_type == "github"
    assert items[0].title == "v1 release"


def test_github_high_priority_preserves_legacy_issue_collection() -> None:
    src = replace(source("github", "https://github.com/example/agent-workflow"), priority=75)

    assert build_github_api_urls(src)[-1].endswith("/issues?state=open&per_page=20")


def test_github_low_priority_without_token_fetches_releases_only(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    src = source("github", "https://github.com/example/agent-workflow")

    assert build_github_api_urls(src) == [
        "https://api.github.com/repos/example/agent-workflow/releases",
    ]


def test_x_username_and_api_urls() -> None:
    assert parse_x_username("https://x.com/karpathy") == "karpathy"
    assert parse_x_username("https://twitter.com/sama/status/1") == "sama"
    assert parse_x_username("@OpenAI") == "OpenAI"
    assert parse_x_username("x://manual") == ""
    assert parse_x_username("https://x.com/i/lists/123") == ""
    assert build_x_user_lookup_url("karpathy") == (
        "https://api.x.com/2/users/by/username/karpathy?user.fields=id%2Cname%2Cusername%2Cverified"
    )
    assert build_x_user_tweets_url("123").startswith("https://api.x.com/2/users/123/tweets?")


def test_parse_x_tweets_fixture() -> None:
    payload = {
        "data": [
            {
                "id": "1800000000000000000",
                "text": "Agent evaluations need reproducible traces and environment isolation.",
                "created_at": "2026-06-30T08:00:00Z",
                "public_metrics": {
                    "retweet_count": 12,
                    "reply_count": 3,
                    "like_count": 140,
                    "quote_count": 2,
                },
            }
        ]
    }

    items = parse_x_tweets(payload, source("x", "https://x.com/karpathy"), username="karpathy")

    assert len(items) == 1
    assert items[0].source_type == "x"
    assert items[0].url == "https://x.com/karpathy/status/1800000000000000000"
    assert items[0].title.startswith("@karpathy: Agent evaluations")
    assert "like_count=140" in items[0].content_or_excerpt


def test_fetch_x_without_token_returns_empty(monkeypatch) -> None:
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)

    assert fetch_source(source("x", "https://x.com/karpathy")) == []


def test_fetch_x_with_bearer_uses_user_timeline(monkeypatch) -> None:
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    calls = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if "/by/username/" in url:
            return Response({"data": {"id": "123", "username": "karpathy"}})
        return Response(
            {
                "data": [
                    {
                        "id": "1800000000000000000",
                        "text": "A public X post about AI systems.",
                        "created_at": "2026-06-30T08:00:00Z",
                    }
                ]
            }
        )

    monkeypatch.setattr("info_radar.fetchers.requests.get", fake_get)
    items = fetch_source(source("x", "https://x.com/karpathy"))

    assert len(items) == 1
    assert items[0].url == "https://x.com/karpathy/status/1800000000000000000"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[1][0].startswith("https://api.x.com/2/users/123/tweets?")


def test_parse_web_list_resolves_relative_urls() -> None:
    html = """
<html>
  <body>
    <a href="/resources/blog/industrial-ai">Industrial AI in process operations</a>
    <a href="https://external.example.com/case">External case</a>
  </body>
</html>
"""
    src = source("web_list", "https://www.seeq.com/resources/blog/")

    items = parse_web_list(html, src)

    assert [item.url for item in items] == [
        "https://www.seeq.com/resources/blog/industrial-ai",
        "https://external.example.com/case",
    ]


def test_parse_reddit_items_fixture() -> None:
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "Agent benchmark discussion",
                        "permalink": "/r/MachineLearning/comments/abc/agent_benchmark_discussion/",
                        "created_utc": 1782816000,
                        "score": 123,
                        "num_comments": 45,
                        "selftext": "A discussion about reproducible agent evaluation.",
                    }
                },
                {"data": {"title": "Pinned", "permalink": "/r/test/comments/pin/", "stickied": True}},
            ]
        }
    }

    items = parse_reddit_items(payload, source("reddit"))

    assert len(items) == 1
    assert items[0].source_type == "reddit"
    assert items[0].url == "https://www.reddit.com/r/MachineLearning/comments/abc/agent_benchmark_discussion/"
    assert "score=123" in items[0].content_or_excerpt


def test_reddit_json_url_can_fallback_to_rss_url() -> None:
    assert (
        build_reddit_rss_url("https://www.reddit.com/r/MachineLearning/hot.json?limit=25")
        == "https://www.reddit.com/r/MachineLearning/.rss"
    )


def test_fetch_source_retries_arxiv_with_user_agent(monkeypatch) -> None:
    src = source("arxiv")
    calls = []

    class Response:
        status_code = 200
        text = """
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Retry Works</title>
    <id>http://arxiv.org/abs/2606.1</id>
    <published>2026-06-30T08:00:00Z</published>
    <summary>We propose a retrying fetch path.</summary>
  </entry>
</feed>
"""

        def raise_for_status(self) -> None:
            return None

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise requests.exceptions.SSLError("EOF")
        return Response()

    monkeypatch.setattr("info_radar.fetchers.requests.get", fake_get)
    monkeypatch.setattr("info_radar.fetchers.RETRY_SLEEP_SECONDS", 0, raising=False)

    items = fetch_source(src)

    assert len(items) == 1
    assert len(calls) == 2
    assert calls[0]["headers"]["User-Agent"].startswith("info-radar/")


def test_parse_openalex_items_reconstructs_abstract() -> None:
    payload = {
        "results": [
            {
                "display_name": "A foundation model for time series forecasting",
                "doi": "https://doi.org/10.1000/example",
                "publication_date": "2026-07-01",
                "abstract_inverted_index": {
                    "We": [0],
                    "forecast": [3],
                    "time": [1],
                    "series": [2],
                },
            },
            {
                "display_name": "A foundation model for time series forecasting",
                "id": "https://openalex.org/W-duplicate",
                "publication_date": "2026-07-01",
                "abstract_inverted_index": {"Duplicate": [0]},
            },
        ]
    }

    items = parse_openalex_items(payload, source("openalex"))

    assert len(items) == 1
    assert items[0].source_type == "openalex"
    assert items[0].content_or_excerpt == "We time series forecast"


def test_fetch_openalex_sends_key_as_request_param(monkeypatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "test-openalex-key")
    calls = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"results": []}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("info_radar.fetchers.requests.get", fake_get)

    assert fetch_source(source("openalex", "https://api.openalex.org/works?search=time%20series")) == []
    assert "test-openalex-key" not in calls[0][0]
    assert calls[0][1]["params"]["api_key"] == "test-openalex-key"
    assert calls[0][1]["params"]["filter"].startswith("from_publication_date:")
    assert "to_publication_date:" in calls[0][1]["params"]["filter"]
    assert "has_abstract:true" in calls[0][1]["params"]["filter"]
    assert "type:article|preprint" in calls[0][1]["params"]["filter"]


def test_fetch_openalex_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENALEX_API_KEY"):
        fetch_source(source("openalex"))


def test_request_error_redacts_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "secret-openalex-key")
    monkeypatch.setattr("info_radar.fetchers.RETRY_SLEEP_SECONDS", 0)

    def fake_get(*args, **kwargs):
        raise requests.RequestException(
            "failed https://api.openalex.org/works?api_key=secret-openalex-key"
        )

    monkeypatch.setattr("info_radar.fetchers.requests.get", fake_get)

    with pytest.raises(requests.RequestException) as exc_info:
        request_with_retries("https://api.openalex.org/works")

    assert "secret-openalex-key" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_source_filters_apply_include_and_exclude_terms() -> None:
    src = replace(
        source("rss"),
        include_any=("digital twin", "personal data"),
        exclude_any=("webinar",),
    )
    items = [
        parse_rss_feed(_rss_item("Digital twin memory", "A personal data system."), src)[0],
        parse_rss_feed(_rss_item("Generic health article", "Unrelated."), src)[0],
        parse_rss_feed(_rss_item("Digital twin webinar", "A personal data webinar."), src)[0],
    ]

    filtered = filter_source_items(items, src)

    assert [item.title for item in filtered] == ["Digital twin memory"]


def test_source_filter_matches_single_terms_on_word_boundaries() -> None:
    src = replace(source("rss"), include_any=("llm",))
    items = [
        parse_rss_feed(_rss_item("Enrollment policy", "Graduate enrollment rules."), src)[0],
        parse_rss_feed(_rss_item("LLM policy", "Rules for an LLM system."), src)[0],
    ]

    filtered = filter_source_items(items, src)

    assert [item.title for item in filtered] == ["LLM policy"]


def test_source_filter_can_require_topic_in_title() -> None:
    src = replace(source("rss"), include_title_any=("companion ai", "human-ai"))
    items = [
        parse_rss_feed(_rss_item("Companion AI governance", "A roadmap."), src)[0],
        parse_rss_feed(_rss_item("Generic governance", "Companion AI is mentioned once."), src)[0],
    ]

    filtered = filter_source_items(items, src)

    assert [item.title for item in filtered] == ["Companion AI governance"]


def _rss_item(title: str, description: str) -> str:
    slug = title.lower().replace(" ", "-")
    return f"""
<rss version="2.0"><channel><item>
  <title>{title}</title>
  <link>https://example.com/{slug}</link>
  <description>{description}</description>
</item></channel></rss>
"""
