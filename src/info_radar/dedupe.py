import hashlib
import re
from dataclasses import replace
from typing import Dict, Iterable, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "spm"}


def dedupe_items(items):
    clusters: Dict[str, list] = {}
    for item in items:
        key = _cluster_key(item)
        clusters.setdefault(key, []).append(item)

    deduped = []
    for key, cluster_items in clusters.items():
        representative = max(cluster_items, key=lambda item: len(item.content_or_excerpt or ""))
        cluster_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        deduped.append(replace(representative, cluster_id=cluster_id, duplicate_count=len(cluster_items)))

    return sorted(deduped, key=lambda item: (item.published_at, item.title), reverse=True)


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith("utm_") and key not in TRACKING_PARAMS
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def _cluster_key(item) -> str:
    canonical_url = canonicalize_url(item.url)
    title_key = re.sub(r"\W+", " ", item.title.lower()).strip()
    if canonical_url:
        return f"url:{canonical_url}"
    return f"title:{title_key}"
