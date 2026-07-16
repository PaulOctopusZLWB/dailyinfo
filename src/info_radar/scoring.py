import html
import re

from info_radar.directions import DIRECTIONS
from info_radar.models import ScoredItem


DIRECTION_KEYWORDS = {
    "macro_ai": [
        "frontier",
        "foundation model",
        "agi",
        "openai",
        "anthropic",
        "deepmind",
        "scaling",
        "capability",
        "ai thesis",
        "模型能力",
        "前沿",
        "范式",
        "大模型",
        "产业判断",
    ],
    "temporal": [
        "time-series",
        "time series",
        "temporal",
        "forecast",
        "forecasting",
        "sequence",
        "event",
        "时序",
        "预测",
        "时间序列",
        "事件",
        "动态系统",
    ],
    "industrial_ai": [
        "industrial",
        "control",
        "scada",
        "dcs",
        "mes",
        "apc",
        "factory",
        "manufacturing",
        "opc ua",
        "edge ai",
        "edge computing",
        "digital twin",
        "industry 4.0",
        "process engineering",
        "工业",
        "工控",
        "控制软件",
        "流程工业",
        "工艺",
    ],
    "ai_agents": [
        "agent",
        "agents",
        "workflow",
        "github",
        "repo",
        "benchmark",
        "tool calling",
        "codex",
        "claude code",
        "方法论",
        "开源库",
        "工作流",
    ],
    "human_digital_twin": [
        "digital twin",
        "personal context",
        "memory",
        "life os",
        "human model",
        "companion",
        "数字孪生",
        "个人上下文",
        "记忆",
        "人格",
        "人类模型",
    ],
    "ai_philosophy": [
        "philosophy",
        "philosophical",
        "human-ai interaction",
        "human ai interaction",
        "human-machine interaction",
        "agency",
        "selfhood",
        "personhood",
        "meaning",
        "ethics",
        "values",
        "consciousness",
        "anthropomorphism",
        "phenomenology",
        "identity",
        "attention",
        "emotional boundary",
        "ai companion",
        "哲学",
        "朴素哲学",
        "人机互动",
        "人机关系",
        "主体性",
        "能动性",
        "意义",
        "价值观",
        "伦理",
        "意识",
        "现象学",
        "拟人",
        "身份",
        "自我",
        "注意力",
        "情感边界",
        "陪伴",
    ],
    "dynamical_systems": [
        "dynamical system reconstruction",
        "dynamical systems reconstruction",
        "system identification",
        "state space reconstruction",
        "state-space reconstruction",
        "latent dynamics",
        "latent dynamical",
        "hidden state inference",
        "partial observations",
        "partially observed",
        "stochastic dynamics",
        "nonlinear dynamics",
        "chaotic dynamics",
        "attractor reconstruction",
        "attractor geometry",
        "koopman operator",
        "neural ode",
        "neural sde",
        "sindy",
        "reservoir computing",
        "动力系统重建",
        "动力学重建",
        "系统辨识",
        "状态空间重建",
        "隐状态推断",
        "部分观测",
        "随机动力学",
        "非线性动力学",
        "混沌动力学",
        "吸引子重建",
    ],
}

AD_KEYWORDS = [
    "限时",
    "训练营",
    "报名",
    "购买",
    "课程",
    "优惠",
    "折扣",
    "加微信",
    "私信",
    "广告",
    "赞助",
    "咨询",
    "白皮书下载",
]

CLAIM_MARKERS = [
    "we propose",
    "we introduce",
    "we show",
    "we find",
    "we demonstrate",
    "we evaluate",
    "this paper proposes",
    "this paper introduces",
    "this work",
    "our results",
    "提出",
    "发现",
    "证明",
    "显示",
    "认为",
    "主张",
    "验证",
]


def score_item(item, source_priority: int = 50) -> ScoredItem:
    text = f"{item.title}\n{item.content_or_excerpt}\n{item.url}".lower()
    direction_scores = {}
    for direction_id, keywords in DIRECTION_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            if keyword.lower() in text:
                score += 12.0
        if direction_id in item.direction_hints:
            score += 35.0
        direction_scores[direction_id] = score

    primary_direction = max(direction_scores, key=direction_scores.get)
    if direction_scores[primary_direction] == 0:
        primary_direction = item.direction_hints[0] if item.direction_hints else "macro_ai"

    ad_hits = [keyword for keyword in AD_KEYWORDS if keyword.lower() in text]
    ad_penalty = 35.0 if len(ad_hits) >= 3 else 18.0 if ad_hits else 0.0
    duplicate_penalty = max(0, item.duplicate_count - 1) * 8.0
    evidence_type = infer_evidence_type(item)
    core_argument = extract_core_argument(item)
    evidence_bonus = {
        "代码/开源项目": 20.0,
        "论文/研究": 18.0,
        "安全公告/漏洞通报": 16.0,
        "官方/产品更新": 14.0,
        "视频/社群讨论": 8.0,
        "观点/转述": 4.0,
    }[evidence_type]
    score = source_priority * 0.35 + direction_scores[primary_direction] + evidence_bonus - ad_penalty - duplicate_penalty

    return ScoredItem(
        source_id=item.source_id,
        source_name=item.source_name,
        source_type=item.source_type,
        title=item.title,
        url=item.url,
        published_at=item.published_at,
        content_or_excerpt=item.content_or_excerpt,
        direction_hints=item.direction_hints,
        cluster_id=item.cluster_id,
        duplicate_count=item.duplicate_count,
        primary_direction=primary_direction,
        score=round(max(score, 0.0), 2),
        evidence_type=evidence_type,
        ad_risk=_ad_risk_label(ad_hits),
        core_argument=core_argument,
        recommendation_reason=_recommendation_reason(item, primary_direction, evidence_type, bool(ad_hits)),
        direction_scores=direction_scores,
    )


def infer_evidence_type(item) -> str:
    text = f"{item.source_type} {item.url} {item.title} {item.content_or_excerpt}".lower()
    if (
        "ics-advisories" in text
        or "cisa ics" in text
        or "cve-" in text
        or "vulnerability" in text
        or "漏洞" in text
    ):
        return "安全公告/漏洞通报"
    if item.source_type == "github" or "github.com" in text:
        return "代码/开源项目"
    if item.source_type in {"arxiv", "openalex"} or "arxiv.org" in text or "paper" in text or "论文" in text:
        return "论文/研究"
    if re.search(r"\b(repo|repository)\b", text):
        return "代码/开源项目"
    if item.source_type in {"bilibili", "x", "zsxq", "manual"}:
        return "视频/社群讨论"
    if any(token in text for token in ["official", "release", "changelog", "blog", "公告", "发布"]):
        return "官方/产品更新"
    return "观点/转述"


def _ad_risk_label(ad_hits) -> str:
    if len(ad_hits) >= 3:
        return "明显推广"
    if ad_hits:
        return "弱推广"
    return "未见明显推广"


def extract_core_argument(item) -> str:
    title = clean_text(item.title)
    body = clean_text(item.content_or_excerpt)
    sentence = pick_claim_sentence(body) or title
    if sentence == title:
        argument = f"核心论述：这条材料围绕「{title}」提出了一个值得跟踪的方向。"
    elif contains_cjk(sentence):
        argument = f"核心论述：{sentence}"
    else:
        argument = f"核心论述：围绕「{title}」，材料主张：{sentence}"
    return compact(argument, 260)


def pick_claim_sentence(text: str) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return ""
    for sentence in sentences:
        lower = sentence.lower()
        if any(marker in lower for marker in CLAIM_MARKERS):
            return sentence
    return sentences[0]


def split_sentences(text: str):
    normalized = clean_text(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", normalized)
    return [part.strip() for part in parts if len(part.strip()) >= 20]


def clean_text(text: str) -> str:
    unescaped = html.unescape(text or "")
    without_tags = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", without_tags).strip()


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def compact(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _recommendation_reason(item, direction_id: str, evidence_type: str, has_ad_risk: bool) -> str:
    direction_label = DIRECTIONS[direction_id]
    novelty = infer_novelty_signal(item)
    reason = f"值得推荐：它与「{direction_label}」直接相关，{novelty}，证据类型为{evidence_type}"
    if has_ad_risk:
        reason += "；含推广信号，已降权"
    return reason + "。"


def infer_novelty_signal(item) -> str:
    text = f"{item.title}\n{item.content_or_excerpt}".lower()
    if any(token in text for token in ["benchmark", "evaluat", "bench", "测评", "评估"]):
        return "提供了可比较的评测或 benchmark 线索"
    if any(token in text for token in ["release", "changelog", "version", "发布", "更新"]):
        return "对应新的产品、版本或项目更新"
    if any(token in text for token in ["we propose", "introduce", "提出", "新方法"]):
        return "包含新的方法、框架或问题表述"
    if item.source_type == "github":
        return "来自可落地验证的开源实现或 issue 讨论"
    if item.source_type in {"arxiv", "openalex"}:
        return "来自近期论文，适合作为前沿假设输入"
    return "相对现有源池有新的事实或论述增量"
