import os
import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Iterable, List, Optional
from urllib.parse import urlencode, urljoin, urlparse
from xml.etree import ElementTree

import feedparser
import requests

from info_radar.config import Source
from info_radar.models import RadarItem


REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 2
USER_AGENT = "info-radar/0.1 (+https://local.invalid; personal research radar)"
SECRET_ENV_KEYS = (
    "GITHUB_TOKEN",
    "OPENALEX_API_KEY",
    "X_BEARER_TOKEN",
    "TWITTER_BEARER_TOKEN",
)
OPENALEX_LOOKBACK_DAYS = 45


def fetch_source(source: Source) -> List[RadarItem]:
    return filter_source_items(_fetch_source_unfiltered(source), source)


def _fetch_source_unfiltered(source: Source) -> List[RadarItem]:
    if source.type in {"manual", "bilibili", "zsxq"}:
        return []
    if source.type == "x":
        return fetch_x_source(source)
    if source.type in {"rss", "atom", "youtube"}:
        response = request_with_retries(source.url)
        return parse_rss_feed(response.text, source)
    if source.type == "arxiv":
        response = request_with_retries(source.url)
        return parse_arxiv_feed(response.text, source)
    if source.type == "openalex":
        return fetch_openalex_source(source)
    if source.type == "github":
        items = []
        headers = _github_headers()
        for api_url in build_github_api_urls(source):
            response = request_with_retries(api_url, headers=headers)
            items.extend(parse_github_items(response.json(), source))
        return items
    if source.type == "reddit":
        try:
            response = request_with_retries(source.url)
            return parse_reddit_items(response.json(), source)
        except requests.RequestException:
            response = request_with_retries(build_reddit_rss_url(source.url))
            return parse_rss_feed(response.text, source)
    if source.type == "web_list":
        response = request_with_retries(source.url)
        return parse_web_list(response.text, source)
    raise ValueError(f"unsupported source type: {source.type}")


def request_with_retries(
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
):
    request_headers = default_headers()
    if headers:
        request_headers.update(headers)
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=request_headers, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(RETRY_SLEEP_SECONDS * attempt)
    raise requests.RequestException(_sanitize_request_error(last_error)) from None


def default_headers() -> dict:
    return {"User-Agent": USER_AGENT}


def parse_rss_feed(xml: str, source: Source) -> List[RadarItem]:
    parsed = feedparser.parse(xml)
    items = []
    for entry in parsed.entries:
        title = _entry_value(entry, "title")
        url = _entry_value(entry, "link")
        if not title or not url:
            continue
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                title=title,
                url=url,
                published_at=_entry_value(entry, "published") or _entry_value(entry, "updated"),
                content_or_excerpt=_entry_value(entry, "summary") or _entry_value(entry, "description"),
                direction_hints=source.directions,
            )
        )
    return items


def parse_arxiv_feed(xml: str, source: Source) -> List[RadarItem]:
    root = ElementTree.fromstring(xml)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", namespace):
        title = _xml_text(entry, "atom:title", namespace)
        url = _xml_text(entry, "atom:id", namespace)
        if not title or not url:
            continue
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type="arxiv",
                title=" ".join(title.split()),
                url=url,
                published_at=_xml_text(entry, "atom:published", namespace),
                content_or_excerpt=" ".join(_xml_text(entry, "atom:summary", namespace).split()),
                direction_hints=source.directions,
            )
        )
    return items


def fetch_openalex_source(source: Source) -> List[RadarItem]:
    api_key = (os.environ.get("OPENALEX_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENALEX_API_KEY is not configured")
    today = datetime.now(timezone.utc).date()
    window_start = today - timedelta(days=OPENALEX_LOOKBACK_DAYS)
    params = {
        "api_key": api_key,
        "filter": (
            f"from_publication_date:{window_start.isoformat()},"
            f"to_publication_date:{today.isoformat()},"
            "has_abstract:true,type:article|preprint"
        ),
    }
    response = request_with_retries(source.url, params=params)
    return parse_openalex_items(response.json(), source)


def parse_openalex_items(payload: object, source: Source) -> List[RadarItem]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("results", [])
    if not isinstance(rows, list):
        return []

    items = []
    seen_titles = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("display_name") or row.get("title") or "").strip()
        title_key = re.sub(r"\s+", " ", title).casefold()
        primary_location = row.get("primary_location")
        landing_page_url = ""
        if isinstance(primary_location, dict):
            landing_page_url = str(primary_location.get("landing_page_url") or "").strip()
        url = str(row.get("doi") or landing_page_url or row.get("id") or "").strip()
        if not title or not url or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type="openalex",
                title=title,
                url=url,
                published_at=str(row.get("publication_date") or ""),
                content_or_excerpt=_openalex_abstract(row.get("abstract_inverted_index")),
                direction_hints=source.directions,
            )
        )
    return items


def build_github_api_urls(source: Source) -> List[str]:
    parsed = urlparse(source.url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc != "github.com" or len(path_parts) < 2:
        raise ValueError(f"github source url must be https://github.com/owner/repo: {source.url}")
    owner, repo = path_parts[0], path_parts[1]
    base = f"https://api.github.com/repos/{owner}/{repo}"
    urls = [f"{base}/releases"]
    include_issues = source.github_include_issues
    if include_issues is None:
        include_issues = source.priority >= 75
    if include_issues:
        urls.append(f"{base}/issues?state=open&per_page=20")
    return urls


def filter_source_items(items: Iterable[RadarItem], source: Source) -> List[RadarItem]:
    include_terms = tuple(term.casefold() for term in source.include_any)
    include_title_terms = tuple(term.casefold() for term in source.include_title_any)
    exclude_terms = tuple(term.casefold() for term in source.exclude_any)
    filtered = []
    for item in items:
        title = re.sub(r"\s+", " ", item.title.casefold())
        haystack = re.sub(
            r"\s+",
            " ",
            f"{item.title}\n{item.content_or_excerpt}\n{item.url}".casefold(),
        )
        if exclude_terms and any(_term_matches(term, haystack) for term in exclude_terms):
            continue
        if include_terms and not any(_term_matches(term, haystack) for term in include_terms):
            continue
        if include_title_terms and not any(_term_matches(term, title) for term in include_title_terms):
            continue
        filtered.append(item)
    return filtered


def _term_matches(term: str, haystack: str) -> bool:
    if re.fullmatch(r"\w+", term, flags=re.UNICODE):
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        return re.search(pattern, haystack, flags=re.UNICODE) is not None
    return term in haystack


def parse_github_items(payload: object, source: Source) -> List[RadarItem]:
    if not isinstance(payload, list):
        return []
    items = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        if "pull_request" in row:
            continue
        title = str(row.get("name") or row.get("title") or "").strip()
        url = str(row.get("html_url") or "").strip()
        if not title or not url:
            continue
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type="github",
                title=title,
                url=url,
                published_at=str(row.get("published_at") or row.get("created_at") or row.get("updated_at") or ""),
                content_or_excerpt=str(row.get("body") or ""),
                direction_hints=source.directions,
            )
        )
    return items


def fetch_x_source(source: Source) -> List[RadarItem]:
    token = _x_bearer_token()
    if not token:
        return []
    username = parse_x_username(source.url)
    if not username:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    user_response = request_with_retries(build_x_user_lookup_url(username), headers=headers)
    user_id = parse_x_user_id(user_response.json())
    if not user_id:
        return []
    tweets_response = request_with_retries(build_x_user_tweets_url(user_id), headers=headers)
    return parse_x_tweets(tweets_response.json(), source, username=username)


def parse_x_username(url: str) -> str:
    text = (url or "").strip()
    if not text or text.startswith("x://"):
        return ""
    if text.startswith("@"):
        return text[1:].strip()
    parsed = urlparse(text)
    if parsed.netloc not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return ""
    if parts[0] in {"i", "intent", "search", "home", "explore"}:
        return ""
    return parts[0].lstrip("@")


def build_x_user_lookup_url(username: str) -> str:
    query = urlencode({"user.fields": "id,name,username,verified"})
    return f"https://api.x.com/2/users/by/username/{username}?{query}"


def build_x_user_tweets_url(user_id: str, max_results: int = 10) -> str:
    query = urlencode(
        {
            "max_results": str(max_results),
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,lang,public_metrics,referenced_tweets",
        }
    )
    return f"https://api.x.com/2/users/{user_id}/tweets?{query}"


def parse_x_user_id(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""
    return str(data.get("id") or "").strip()


def parse_x_tweets(payload: object, source: Source, username: str) -> List[RadarItem]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tweet_id = str(row.get("id") or "").strip()
        text = _clean_x_text(str(row.get("text") or ""))
        if not tweet_id or not text:
            continue
        metrics = row.get("public_metrics", {})
        excerpt = text
        if isinstance(metrics, dict):
            metric_text = "; ".join(
                f"{key}={metrics.get(key)}"
                for key in ["retweet_count", "reply_count", "like_count", "quote_count"]
                if metrics.get(key) is not None
            )
            if metric_text:
                excerpt = f"{text}\n\nX public metrics: {metric_text}"
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type="x",
                title=_x_title(username, text),
                url=f"https://x.com/{username}/status/{tweet_id}",
                published_at=str(row.get("created_at") or ""),
                content_or_excerpt=excerpt,
                direction_hints=source.directions,
            )
        )
    return items


def parse_reddit_items(payload: object, source: Source) -> List[RadarItem]:
    if not isinstance(payload, dict):
        return []
    children = payload.get("data", {}).get("children", [])
    if not isinstance(children, list):
        return []

    items = []
    for child in children:
        if not isinstance(child, dict):
            continue
        row = child.get("data", {})
        if not isinstance(row, dict) or row.get("stickied"):
            continue
        title = str(row.get("title") or "").strip()
        permalink = str(row.get("permalink") or "").strip()
        url = str(row.get("url") or "").strip()
        if permalink.startswith("/"):
            permalink = f"https://www.reddit.com{permalink}"
        canonical_url = permalink or url
        if not title or not canonical_url:
            continue
        created = row.get("created_utc")
        published_at = ""
        if isinstance(created, (int, float)):
            published_at = datetime.fromtimestamp(created, timezone.utc).isoformat()
        score = row.get("score", 0)
        comments = row.get("num_comments", 0)
        body = str(row.get("selftext") or row.get("link_flair_text") or "")
        excerpt = f"Reddit score={score}; comments={comments}. {body}".strip()
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type="reddit",
                title=title,
                url=canonical_url,
                published_at=published_at,
                content_or_excerpt=excerpt,
                direction_hints=source.directions,
            )
        )
    return items


def build_reddit_rss_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "r":
        return f"https://www.reddit.com/r/{parts[1]}/.rss"
    return url


def parse_web_list(html: str, source: Source) -> List[RadarItem]:
    parser = _LinkParser()
    parser.feed(html)
    items = []
    for title, url in parser.links[:50]:
        resolved_url = urljoin(source.url, url)
        if not title or not resolved_url.startswith("http"):
            continue
        items.append(
            RadarItem(
                source_id=source.id,
                source_name=source.name,
                source_type="web_list",
                title=title,
                url=resolved_url,
                published_at="",
                content_or_excerpt="网页列表链接，需后续人工或 LLM 补充摘要。",
                direction_hints=source.directions,
            )
        )
    return items


def _entry_value(entry, key: str) -> str:
    value = entry.get(key, "")
    return str(value).strip()


def _xml_text(entry, path: str, namespace) -> str:
    element = entry.find(path, namespace)
    return element.text.strip() if element is not None and element.text else ""


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _x_bearer_token() -> str:
    return (os.environ.get("X_BEARER_TOKEN") or os.environ.get("TWITTER_BEARER_TOKEN") or "").strip()


def _clean_x_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _openalex_abstract(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    positioned_words = []
    for word, positions in value.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_words.append((position, str(word)))
    positioned_words.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positioned_words)[:4000]


def _sanitize_request_error(error: Optional[BaseException]) -> str:
    text = str(error or "request failed")
    for key in SECRET_ENV_KEYS:
        secret = (os.environ.get(key) or "").strip()
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return re.sub(r"([?&](?:api_key|access_token|token)=)[^&\s]+", r"\1[REDACTED]", text)


def _x_title(username: str, text: str) -> str:
    title = text[:118].rstrip()
    if len(text) > 118:
        title = f"{title}..."
    return f"@{username}: {title}"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links = []
        self._current_href = ""
        self._current_text = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == "a" and self._current_href:
            title = re.sub(r"\s+", " ", "".join(self._current_text)).strip()
            self.links.append((title, self._current_href))
            self._current_href = ""
            self._current_text = []
