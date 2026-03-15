"""
Step 1: Parse your Zotero BibTeX export.

Zotero 导出时选 BibTeX 格式，勾上 "Export Notes" 和 "Export Files"，
最重要的是确保勾选了 "Include Abstracts"。
"""

import json
import bibtexparser
from pathlib import Path


def parse_bibtex(bib_path: str) -> list[dict]:
    """
    读取 .bib 文件，返回标准化的 paper 列表。
    每篇论文保留：title, abstract, keywords, year, authors, entry_type。
    """
    path = Path(bib_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到文件：{bib_path}")

    with open(path, encoding="utf-8") as f:
        db = bibtexparser.load(f)

    papers = []
    for entry in db.entries:
        # 跳过书籍、网页等非论文条目
        if entry.get("ENTRYTYPE", "").lower() in ("book", "misc", "online"):
            if not entry.get("abstract"):
                continue

        title = entry.get("title", "").replace("{", "").replace("}", "").strip()
        abstract = entry.get("abstract", "").strip()
        keywords = entry.get("keywords", "").strip()
        year = entry.get("year", "0")

        # 没有 title 的跳过
        if not title:
            continue

        # 用 title + abstract 作为这篇论文的文本表示
        text = f"{title}. {abstract}" if abstract else title

        papers.append({
            "title": title,
            "abstract": abstract,
            "keywords": keywords,
            "year": int(year) if year.isdigit() else 0,
            "authors": entry.get("author", ""),
            "text": text,  # 聚类时用这个字段
        })

    return papers


def load_or_parse(bib_path: str, cache_path: str = "profiles/parsed-library.json") -> list[dict]:
    """
    如果已有缓存就直接读，否则重新解析。
    每次 .bib 文件修改时间变化才重新解析。
    """
    bib = Path(bib_path)
    cache = Path(cache_path)

    if cache.exists():
        cached = json.loads(cache.read_text())
        if cached.get("mtime") == bib.stat().st_mtime:
            return cached["papers"]

    papers = parse_bibtex(bib_path)
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps({
        "mtime": bib.stat().st_mtime,
        "papers": papers,
    }, ensure_ascii=False, indent=2))

    return papers
