"""
Step 3: 按每个兴趣簇查询 arXiv，返回候选论文列表。

用 arXiv 的免费 Atom API，不需要任何 key。
"""

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta


ARXIV_BASE = "http://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


def _parse_atom(xml_bytes: bytes) -> list[dict]:
    """解析 arXiv Atom XML，返回论文列表。"""
    root = ET.fromstring(xml_bytes)
    papers = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        arxiv_id = entry.find(f"{{{ATOM_NS}}}id").text.strip()
        # id 格式: http://arxiv.org/abs/2401.12345v1 → 取 2401.12345
        arxiv_id = arxiv_id.split("/abs/")[-1].split("v")[0]

        title = entry.find(f"{{{ATOM_NS}}}title").text.strip().replace("\n", " ")
        abstract = entry.find(f"{{{ATOM_NS}}}summary").text.strip().replace("\n", " ")
        submitted = entry.find(f"{{{ATOM_NS}}}published").text[:10]  # YYYY-MM-DD

        authors = [
            a.find(f"{{{ATOM_NS}}}name").text
            for a in entry.findall(f"{{{ATOM_NS}}}author")
        ]

        categories = [
            c.attrib.get("term", "")
            for c in entry.findall(f"{{{ATOM_NS}}}category")
        ]

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "submitted": submitted,
            "authors": authors[:5],  # 最多保留前 5 位作者
            "categories": categories,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
        })

    return papers


def search_arxiv(query: str, max_results: int = 30, days_back: int = 14) -> list[dict]:
    """
    查询 arXiv。

    query: 检索词，来自 interest cluster 的 retrieval_queries
    days_back: 只看最近 N 天的论文
    """
    cutoff = str(date.today() - timedelta(days=days_back))

    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })

    url = f"{ARXIV_BASE}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_bytes = resp.read()
    except Exception as e:
        print(f"  ⚠ arXiv 请求失败 ({query[:40]}...): {e}")
        return []

    papers = _parse_atom(xml_bytes)

    # 过滤日期
    papers = [p for p in papers if p["submitted"] >= cutoff]

    return papers


def retrieve_all(profile: dict, days_back: int = 14) -> list[dict]:
    """
    对所有兴趣簇依次检索，合并去重，返回候选列表。

    arXiv API 建议请求间隔 3 秒，避免被限速。
    """
    seen_ids = set()
    all_candidates = []

    for interest in profile["interests"]:
        label = interest["label"]
        queries = interest["retrieval_queries"]

        for query in queries:
            print(f"  → 检索 [{label}]: {query[:50]}...")
            results = search_arxiv(query, days_back=days_back)

            for paper in results:
                if paper["arxiv_id"] not in seen_ids:
                    seen_ids.add(paper["arxiv_id"])
                    paper["source_cluster"] = label  # 记录来自哪个兴趣簇
                    all_candidates.append(paper)

            time.sleep(3)  # 礼貌性等待

    print(f"\n共检索到 {len(all_candidates)} 篇候选（去重后）")
    return all_candidates
