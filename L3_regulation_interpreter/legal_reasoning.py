"""
L3: GPT-5.1 Legal Reasoning

Computes the 4 sub-scores and generates a citation trail.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from .openai_client import chat_json, is_openai_configured


SYSTEM_PROMPT = """
You are the legal reasoning engine for an RBI/NPCI/PMLA compliance pipeline.

Your job is to reason over:
- transaction facts
- retrieved regulatory chunks
- suspicious transaction typologies

You must return ONLY valid JSON.
Be conservative, cite the retrieved material, and never invent a regulation that
is not present in the retrieved chunks.
""".strip()


USE_CASES = [
    {
        "name": "smurfing",
        "description": "Repeated smaller transactions within a short timeframe intended to avoid reporting thresholds.",
    },
    {
        "name": "mule_accounts",
        "description": "Recently opened accounts showing immediate, sustained, high-volume inflows and outflows suggestive of layering.",
    },
    {
        "name": "inconsistent_geographic_activity",
        "description": "Sudden cross-border or geographically inconsistent activity for a customer profile.",
    },
    {
        "name": "ghost_accounts",
        "description": "Dormant or long-idle accounts suddenly receiving or sending large-value funds.",
    },
]


def _serialize_chunks(regulation_chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "title": chunk.get("title"),
            "section_id": chunk.get("section_id"),
            "section_heading": chunk.get("section_heading"),
            "page_number": chunk.get("page_number"),
            "tags": chunk.get("tags"),
            "content": chunk.get("content"),
            "retrieval_score": chunk.get("retrieval_score"),
        }
        for chunk in regulation_chunks
    ]


def _build_reasoning_prompt(event: Dict[str, Any], regulation_chunks: Sequence[Dict[str, Any]]) -> str:
    return f"""
Compute the Layer 3 legal reasoning output for the following case.

Transaction / case event:
{json.dumps(event, indent=2)}

Supported suspicious activity use cases:
{json.dumps(USE_CASES, indent=2)}

Retrieved regulation chunks:
{json.dumps(_serialize_chunks(regulation_chunks), indent=2)}

Return JSON with this exact structure:
{{
  "retrieval_match": <0 to 1>,
  "rule_applicability": <0 to 1>,
  "evidence_sufficiency": <0 to 1>,
  "precedent_confidence": <0 to 1>,
  "applicable_use_cases": ["..."],
  "applicable_rules": [
    {{
      "document_id": "...",
      "title": "...",
      "section_id": "...",
      "reason": "..."
    }}
  ],
  "citation_trail": [
    {{
      "chunk_id": "...",
      "title": "...",
      "section_heading": "...",
      "excerpt": "short excerpt",
      "why_it_matters": "..."
    }}
  ],
  "verdict": "clear" | "review" | "suspicious",
  "explanation": "...",
  "final_score": <0 to 1>
}}

Scoring guidance:
- retrieval_match: how well the retrieved chunks match the case facts
- rule_applicability: how clearly the retrieved rules apply to this case
- evidence_sufficiency: whether transaction facts support a defensible decision
- precedent_confidence: whether the pattern resembles recognized suspicious typologies

Final score should reflect the weighted legal confidence after reasoning, not just retrieval quality.
If the rules are weakly related or evidence is thin, lower the score.
""".strip()


def generate_legal_analysis(event, regulation_chunks):
    """
    Uses a large language model to analyze the transaction against the retrieved regulations.
    """
    print("L3: Applying legal reasoning...")

    fallback_reason = "OPENAI_API_KEY is not configured."
    if is_openai_configured():
        try:
            return chat_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=_build_reasoning_prompt(event, regulation_chunks),
            )
        except Exception as exc:
            print(f"L3: GPT legal reasoning fallback triggered: {exc}")
            fallback_reason = str(exc)

    top_chunk = regulation_chunks[0] if regulation_chunks else {}
    analysis = {
        "retrieval_match": round(float(top_chunk.get("retrieval_score", 0.0)), 4) if top_chunk else 0.0,
        "rule_applicability": 0.65 if regulation_chunks else 0.0,
        "evidence_sufficiency": 0.55,
        "precedent_confidence": 0.5,
        "applicable_use_cases": [],
        "applicable_rules": [
            {
                "document_id": chunk.get("document_id"),
                "title": chunk.get("title"),
                "section_id": chunk.get("section_id"),
                "reason": "Retrieved as a potentially relevant rule chunk.",
            }
            for chunk in regulation_chunks[:3]
        ],
        "citation_trail": [
            {
                "chunk_id": chunk.get("chunk_id"),
                "title": chunk.get("title"),
                "section_heading": chunk.get("section_heading"),
                "excerpt": str(chunk.get("content", ""))[:240],
                "why_it_matters": "Potentially relevant to the transaction facts.",
            }
            for chunk in regulation_chunks[:3]
        ],
        "verdict": "review",
        "explanation": "Fallback legal reasoning used because the live GPT-5.1 call was unavailable.",
        "fallback_reason": fallback_reason,
        "final_score": 0.58,
    }
    return analysis
