"""
Step 6: 把筛选后的论文渲染成 Markdown digest 文件。
"""

from datetime import date
from pathlib import Path

LABELS = {
    "zh": {
        "selected": "从 {total} 篇候选论文中精选 {kept} 篇。",
        "authors": "作者",
        "submitted": "提交日期",
        "relevance": "相关性评分",
        "why_read": "为什么要读",
        "connection": "与你的工作的联系",
        "caveats": "注意事项",
        "anchor": "相关研究方向",
        "et_al": "等",
        "no_papers": "本期没有选出论文。",
    },
    "en": {
        "selected": "{kept} papers selected from {total} candidates.",
        "authors": "Authors",
        "submitted": "Submitted",
        "relevance": "Relevance score",
        "why_read": "Why read this",
        "connection": "Connection to your work",
        "caveats": "Caveats",
        "anchor": "Related research areas",
        "et_al": "et al.",
        "no_papers": "No papers selected for this digest.",
    },
}


def render_markdown(enriched: list[dict], output_path: str = "reports/digest.md", lang: str = "en") -> str:
    kept = [p for p in enriched if p.get("review", {}).get("keep", False)]
    L = LABELS.get(lang, LABELS["en"])

    if not kept:
        return L["no_papers"]

    today = str(date.today())
    total_candidates = len(enriched)

    lines = [
        f"# Literature Radar — {today}",
        f"",
        L["selected"].format(total=total_candidates, kept=len(kept)),
        f"",
        "---",
        "",
    ]

    for p in kept:
        r = p["review"]
        authors_str = ", ".join(p["authors"][:3])
        if len(p["authors"]) > 3:
            authors_str += f" {L['et_al']}"

        lines += [
            f"## {p['title']}",
            f"",
            f"**{L['authors']}:** {authors_str}  ",
            f"**{L['submitted']}:** {p['submitted']}  ",
            f"**arXiv:** [{p['arxiv_id']}]({p['url']})  ",
            f"**{L['relevance']}:** {p['scores']['final']:.3f}",
            f"",
            f"> {p['abstract'][:300]}{'...' if len(p['abstract']) > 300 else ''}",
            f"",
            f"**{L['why_read']}:** {r['recommendation']}",
            f"",
            f"**{L['connection']}:** {r['why_it_matters']}",
            f"",
        ]

        if r.get("caveats"):
            lines += [f"**{L['caveats']}:** {r['caveats']}", ""]

        if r.get("anchor_connection"):
            lines += [f"**{L['anchor']}:** {r['anchor_connection']}", ""]

        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    Path(output_path).parent.mkdir(exist_ok=True)
    Path(output_path).write_text(content, encoding="utf-8")
    return content

