"""
Step 2: 把你的文献库聚类成 4–8 个兴趣簇，生成 research-interest.json。

原理：用 TF-IDF 把每篇论文变成向量，然后 k-means 聚类。
不需要 LLM，纯数学操作。LLM 只用来给每个簇起一个人类可读的名字。
"""

import json
import re
from datetime import date
from pathlib import Path

import numpy as np
from anthropic import Anthropic
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score


def _best_k(matrix, k_range=(4, 9)) -> int:
    """用 silhouette score 自动选最优 k。"""
    best_k, best_score = k_range[0], -1
    for k in range(*k_range):
        if k >= matrix.shape[0]:
            break
        labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(matrix)
        score = silhouette_score(matrix, labels)
        if score > best_score:
            best_score, best_k = score, k
    return best_k


def _top_terms(tfidf_matrix, vectorizer, cluster_labels, cluster_id, n=12) -> list[str]:
    """取某个 cluster 里 TF-IDF 权重最高的词。"""
    indices = np.where(cluster_labels == cluster_id)[0]
    centroid = tfidf_matrix[indices].mean(axis=0)
    centroid = np.asarray(centroid).flatten()
    top_indices = centroid.argsort()[::-1][:n]
    terms = vectorizer.get_feature_names_out()
    return [terms[i] for i in top_indices]


def _name_cluster_with_llm(top_terms: list[str], anchor_titles: list[str], api_key: str | None, lang: str = "en") -> tuple[str, str]:
    """
    用 Claude 给 cluster 起名。如果没有 API key，就用 top_terms[0] 代替。
    返回 (label, description)。
    """
    if not api_key:
        return top_terms[0], f"Cluster around: {', '.join(top_terms[:5])}"

    client = Anthropic(api_key=api_key)

    if lang == "zh":
        prompt = f"""根据研究集群的这些顶级关键词：{', '.join(top_terms)}

以及这些代表性论文标题：
{chr(10).join(f'- {t}' for t in anchor_titles)}

请写出：
1. 这个研究领域的简短标签（3-5 个词，名词短语）
2. 这个集群涵盖内容的 1 句描述

仅返回 JSON：{{"label": "...", "description": "..."}}"""
    else:
        prompt = f"""Given these top keywords for a research cluster: {', '.join(top_terms)}

And these representative paper titles:
{chr(10).join(f'- {t}' for t in anchor_titles)}

Please write:
1. A short label for this research area (3-5 words, noun phrase)
2. A 1-sentence description of what this cluster covers

Return only JSON: {{"label": "...", "description": "..."}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    raw = re.sub(r'\n\s+', ' ', raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  cluster naming JSON parse failed: {e}")
        print(f"  response: {raw[:200]}")
        raw = re.sub(r'(?<!\\)"(?=[^"]*"[^"]*$)', '\\"', raw)
        try:
            data = json.loads(raw)
        except:
            return top_terms[0], f"Keywords: {', '.join(top_terms[:5])}"
    return data["label"], data["description"]


def build_profile(
    papers: list[dict],
    output_path: str = "profiles/research-interest.json",
    api_key: str | None = None,
    auto_k: bool = True,
    lang: str = "en",
) -> dict:
    """
    主入口：从论文列表生成 research-interest.json。

    papers: parse_bibtex() 的输出
    output_path: 写入位置
    api_key: Anthropic API key，用于给 cluster 命名（可选）
    auto_k: True = 自动选 k；False = 固定 k=6
    """
    if len(papers) < 4:
        raise ValueError("至少需要 4 篇论文才能聚类。")

    texts = [p["text"] for p in papers]

    # TF-IDF 向量化，过滤掉太常见和太罕见的词
    vectorizer = TfidfVectorizer(
        max_features=3000,
        stop_words="english",
        min_df=2,
        max_df=0.85,
        ngram_range=(1, 2),  # 包括 bigram，比如 "neural network"
    )
    matrix = vectorizer.fit_transform(texts)

    # 选 k
    k = _best_k(matrix.toarray()) if auto_k else 6

    # 聚类
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(matrix)

    interests = []
    for cluster_id in range(k):
        indices = np.where(labels == cluster_id)[0]
        cluster_papers = [papers[i] for i in indices]

        # 找最靠近 centroid 的 3 篇作为 anchor
        cluster_matrix = matrix[indices]
        centroid = cluster_matrix.mean(axis=0)
        # 转换为密集数组计算欧氏距离
        cluster_dense = np.asarray(cluster_matrix.todense())
        centroid_dense = np.asarray(centroid).flatten()
        distances = np.linalg.norm(cluster_dense - centroid_dense, axis=1)
        anchor_indices = distances.argsort()[:3]
        anchors = [cluster_papers[i]["title"] for i in anchor_indices]

        top_terms = _top_terms(matrix, vectorizer, labels, cluster_id)

        label, description = _name_cluster_with_llm(top_terms, anchors, api_key, lang)

        # 从 top_terms 生成 2 个 arXiv 检索 query
        q1 = " ".join(top_terms[:4])
        q2 = " ".join(top_terms[4:8])

        interests.append({
            "label": label,
            "description": description,
            "retrieval_queries": [q1, q2],
            "anchor_titles": anchors,
            "top_terms": top_terms,
            "paper_count": int(len(indices)),
        })

    profile = {
        "interests": interests,
        "last_updated": str(date.today()),
        "library_size": len(papers),
        "k": k,
    }

    Path(output_path).parent.mkdir(exist_ok=True)
    Path(output_path).write_text(json.dumps(profile, ensure_ascii=False, indent=2))

    return profile
