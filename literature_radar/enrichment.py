"""
Step 5: 让 Claude 读排名靠前的候选论文，写推荐理由。

这是 pipeline 里唯一调用 LLM 的步骤（除了 profile 命名）。
Claude 只能填 review 字段，不能改论文的其他元数据。
"""

import json
import re

from anthropic import Anthropic


ENRICHMENT_SYSTEM_ZH = """你是一位研究助手，帮助研究者找到相关论文。
对于每篇论文，你需要：
1. 判断它是否值得出现在摘要中（keep: true/false）
2. 写一个简短的推荐和背景说明

要直接诚实。如果一篇论文只是边缘相关，就说出来。
如果你无法评估（太专业化），设置 keep 为 false 并在 caveats 中解释。
用简洁的散文写作，字段内不要用项目符号。用中文回复。
只返回有效的 JSON，不要 markdown 代码块。"""

ENRICHMENT_SYSTEM_EN = """You are a research assistant helping a researcher find relevant papers.
For each paper, you need to:
1. Decide if it belongs in the digest (keep: true/false)
2. Write a short recommendation and context

Be direct and honest. If a paper is only marginally relevant, say so.
If you cannot evaluate it (too specialized), set keep to false and explain in caveats.
Write in concise prose, no bullet points inside fields. Reply in English.
Return only valid JSON, no markdown code blocks."""


def enrich_candidates(
    candidates: list[dict],
    profile: dict,
    api_key: str,
    digest_size: int = 5,
    lang: str = "en",
) -> list[dict]:
    """
    对 top candidates 调用 Claude，填入 review 字段。

    candidates: ranker.rank_candidates() 的输出（已排序）
    digest_size: 最终 digest 保留几篇（Claude 从候选里选）
    """
    client = Anthropic(api_key=api_key)
    system_prompt = ENRICHMENT_SYSTEM_ZH if lang == "zh" else ENRICHMENT_SYSTEM_EN

    interest_summary = "\n".join(
        f"- {i['label']}: {i['description']}" for i in profile["interests"]
    )

    papers_text = ""
    for idx, p in enumerate(candidates):
        papers_text += f"""
Paper {idx + 1}:
Title: {p['title']}
Authors: {', '.join(p['authors'])}
Submitted: {p['submitted']}
arXiv: {p['url']}
Abstract: {p['abstract'][:600]}
Relevance cluster: {p.get('source_cluster', 'unknown')}
Score: {p['scores']['final']:.3f}
---"""

    if lang == "zh":
        user_prompt = f"""研究者的兴趣方向：
{interest_summary}

以下是 {len(candidates)} 篇候选论文，按相关性评分排序。
请从中选出最好的 {digest_size} 篇纳入摘要（对这些论文设置 keep: true）。
对所有论文填写 review 字段。

{papers_text}

返回一个包含 {len(candidates)} 个对象的 JSON 数组，每篇论文一个，顺序相同：
[
  {{
    "arxiv_id": "...",
    "keep": true 或 false,
    "recommendation": "2-3 句话说明为什么这篇论文值得关注",
    "why_it_matters": "与研究者工作的连接或该领域的开放问题",
    "caveats": "局限性、范围限制或浅读而非深读的原因",
    "anchor_connection": "与其现有工作最可能相关的概念或领域"
  }},
  ...
]"""
    else:
        user_prompt = f"""Researcher's interests:
{interest_summary}

Below are {len(candidates)} candidate papers ranked by relevance score.
Select the best {digest_size} for the digest (set keep: true for those).
Fill in the review fields for all papers.

{papers_text}

Return a JSON array of {len(candidates)} objects, one per paper, in the same order:
[
  {{
    "arxiv_id": "...",
    "keep": true or false,
    "recommendation": "2-3 sentences on why this paper is worth reading",
    "why_it_matters": "connection to the researcher's work or open questions in the field",
    "caveats": "limitations, scope restrictions, or reasons to skim rather than read deeply",
    "anchor_connection": "concepts or areas most relevant to their existing work"
  }},
  ...
]"""

    print("  → Asking Claude to filter and write recommendations...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    # 清理可能的格式问题
    raw = re.sub(r'\n\s+', ' ', raw)  # 替换换行符和多余空格

    try:
        reviews = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON 解析失败: {e}")
        print(f"  响应内容（前 500 字）: {raw[:500]}")
        # 尝试修复未转义的引号
        raw = re.sub(r'(?<!\\)"(?=[^"]*"[^"]*$)', '\\"', raw)
        try:
            reviews = json.loads(raw)
        except:
            raise

    # 把 review 合并回 candidates
    review_map = {r["arxiv_id"]: r for r in reviews}
    enriched = []
    for paper in candidates:
        aid = paper["arxiv_id"]
        review = review_map.get(aid, {})
        enriched.append({
            **paper,
            "review": {
                "keep": review.get("keep", False),
                "recommendation": review.get("recommendation", ""),
                "why_it_matters": review.get("why_it_matters", ""),
                "caveats": review.get("caveats", ""),
                "anchor_connection": review.get("anchor_connection", ""),
            }
        })

    return enriched
