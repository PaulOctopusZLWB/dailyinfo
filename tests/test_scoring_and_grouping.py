from info_radar.dedupe import dedupe_items
from info_radar.models import RadarItem
from info_radar.pipeline import filter_recent_items, group_ranked_items
from info_radar.scoring import score_item


def make_item(
    title: str,
    url: str,
    source_type: str = "rss",
    excerpt: str = "",
    published_at: str = "2026-06-30T08:00:00+08:00",
) -> RadarItem:
    return RadarItem(
        source_id="source",
        source_name="Source",
        source_type=source_type,
        title=title,
        url=url,
        published_at=published_at,
        content_or_excerpt=excerpt,
        direction_hints=(),
    )


def test_scoring_detects_agent_relevance_and_ad_risk() -> None:
    item = make_item(
        "Agent workflow benchmark",
        "https://example.com/agent",
        excerpt="GitHub repo shows benchmark results. 限时训练营报名购买课程。",
    )

    scored = score_item(item, source_priority=70)

    assert scored.primary_direction == "ai_agents"
    assert scored.ad_risk == "明显推广"
    assert scored.evidence_type == "代码/开源项目"
    assert scored.core_argument.startswith("核心论述：")
    assert "值得推荐" in scored.recommendation_reason
    assert scored.score < 100


def test_scoring_does_not_treat_proposed_as_repo_evidence() -> None:
    item = make_item(
        "Adaptive Financial Transformer",
        "https://arxiv.org/abs/2606.29347",
        source_type="arxiv",
        excerpt="A model is proposed for stock return prediction under non-stationary markets.",
    )

    scored = score_item(item, source_priority=80)

    assert scored.evidence_type == "论文/研究"


def test_scoring_does_not_treat_reported_as_repo_evidence() -> None:
    item = make_item(
        "What Counts as an Error? Dual-Reference Benchmarking for Atypical ASR",
        "https://arxiv.org/abs/2606.30000",
        source_type="arxiv",
        excerpt="ASR systems have been often reported to underperform on atypical speech.",
    )

    scored = score_item(item, source_priority=80)

    assert scored.evidence_type == "论文/研究"


def test_scoring_treats_openalex_as_research_evidence() -> None:
    item = make_item(
        "Human-AI interaction and personal context",
        "https://doi.org/10.1000/openalex-example",
        source_type="openalex",
        excerpt="We study human-AI interaction and personal data systems.",
    )

    scored = score_item(item, source_priority=75)

    assert scored.evidence_type == "论文/研究"


def test_scoring_detects_ai_era_philosophy_discussion() -> None:
    item = make_item(
        "AI era philosophy of agency and meaning in human-AI interaction",
        "https://example.com/ai-philosophy",
        excerpt=(
            "An essay argues that generative AI changes selfhood, personhood, agency, "
            "ethics, meaning, and the emotional boundary of human-AI interaction."
        ),
    )

    scored = score_item(item, source_priority=70)

    assert scored.primary_direction == "ai_philosophy"


def test_scoring_detects_dynamical_system_reconstruction() -> None:
    item = make_item(
        "Dynamical system reconstruction from partial observations using stochastic dynamics",
        "https://arxiv.org/abs/2510.01089",
        source_type="arxiv",
        excerpt=(
            "We infer latent system state trajectories and noise time series from partially observed "
            "nonlinear dynamics using a variational state-space model."
        ),
    )

    scored = score_item(item, source_priority=90)

    assert scored.primary_direction == "dynamical_systems"


def test_scoring_detects_ics_advisory_evidence_type() -> None:
    item = RadarItem(
        source_id="cisa-ics-advisories",
        source_name="CISA ICS Advisories",
        source_type="rss",
        title="Frangoteam FUXA SCADA/HMI",
        url="https://www.cisa.gov/news-events/ics-advisories/icsa-26-181-02",
        published_at="2026-06-30T12:00:00Z",
        content_or_excerpt="CVE-2026-13207 with CSAF JSON on GitHub affects SCADA/HMI deployments.",
        direction_hints=("industrial_ai",),
    )

    scored = score_item(item, source_priority=78)

    assert scored.evidence_type == "安全公告/漏洞通报"


def test_scoring_detects_smart_manufacturing_as_industrial_ai() -> None:
    item = make_item(
        "Smart manufacturing roadmap for edge AI",
        "https://example.com/smart-manufacturing",
        excerpt="An OPC UA and edge computing architecture for a digital twin factory.",
    )

    scored = score_item(item, source_priority=74)

    assert scored.primary_direction == "industrial_ai"


def test_content_signal_can_override_source_direction_hint() -> None:
    item = RadarItem(
        source_id="arxiv-ai",
        source_name="arXiv AI",
        source_type="arxiv",
        title="A time-series classification framework for absenteeism prediction",
        url="https://arxiv.org/abs/2606.31532",
        published_at="2026-06-30T08:00:00+08:00",
        content_or_excerpt="We propose a time series classification framework for proactive forecasting of future absence labels.",
        direction_hints=("macro_ai",),
    )

    scored = score_item(item, source_priority=80)

    assert scored.primary_direction == "temporal"


def test_dedupe_collapses_tracking_urls_and_repeated_titles() -> None:
    first = make_item("OpenAI releases agent SDK", "https://example.com/post?utm_source=x")
    second = make_item("OpenAI releases agent SDK", "https://example.com/post#comments")
    third = make_item("Different temporal paper", "https://example.com/temporal")

    deduped = dedupe_items([first, second, third])

    assert len(deduped) == 2
    assert deduped[0].duplicate_count == 2
    assert deduped[0].cluster_id == deduped[0].cluster_id


def test_filter_recent_items_keeps_last_15_days_and_unknown_dates() -> None:
    recent = make_item(
        title="Recent",
        url="https://example.com/recent",
        published_at="2026-06-20T08:00:00Z",
    )
    old = make_item(
        title="Old",
        url="https://example.com/old",
        published_at="2026-06-01T08:00:00Z",
    )
    unknown = make_item(
        title="Unknown",
        url="https://example.com/unknown",
        published_at="",
    )

    filtered = filter_recent_items([recent, old, unknown], report_date="2026-07-01", lookback_days=15)

    assert [entry.title for entry in filtered] == ["Recent", "Unknown"]


def test_grouping_limits_each_direction_and_prevents_cross_direction_duplicates() -> None:
    items = []
    for index in range(12):
        item = make_item(
            f"Agent library {index}",
            f"https://github.com/example/agent-{index}",
            source_type="github",
            excerpt="agent workflow github repo benchmark",
        )
        scored = score_item(item, source_priority=80)
        items.append(scored)

    grouped = group_ranked_items(items, per_direction_limit=10)

    assert len(grouped["ai_agents"]) == 10
    all_urls = [item.url for group in grouped.values() for item in group]
    assert len(all_urls) == len(set(all_urls))


def test_grouping_can_cap_source_concentration_within_direction() -> None:
    items = []
    for index in range(6):
        item = RadarItem(
            source_id="cisa-ics-advisories",
            source_name="CISA ICS Advisories",
            source_type="rss",
            title=f"SCADA advisory {index}",
            url=f"https://www.cisa.gov/news-events/ics-advisories/{index}",
            published_at="2026-06-30T08:00:00+08:00",
            content_or_excerpt="SCADA HMI PLC industrial control vulnerability advisory.",
            direction_hints=("industrial_ai",),
        )
        items.append(score_item(item, source_priority=90))
    for index in range(3):
        item = RadarItem(
            source_id="seeq-blog",
            source_name="Seeq Blog",
            source_type="rss",
            title=f"Process optimization analytics {index}",
            url=f"https://www.seeq.com/resources/blog/{index}",
            published_at="2026-06-30T08:00:00+08:00",
            content_or_excerpt="Process industry AI analytics and time series optimization.",
            direction_hints=("industrial_ai",),
        )
        items.append(score_item(item, source_priority=70))

    grouped = group_ranked_items(items, per_direction_limit=10, per_source_limit=4)

    industrial_sources = [item.source_id for item in grouped["industrial_ai"]]
    assert industrial_sources.count("cisa-ics-advisories") == 4
    assert industrial_sources.count("seeq-blog") == 3
