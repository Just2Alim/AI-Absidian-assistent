"""
Hybrid local RAG search.

The first implementation is dependency-light: FTS candidates plus token-overlap
semantic scoring. It is deliberately local and deterministic. A future embedding
model can be plugged into this module without changing the API.
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List

from database import get_note_documents, search_notes


TOKEN_RE = re.compile(r"[\w\u0400-\u04FF]{3,}", re.UNICODE)


def _tokens(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[token] * b[token] for token in common)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _snippet(body: str, query_terms: List[str], length: int = 280) -> str:
    text = re.sub(r"\s+", " ", body or "").strip()
    if not text:
        return ""
    lower = text.lower()
    positions = [lower.find(term) for term in query_terms if lower.find(term) >= 0]
    start = max(min(positions) - 80, 0) if positions else 0
    snippet = text[start:start + length]
    return ("..." if start else "") + snippet + ("..." if start + length < len(text) else "")


async def hybrid_rag_search(query: str, limit: int = 10) -> Dict[str, Any]:
    query_terms = _tokens(query)
    query_counter = Counter(query_terms)

    fts_results = await search_notes(query, limit=max(limit * 2, 20))
    fts_ids = {item["id"] for item in fts_results}
    fts_rank = {item["id"]: index for index, item in enumerate(fts_results)}

    documents = await get_note_documents()
    scored = []
    for doc in documents:
        body = " ".join([
            doc.get("title") or "",
            doc.get("folder") or "",
            doc.get("tags") or "",
            doc.get("body") or "",
        ])
        overlap_score = _cosine(query_counter, Counter(_tokens(body)))
        fts_boost = 1.0 / (1 + fts_rank[doc["id"]]) if doc["id"] in fts_ids else 0.0
        score = overlap_score * 0.72 + fts_boost * 0.28
        if score <= 0:
            continue
        scored.append({
            "id": doc["id"],
            "path": doc["path"],
            "title": doc["title"],
            "folder": doc["folder"],
            "modified_at": doc["modified_at"],
            "word_count": doc["word_count"],
            "score": round(score, 5),
            "snippet": _snippet(doc.get("body") or "", query_terms),
            "source": "hybrid-local",
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    top = scored[:limit]
    context = "\n\n".join(
        f"### {item['title']} ({item['path']})\n{item['snippet']}"
        for item in top
    )
    return {
        "query": query,
        "results": top,
        "context": context,
        "engine": "fts+local-token-semantic",
    }
