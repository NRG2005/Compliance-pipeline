"""
L3: Hybrid Retrieval

Current goal:
- develop retrieval locally against a JSON regulation corpus
- keep the same interfaces easy to swap to Azure AI Search later

Design:
- input JSON stores source regulation content, not embeddings
- this module chunks, indexes, and ranks clauses/sections at runtime
- ranking is currently lexical plus metadata-aware; later the vector part can
  be replaced by Azure AI Search hybrid retrieval without changing callers
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from config import get_config

config = get_config()

DEFAULT_LOCAL_CORPUS_PATH = os.environ.get(
    "LOCAL_REGULATION_CORPUS_PATH",
    str(Path(__file__).with_name("sample_regulations.json")),
)
DEFAULT_TOP_K = int(os.environ.get("L3_TOP_K", "5"))
DEFAULT_CHUNK_WORDS = int(os.environ.get("L3_CHUNK_WORDS", "140"))
DEFAULT_CHUNK_OVERLAP = int(os.environ.get("L3_CHUNK_OVERLAP", "30"))


def _tokenize(text: Any) -> List[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def build_search_query(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts the transaction/event context into a retrieval query object.

    This is intentionally simple and auditable for now. Later the same query
    object can be translated into Azure AI Search keyword + vector inputs.
    """
    channel = str(event.get("channel", "")).upper()
    amount = event.get("amount")
    amount_band = "small"
    try:
        numeric_amount = float(amount)
        if numeric_amount >= 1_000_000:
            amount_band = "very_large"
        elif numeric_amount >= 200_000:
            amount_band = "large"
        elif numeric_amount >= 50_000:
            amount_band = "medium"
    except (TypeError, ValueError):
        numeric_amount = None

    keywords = [
        channel.lower(),
        "rbi",
        "compliance",
        "transaction",
        "payment",
        amount_band,
    ]

    for key in ("sender_bank", "receiver_bank", "receiver_type", "purpose_code", "channel"):
        value = event.get(key)
        if value:
            keywords.extend(_tokenize(value))

    for key in ("scenario_tag", "funds_in_out_pattern", "l3_investigation_notes", "purpose_code_declared"):
        value = event.get(key)
        if value:
            keywords.extend(_tokenize(value))

    for key in ("t2_watchlist_hit", "t3_risk_label", "geo_country", "transaction_type"):
        value = event.get(key)
        if value:
            keywords.extend(_tokenize(value))

    return {
        "channel": channel,
        "amount": numeric_amount,
        "amount_band": amount_band,
        "keywords": _dedupe_preserve_order(keywords),
        "query_text": " ".join(_dedupe_preserve_order(keywords)),
    }


def _window_words(text: str, chunk_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if len(words) <= chunk_words:
        return [text.strip()] if text.strip() else []

    chunks = []
    start = 0
    stride = max(chunk_words - overlap_words, 1)
    while start < len(words):
        window = words[start : start + chunk_words]
        if not window:
            break
        chunks.append(" ".join(window).strip())
        start += stride
    return chunks


def chunk_regulation_document(
    document: Dict[str, Any],
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Converts one regulation document into searchable chunks.

    Expected source shape:
    {
      "document_id": "...",
      "title": "...",
      "regulator": "RBI",
      "document_type": "master_direction",
      "effective_date": "2026-01-01",
      "url": "...",
      "tags": ["KYC", "AML", "UPI"],
      "sections": [
        {
          "section_id": "...",
          "heading": "...",
          "text": "...",
          "clauses": ["...", "..."]
        }
      ]
    }
    """
    document_id = document.get("document_id") or document.get("id") or document.get("doc_id")
    title = document.get("title", "")
    tags = document.get("tags") or []
    regulator = document.get("regulator", "RBI")
    document_type = document.get("document_type", "regulation")
    effective_date = document.get("effective_date")
    url = document.get("url")

    chunked_rows: List[Dict[str, Any]] = []
    sections = document.get("sections") or []
    if not sections and document.get("text"):
        sections = [{"section_id": "full_text", "heading": title, "text": document["text"], "clauses": []}]

    for section in sections:
        section_id = section.get("section_id") or section.get("id") or "section"
        heading = section.get("heading", "")
        clauses = section.get("clauses") or []

        candidate_texts: List[str] = []
        if section.get("text"):
            candidate_texts.extend(_window_words(str(section["text"]), chunk_words, overlap_words))
        for clause in clauses:
            if clause:
                candidate_texts.extend(_window_words(str(clause), chunk_words, overlap_words))

        for index, chunk_text in enumerate(candidate_texts, start=1):
            searchable_text = " ".join(part for part in [title, heading, chunk_text, " ".join(tags)] if part)
            chunked_rows.append(
                {
                    "chunk_id": f"{document_id}:{section_id}:{index}",
                    "document_id": document_id,
                    "title": title,
                    "regulator": regulator,
                    "document_type": document_type,
                    "effective_date": effective_date,
                    "url": url,
                    "tags": tags,
                    "section_id": section_id,
                    "section_heading": heading,
                    "content": chunk_text,
                    "searchable_text": searchable_text,
                }
            )

    return chunked_rows


def load_regulation_corpus(
    corpus_path: Optional[str] = None,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    path = Path(corpus_path or DEFAULT_LOCAL_CORPUS_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Regulation corpus not found at {path}. Add your JSON corpus or set LOCAL_REGULATION_CORPUS_PATH."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        documents = payload.get("documents") or payload.get("regulations") or [payload]
    elif isinstance(payload, list):
        documents = payload
    else:
        raise ValueError("Regulation corpus JSON must be a list or an object with a 'documents' field.")

    chunks: List[Dict[str, Any]] = []
    for document in documents:
        chunks.extend(chunk_regulation_document(document, chunk_words=chunk_words, overlap_words=overlap_words))
    return chunks


def _metadata_boost(chunk: Dict[str, Any], query: Dict[str, Any]) -> float:
    boost = 0.0
    channel = query.get("channel")
    tags = {str(tag).lower() for tag in chunk.get("tags", [])}
    doc_type = str(chunk.get("document_type", "")).lower()
    text = chunk.get("searchable_text", "").lower()

    if channel and channel.lower() in tags:
        boost += 0.45
    if channel and channel.lower() in text:
        boost += 0.2
    if "kyc" in tags or "aml" in tags:
        boost += 0.05
    if doc_type in {"master_direction", "guideline", "circular"}:
        boost += 0.05
    return boost


def _lexical_score(query_tokens: Sequence[str], chunk: Dict[str, Any]) -> float:
    chunk_tokens = _tokenize(chunk.get("searchable_text"))
    if not chunk_tokens:
        return 0.0

    query_counter = Counter(query_tokens)
    chunk_counter = Counter(chunk_tokens)
    overlap = sum(min(query_counter[token], chunk_counter[token]) for token in query_counter)
    norm = math.sqrt(len(query_tokens) * len(chunk_tokens)) or 1.0
    return overlap / norm


def _rank_chunks(chunks: Sequence[Dict[str, Any]], query: Dict[str, Any], top_k: int) -> List[Dict[str, Any]]:
    query_tokens = _tokenize(query.get("query_text"))
    ranked_rows: List[Dict[str, Any]] = []
    for chunk in chunks:
        lexical = _lexical_score(query_tokens, chunk)
        score = lexical + _metadata_boost(chunk, query)
        if score <= 0:
            continue
        ranked_rows.append(
            {
                **chunk,
                "retrieval_score": round(score, 4),
                "lexical_score": round(lexical, 4),
            }
        )

    ranked_rows.sort(key=lambda row: row["retrieval_score"], reverse=True)
    return ranked_rows[:top_k]


def _compute_retrieval_match(top_chunks: Sequence[Dict[str, Any]]) -> float:
    """
    Produces the retrieval-match sub-score expected by L3.

    Current interpretation:
    - high if the top result is strong and the top few results are consistent
    - low if results are weak or sparse
    """
    if not top_chunks:
        return 0.0

    top_score = float(top_chunks[0].get("retrieval_score", 0.0))
    avg_top = sum(float(row.get("retrieval_score", 0.0)) for row in top_chunks[:3]) / min(len(top_chunks), 3)
    match_score = min(1.0, (0.65 * top_score) + (0.35 * avg_top))
    return round(match_score, 4)


def search_regulations(
    event: Dict[str, Any],
    corpus_path: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
) -> Dict[str, Any]:
    """
    Performs local hybrid-style retrieval on the regulation corpus.

    Return shape:
    {
      "query": {...},
      "retrieval_match": 0.0-1.0,
      "chunks": [...]
    }
    """
    print("L3: Searching for relevant regulations...")
    query = build_search_query(event)
    chunks = load_regulation_corpus(corpus_path=corpus_path)
    top_chunks = _rank_chunks(chunks, query, top_k=top_k)
    retrieval_match = _compute_retrieval_match(top_chunks)

    return {
        "query": query,
        "retrieval_match": retrieval_match,
        "chunks": top_chunks,
        "backend": "local_json_corpus",
        "future_backend": "azure_ai_search_hybrid",
    }
