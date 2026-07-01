from dataclasses import dataclass, field
from typing import Mapping, Tuple


@dataclass(frozen=True)
class RadarItem:
    source_id: str
    source_name: str
    source_type: str
    title: str
    url: str
    published_at: str
    content_or_excerpt: str
    direction_hints: Tuple[str, ...]
    cluster_id: str = ""
    duplicate_count: int = 1


@dataclass(frozen=True)
class ScoredItem(RadarItem):
    primary_direction: str = ""
    score: float = 0.0
    evidence_type: str = ""
    ad_risk: str = ""
    core_argument: str = ""
    recommendation_reason: str = ""
    direction_scores: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectionSummary:
    direction_id: str
    target: int
    actual: int
    shortage_reason: str


@dataclass(frozen=True)
class FetchFailure:
    source_id: str
    source_name: str
    reason: str
