import pytest

from info_radar.publish import PublishValidationError, validate_processed_morning_brief


def test_publish_rejects_core_entries_with_more_than_three_explicit_deep_links() -> None:
    markdown = (
        "# 2026-07-01 信息雷达晨报\n\n"
        "## 核心阅读区\n\n"
        "### 1. Agent 工程治理需要拆成多个独立判断 [[#D1. Agent 运行态治理|「link」]]\n"
        "今天的候选材料显示，agent 工程正在同时进入运行态治理、任务复现、平台稳定性和成本控制四条线索。"
        "如果把这些材料硬合成一个大判断，读者只能看到模糊方向，看不到内部论点的差异，也无法判断哪条证据真正支撑了哪一个决策。"
        "因此核心阅读区应该把不同论点离散成多个判断，每个判断只显性绑定少量最关键证据。\n\n"
        "推荐理由：这个约束能让晨报从来源罗列升级为观点沉淀，避免一个判断吞掉过多材料。"
        "它也迫使加工过程说明证据和观点之间的精确关系，便于读者继续深读和复盘。\n\n"
        "深读入口：[[#D1. Agent 运行态治理|D1]] · [[#D2. Agent 任务复现|D2]] · "
        "[[#D3. Agent 平台稳定性|D3]] · [[#D4. Agent 成本控制|D4]]\n\n"
        "## 深度阅读区\n\n"
        "### D1. Agent 运行态治理 [[#E1. Agent 运行态治理|「证据」]]\n"
        "这张卡讨论运行态治理如何影响 agent 产品边界。\n\n"
        "### D2. Agent 任务复现 [[#E2. Agent 任务复现|「证据」]]\n"
        "这张卡讨论任务复现如何影响 agent 评测可信度。\n\n"
        "### D3. Agent 平台稳定性 [[#E3. Agent 平台稳定性|「证据」]]\n"
        "这张卡讨论平台稳定性如何影响 agent 采用决策。\n\n"
        "### D4. Agent 成本控制 [[#E4. Agent 成本控制|「证据」]]\n"
        "这张卡讨论成本控制如何影响 agent 的真实部署。\n\n"
        "## 证据区\n\n"
        "### E1. Agent 运行态治理\n"
        "- 来源：https://example.com/agent-runtime\n\n"
        "### E2. Agent 任务复现\n"
        "- 来源：https://example.com/agent-replay\n\n"
        "### E3. Agent 平台稳定性\n"
        "- 来源：https://example.com/agent-stability\n\n"
        "### E4. Agent 成本控制\n"
        "- 来源：https://example.com/agent-cost\n"
    )

    with pytest.raises(PublishValidationError, match="最多显性关联 3 个"):
        validate_processed_morning_brief(markdown)
