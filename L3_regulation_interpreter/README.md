# L3: Regulation Interpreter

## What You Should Put In The JSON

Use the JSON file as a **source regulation corpus**, not as precomputed embeddings.

That means the JSON should contain:

- document metadata
- sections / clauses
- clean text
- tags you already know

Do **not** store vector embeddings in this file for now.

Why:

- embeddings may change when you switch embedding models
- chunking strategy may change later
- source-first JSON is easier to debug, audit, and re-index into Azure AI Search

## Recommended JSON Shape

```json
{
  "documents": [
    {
      "document_id": "rbi-kyc-md-2025",
      "title": "RBI Master Direction - Know Your Customer (KYC)",
      "regulator": "RBI",
      "document_type": "master_direction",
      "effective_date": "2025-01-01",
      "url": "https://...",
      "tags": ["KYC", "AML", "banking", "upi"],
      "sections": [
        {
          "section_id": "sec-1",
          "heading": "Customer Due Diligence",
          "text": "Full section text here",
          "clauses": [
            "Clause 1 text here",
            "Clause 2 text here"
          ]
        }
      ]
    }
  ]
}
```

## What To Include Per Document

- `document_id`: stable unique ID
- `title`: full title of the circular / direction / guideline
- `regulator`: usually `RBI`, but can later support `FIU-IND`, `NPCI`, `FEMA`
- `document_type`: `master_direction`, `circular`, `guideline`, `notification`
- `effective_date`: when the regulation became effective
- `url`: source link
- `tags`: compliance categories like `KYC`, `AML`, `UPI`, `NEFT`, `RTGS`, `cross_border`
- `sections`: the actual searchable content

## Pre-Chunked Or Raw?

Best option for now:

- keep it **sectioned but not embedding-ready**
- optionally split large sections into `clauses`

That gives you:

- enough structure to chunk locally now
- flexibility to re-chunk later for Azure AI Search

## Retrieval Plan

For your part of `L3`, the best path is:

1. Store regulations in source JSON form
2. Chunk sections/clauses in code
3. Rank chunks locally for now
4. Return top-k regulation chunks plus a retrieval-match score
5. Later replace local ranking with Azure AI Search hybrid retrieval

## Current Local Implementation

`hybrid_retrieval.py` now supports:

- loading a local JSON corpus
- chunking document sections
- building a query from transaction context
- ranking chunks using lexical + metadata-aware scoring
- returning `retrieval_match` and top chunks

## Why RAG Is Still The Right Choice

Yes, use a RAG-style retrieval layer here.

Not because you need generation first, but because:

- regulations change frequently
- the rule corpus is external knowledge
- you need auditable citations
- you want to retrieve exact clauses before legal reasoning

So for `L3`, retrieval-first RAG is the correct architecture.
