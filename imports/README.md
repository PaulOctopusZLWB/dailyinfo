# 手工导入

`imports/` 用于 Bilibili、X、知识星球、微信公众号等 v0 不直接抓取或不应绕过权限的平台。

## JSONL

每行一个材料：

```json
{"title":"Agent workflow repo","url":"https://github.com/example/agent-workflow","source_name":"X 手工导入","published_at":"2026-06-30T08:00:00+08:00","content_or_excerpt":"摘录或你自己的摘要。","direction_hint":"ai_agents"}
```

## Markdown

```markdown
## B 站时序模型分享
url: https://www.bilibili.com/video/BVxxxx
source_name: Bilibili 手工导入
published_at: 2026-06-30T09:00:00+08:00
direction_hint: temporal

只放必要摘录或自己的摘要，不复制受限全文。
```
