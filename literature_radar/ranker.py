"""
Step 4: 给候选论文打分，选出最值得看的前 N 篇。

两个信号：
- topic_fit (0.70): 摘要与兴趣簇关键词的 TF-IDF 相似度
- recency_boost (0.30): 越新的论文分越高，指数衰减

不需要 LLM，纯数学。
"""

import math
from datetime import date

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _recency_score(submitted: str, half_life_days: int = 7) -> float:
    """
    距今越近分越高。
    half_life_days=7 表示 7 天前的论文得分是今天的一半。
    """
    try:
        delta = (date.today() - date.fromisoformat(submitted)).days
    except Exception:
        return 0.0
    return math.exp(-math.log(2) * delta / half_life_days)


def rank_candidates(
    candidates: list[dict],
    profile: dict,
    top_n: int = 20,
    w_topic: float = 0.70,
    w_recency: float = 0.30,
) -> list[dict]:
    """
    给每篇候选论文打分，返回排序后的前 top_n 篇。

    candidates: retrieve_all() 的输出
    profile: research-interest.json 的内容
    top_n: 保留前多少篇进入 agent enrichment
    """
    if not candidates:
        return []

    # 把所有兴趣簇的关键词合并成一个"兴趣文档"
    # 用这个来衡量候选论文的整体相关性
    interest_texts = []
    for interest in profile["interests"]:
        terms = " ".join(interest["top_terms"])
        desc = interest["description"]
        interest_texts.append(f"{desc} {terms}")

    combined_interest = " ".join(interest_texts)

    # 候选摘要
    candidate_texts = [
        f"{c['title']} {c['abstract']}" for c in candidates
    ]

    # TF-IDF 向量化：把兴趣文本和候选文本放在一起训练 vocab
    all_texts = [combined_interest] + candidate_texts
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(all_texts)

    interest_vec = matrix[0]
    candidate_matrix = matrix[1:]

    # cosine similarity：每篇候选 vs 兴趣文档
    similarities = cosine_similarity(candidate_matrix, interest_vec).flatten()

    # 综合评分
    scored = []
    for i, candidate in enumerate(candidates):
        topic_score = float(similarities[i])
        recency = _recency_score(candidate["submitted"])
        final = w_topic * topic_score + w_recency * recency

        scored.append({
            **candidate,
            "scores": {
                "topic_fit": round(topic_score, 4),
                "recency": round(recency, 4),
                "final": round(final, 4),
            }
        })

    # 按 final score 降序
    scored.sort(key=lambda x: x["scores"]["final"], reverse=True)

    return scored[:top_n]
