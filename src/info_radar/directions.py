from collections import OrderedDict


DIRECTIONS = OrderedDict(
    [
        ("macro_ai", "宏观 AI 前沿论点"),
        ("temporal", "时序模型、时序算法、时序认知、时序应用前沿"),
        ("industrial_ai", "工业控制软件 + AI 结合前沿"),
        ("ai_agents", "最佳使用 AI agent 的 GitHub 库、方法论、认知、讨论、重要观点"),
        ("human_digital_twin", "面向人类的数字孪生"),
        ("ai_philosophy", "AI 时代的泛哲学讨论"),
    ]
)

DIRECTION_PREFIX = {
    "macro_ai": "方向一",
    "temporal": "方向二",
    "industrial_ai": "方向三",
    "ai_agents": "方向四",
    "human_digital_twin": "方向五",
    "ai_philosophy": "方向六",
}
