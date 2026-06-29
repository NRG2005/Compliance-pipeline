# Compliance Pipeline

An end-to-end **Anti-Money Laundering (AML) compliance pipeline** for Indian financial institutions. The system ingests UPI/NEFT/RTGS/IMPS/SWIFT transactions, runs them through 8 processing layers (L0–L7), and produces legally defensible Suspicious Transaction Reports (STRs) compliant with **RBI**, **FIU-IND**, **PMLA**, **FEMA**, and **NPCI** regulations.

Built with a **FastAPI** backend, a **React + TypeScript** frontend, and designed for **Azure-native** deployment with local development fallbacks.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLIANCE PIPELINE                                   │
│                                                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │    L0    │───▶│    L1    │───▶│    L2    │───▶│    L3    │───▶│    L4    │     │
│  │ Ingest   │    │ Routing  │    │ Monitor  │    │ Legal AI │    │ STR Gen  │     │
│  └──────────┘    └────┬─────┘    └──────────┘    └──────────┘    └──────────┘     │
│                       │                                                │           │
│                       │ short-circuit                                  ▼           │
│                       │              ┌──────────┐    ┌──────────┐  ┌──────────┐   │
│                       └─────────────▶│    L6    │    │    L5    │  │    L7    │   │
│                                      │  Audit   │    │  Review  │  │ Reg Watch│   │
│                                      └──────────┘    └──────────┘  └──────────┘   │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Layer Data Flow

```
  CSV Upload
      │
      ▼
┌─────────────┐    Azure Queue Storage
│  L0 Ingest  │───────────────────────────▶ tx-events queue
└──────┬──────┘
       │
       ▼
┌─────────────┐    MinHash LSH similarity check
│  L1 Routing │    + regulation hash freshness
└──────┬──────┘
       │
       ├── similarity ≥ 0.80 & hash unchanged ──▶ SHORT-CIRCUIT to L6 (Audit)
       │
       ▼  (no match or stale hash)
┌─────────────┐    6 parallel detectors (C1–C6)
│  L2 Monitor │    weighted suspicion score
└──────┬──────┘
       │
       ├── score = 0 ──▶ CLEAN (skip L3–L5)
       │
       ▼  (flagged)
┌──────────────┐   Dual retrieval: Azure AI Search + ChromaDB
│  L3 Legal AI │   Dual LLM eval: Gemini 2.5 Flash + Ollama Phi-4
└──────┬───────┘
       │
       ├── confidence < 0.60 ──▶ skip L4
       │
       ▼  (confidence ≥ 0.60)
┌─────────────┐    SLM mapping → XML serialization → XSD/PRV validation
│ L4 STR Gen  │    Self-healing loop (max 3 attempts)
└──────┬──────┘
       │
       ├── FILED ──▶ PDF review copy generated
       ├── FAILED ──▶ escalate to L5
       │
       ▼
┌─────────────┐    Human review queue
│  L5 Review  │    7-day FIU-IND deadline tracking
└──────┬──────┘
       │
       ▼
┌─────────────┐    SHA-256 hash chain
│  L6 Audit   │    Immutable blob storage
└──────┬──────┘
       │
       ▼
┌─────────────┐    Cron-based (every 6h)
│ L7 Reg Watch│    Regulation scraping & hash invalidation
└─────────────┘
```

---

## Layer Details

### L0 — Event Ingestion

Reads transaction CSVs and publishes each row as a JSON message to **Azure Queue Storage** (`tx-events` queue). Supports 5 payment channels: UPI, NEFT, RTGS, IMPS, and SWIFT.

- **Transport**: Azure Queue Storage (falls back to in-process mode in dev)
- **Schema**: 30+ fields per transaction including sender/receiver PAN, geo-coordinates, device ID, cross-border flags

### L1 — Orchestrator & Routing

Determines whether a transaction needs full analysis or can be **short-circuited** using cached verdicts.

- **MinHash LSH**: Computes Jaccard similarity (128 permutations) against case memory. Threshold: **0.80**
- **Regulation Hash**: SHA-256 composite hash of the regulatory corpus. If unchanged since the cached verdict, short-circuit is safe
- **Decision**: `match + hash_unchanged → skip L2–L5` | `no match or stale → full pipeline`

### L2 — Transaction Monitor (6 Parallel Detectors)

Runs **C1–C6 detection categories** concurrently using `asyncio.gather`. Each detector returns `{fired, score, trigger}`. The final flag is an OR of all hard-fires; the weighted score is passed downstream.

```
┌───────────────────────────────────────────────────────────────────┐
│                    L2 TRANSACTION MONITOR                         │
│                                                                   │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │
│   │   C1   │  │   C2   │  │   C3   │  │   C4   │  │   C5   │   │
│   │Velocity│  │Sanction│  │ Graph  │  │Account │  │  FEMA  │   │
│   │Struct. │  │Watchlst│  │Network │  │  Risk  │  │  LRS   │   │
│   │ 0.27   │  │ 0.20   │  │ 0.17   │  │ 0.19   │  │ 0.07   │   │
│   └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘   │
│       │           │           │            │           │         │
│   ┌───┴───────────┴───────────┴────────────┴───────────┴────┐   │
│   │                                                          │   │
│   │   ┌────────┐                                             │   │
│   │   │   C6   │     Weighted Sum + OR-of-Hard-Fires         │   │
│   │   │  Geo   │     ──────────────────────────────▶ FLAG    │   │
│   │   │Anomaly │                                             │   │
│   │   │ 0.10   │                                             │   │
│   │   └────────┘                                             │   │
│   └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

| Category | Weight | What it detects | Key triggers |
|----------|--------|-----------------|--------------|
| **C1** Velocity & Structuring | 0.27 | Smurfing, transaction splitting, credit-line probing, high-value cash | `C1_structuring`, `C1_velocity`, `C1_high_value`, `C1_creditline` |
| **C2** Sanctions & Watchlist | 0.20 | Sanctioned entities, PEPs, fuzzy name matching (RapidFuzz) | `C2_watchlist_hit`, `C2_alias_hit` |
| **C3** Graph / Network Flow | 0.17 | Mule fan-in, sweep patterns, layering round-trips | `C3_fanin`, `C3_sweep`, `C3_roundtrip` |
| **C4** Account Risk & Dormancy | 0.19 | Dormant accounts reactivated, new account risk | `C4_dormancy`, `C4_newaccount` |
| **C5** FEMA / LRS | 0.07 | LRS ceiling breach (USD 250K), beneficiary splitting, gift ratio | `C5_lrs_ceiling`, `C5_split_beneficiary`, `C5_gift_ratio` |
| **C6** Geo-Anomaly | 0.10 | Impossible travel, FATF jurisdiction, account takeover, new device | `C6_impossible_travel`, `C6_jurisdiction`, `C6_takeover`, `C6_subtle_probe` |

### L3 — Regulation Interpreter (Legal AI)

Performs **RAG-based legal reasoning** to determine whether flagged transactions violate specific regulations.

```
┌────────────────────────────────────────────────────────────┐
│                   L3 LEGAL REASONING                       │
│                                                            │
│  Transaction ─────┐                                        │
│  + L2 Triggers    │                                        │
│                   ▼                                        │
│           ┌───────────────┐                                │
│           │ Build Search  │                                │
│           │    Query      │                                │
│           └───────┬───────┘                                │
│                   │                                        │
│         ┌─────────┴──────────┐                             │
│         ▼                    ▼                             │
│  ┌─────────────┐    ┌──────────────┐                      │
│  │ Azure AI    │    │  ChromaDB    │                      │
│  │   Search    │    │  (Nomic      │                      │
│  │ (Hybrid)    │    │  Embeddings) │                      │
│  └──────┬──────┘    └──────┬───────┘                      │
│         │                  │                               │
│         ▼                  ▼                               │
│  ┌─────────────┐    ┌──────────────┐                      │
│  │ Gemini 2.5  │    │ Gemini 2.5   │   Dual-Evaluation   │
│  │   Flash     │    │   Flash      │   (highest conf.    │
│  │ (Azure      │    │ (Nomic       │    wins)            │
│  │  chunks)    │    │  chunks)     │                      │
│  └──────┬──────┘    └──────┬───────┘                      │
│         │                  │                               │
│         └────────┬─────────┘                               │
│                  ▼                                         │
│         ┌───────────────┐                                  │
│         │  Pick Higher  │                                  │
│         │  Confidence   │                                  │
│         └───────┬───────┘                                  │
│                 │                                          │
│                 ▼                                          │
│   4 Sub-Scores + Verdict + Citation Trail                  │
└────────────────────────────────────────────────────────────┘
```

**Dual-evaluation strategy**: The LLM runs independently on Azure AI Search chunks and local ChromaDB/Nomic chunks. The verdict with the highest confidence score wins.

**4 Sub-Scores** (weighted to produce final confidence):

| Sub-Score | Weight | Description |
|-----------|--------|-------------|
| Retrieval Match | 0.30 | How well retrieved regulatory chunks match the case facts |
| Rule Applicability | 0.35 | How clearly the retrieved rules apply to this transaction |
| Evidence Sufficiency | 0.25 | Whether transaction facts support a defensible decision |
| Precedent Confidence | 0.10 | Pattern resemblance to known suspicious typologies |

**Confidence bands** determine routing:

| Band | Range | Action |
|------|-------|--------|
| Auto-file | >= 0.90 | STR auto-filed, post-filing review queued |
| File + Review | 0.60 – 0.89 | STR generated (L4), human review required |
| Human First | 0.50 – 0.59 | Held for compliance officer review |
| Priority Escalation | < 0.50 | Immediate escalation |

**LLM stack**: Gemini 2.5 Flash (primary) with Ollama Phi-4 (fallback). Embeddings via Ollama `nomic-embed-text`.

### L4 — STR Report Generator

Generates **FIU-IND goAML Transaction-Based Report (TRF)** compliant STR XML documents.

```
┌───────────────────────────────────────────────────────┐
│                  L4 REPORT GENERATOR                   │
│                                                        │
│   L3 Verdict ──┐                                       │
│   L2 Evidence ─┤                                       │
│   Transaction ─┘                                       │
│        │                                               │
│        ▼                                               │
│   ┌──────────────┐                                     │
│   │  SLM Mapping │  Phi-4-mini via Ollama              │
│   │  (Constrained│  (deterministic mock fallback)      │
│   │   JSON)      │  Enums locked to XSD values         │
│   └──────┬───────┘                                     │
│          │                                             │
│          ▼                                             │
│   ┌──────────────┐                                     │
│   │ Deterministic│  Pure assembly — no model,          │
│   │  Serializer  │  no invention                       │
│   │  (JSON→XML)  │                                     │
│   └──────┬───────┘                                     │
│          │                                             │
│          ▼                                             │
│   ┌──────────────┐  XSV: XML Schema Validation         │
│   │  Validate    │  PRV: Preliminary Rule Validation    │
│   │  (XSV + PRV) │  (MandatoryValueFatal, etc.)        │
│   └──────┬───────┘                                     │
│          │                                             │
│     ┌────┴────┐                                        │
│     │  Valid? │                                        │
│     └────┬────┘                                        │
│      Yes │    No (≤3 attempts)                         │
│          │    └──▶ Feed errors back to SLM ──▶ Retry   │
│          │                                             │
│          ▼                                             │
│   FILED: XML + PDF review copy                         │
│   or ESCALATE: → L5 with full error context            │
└───────────────────────────────────────────────────────┘
```

**Design guarantees**:
- SLM output constrained to enum lists extracted from the XSD (no invented codes)
- Deterministic serializer (no structural drift)
- XSV catches structure/type/enum errors; PRV catches mandatory/sufficiency/consistency errors
- Self-healing loop: validation errors are fed back to the SLM for targeted repair (max 3 attempts)

### L5 — Human Review Queue

Routes cases to compliance officers based on confidence band. Tracks the **7-day FIU-IND STR filing deadline** from the moment of detection.

### L6 — Audit Logger

Appends a **SHA-256 hash chain** block for every transaction processed. Each block captures the transaction ID, case ID, timestamp, and layer results. Designed for immutable Azure Blob Storage with GRS replication.

### L7 — Regulatory Watch (Cron)

Runs every **6 hours** independently of transaction processing. Scrapes regulatory sources (RBI Master Directions, FIU-IND, NPCI circulars), computes a new composite hash, and invalidates cached verdicts when regulations change — forcing full pipeline re-reasoning on subsequent transactions.

---

## Frontend (React + TypeScript)

A single-page dashboard built with **Vite + React 18 + TypeScript**.

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌──────────────────────────────────────────┐  │
│  │   CP  Compliance Pipeline   RBI · FIU-IND · FEMA · NPCI  │  │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌─────────────────────────────────────────┐  │
│  │              │  │                                         │  │
│  │   PIPELINE   │  │              MAIN AREA                  │  │
│  │   LAYERS     │  │                                         │  │
│  │              │  │  Phase: idle     → Upload CSV + Table   │  │
│  │  L0 Ingest   │  │  Phase: process → Progress bar + Spinner│ │
│  │  L1 Route    │  │  Phase: result  → ResultPanel           │  │
│  │  L2 Monitor  │  │  Phase: error   → Error display         │  │
│  │  L3 Legal    │  │                                         │  │
│  │  L4 STR Gen  │  │  ResultPanel includes:                  │  │
│  │  L5 Review   │  │  - Verdict badge + confidence band      │  │
│  │  L6 Audit    │  │  - L2 trigger checklist                 │  │
│  │  L7 RegWatch │  │  - L3 sub-scores breakdown              │  │
│  │              │  │  - Regulatory citation card              │  │
│  │  (LayerCard  │  │  - Similar cases from case memory       │  │
│  │   per layer) │  │  - STR XML viewer + PDF download link   │  │
│  │              │  │  - Audit hash + processing time          │  │
│  └──────────────┘  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Key components**:
- **UploadZone**: Drag-and-drop CSV upload with auto-publish to Azure Queue
- **TransactionTable**: Paginated (50/page), searchable by TX ID, sender, or receiver name
- **LayerCard**: Real-time status for each pipeline layer (pass/flag/skip/error)
- **ResultPanel**: Full verdict display with sub-scores, citations, XML viewer, PDF link
- **SSE streaming**: Real-time layer-by-layer progress via Server-Sent Events

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Frontend** | React 18, TypeScript, Vite 5 |
| **LLM (primary)** | Google Gemini 2.5 Flash |
| **LLM (fallback)** | Ollama — Phi-4 (reasoning), Phi-4-mini (SLM mapping) |
| **Embeddings** | Ollama — nomic-embed-text |
| **Vector DB** | ChromaDB (local persistent) |
| **Search** | Azure AI Search (hybrid keyword + vector) |
| **Queue** | Azure Queue Storage |
| **Database** | Azure Cosmos DB (case history) |
| **Blob Storage** | Azure Blob Storage (audit logs, reports) |
| **Similarity** | datasketch (MinHash LSH) |
| **Fuzzy Match** | RapidFuzz (name matching in C2) |
| **BM25** | rank-bm25 (lexical retrieval fallback) |
| **XML Validation** | lxml (XSD schema + PRV rules) |
| **PDF Generation** | ReportLab |
| **Data Processing** | pandas, openpyxl |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/transactions/stream` | Run full pipeline for one transaction (SSE stream) |
| `POST` | `/api/publish` | Publish all CSV rows to Azure Queue Storage |
| `GET` | `/api/queue/status` | Check queue depth |
| `GET` | `/api/health` | Health check (lists active layers) |
| `POST` | `/api/debug` | Echo back received payload (development) |
| `GET` | `/reports/{filename}` | Serve generated STR PDF review copies |

The main endpoint (`/api/transactions/stream`) returns **Server-Sent Events** with these message types:

```
layer_start    → { "type": "layer_start", "layer": <int> }
layer_complete → { "type": "layer_complete", "event": { LayerEvent } }
result         → { "type": "result", "result": { PipelineResult } }
error          → { "type": "error", "message": "..." }
```

---

## Project Structure

```
Compliance-pipeline/
├── api.py                          # FastAPI server — SSE streaming endpoint
├── config.py                       # Configuration (Azure creds, paths, thresholds)
├── requirements.txt                # Python dependencies
│
├── L0_event_ingestion/
│   └── event_receiver.py           # Azure Queue publish/receive/ack
│
├── L1_orchestrator/
│   ├── orchestrator.py             # Pipeline routing, L2/L3 dispatch
│   ├── minhash_lsh.py              # MinHash similarity + case memory
│   └── regulation_hash.py          # Regulation freshness check
│
├── L2_transaction_monitor/
│   ├── orchestrator.py             # Parallel C1–C6 runner + weighted scoring
│   ├── data_layer.py               # Unified data access (CSV/history/accounts)
│   ├── main.py                     # Standalone L2 entry point
│   └── detectors/
│       ├── c1_adapter.py                       # C1 interface adapter
│       ├── c1_velocity_and_structuring/        # Velocity, structuring, credit-line
│       │   ├── checks.py                       # Detection logic
│       │   ├── models.py                       # Data models
│       │   ├── thresholds.py                   # Configurable thresholds
│       │   ├── slm_reasoner.py                 # SLM-assisted reasoning
│       │   └── cosmos_client.py                # Cosmos DB integration
│       ├── c2_sanctions_and_watchlist.py        # Fuzzy name match against watchlists
│       ├── c3_graph_network_flow/              # Graph-based mule/layering detection
│       │   ├── detector.py
│       │   ├── graph_builder.py
│       │   ├── patterns.py
│       │   └── slm_classifier.py
│       ├── c4_account_risk_and_dormancy.py     # Account age + dormancy signals
│       ├── c5_fema_lrs.py                      # LRS ceiling, beneficiary split, gift ratio
│       └── c6_geo_anomaly/                     # Geo + device anomaly detection
│           ├── detector.py
│           ├── features.py
│           └── slm_classifier.py
│
├── L3_regulation_interpreter/
│   ├── hybrid_retrieval.py         # Dual retrieval (Azure AI Search + ChromaDB)
│   ├── legal_reasoning.py          # LLM-based legal analysis with sub-scores
│   ├── llm_client.py               # Gemini API + Ollama fallback client
│   ├── chroma_ingestion.py         # ChromaDB vector ingestion
│   ├── azure_ingestion.py          # Azure AI Search ingestion
│   ├── corpus_builder.py           # Regulation document chunking
│   └── regulation_corpus.json      # Local regulatory corpus
│
├── L4_report_generator/
│   ├── l4_report_generator.py      # SLM → XML → validate → PDF
│   ├── TransactionBasedReport_POC.xsd  # FIU-IND goAML schema (POC)
│   └── l3_output_mock.csv          # Test data for standalone L4 runs
│
├── chroma_db/                      # ChromaDB persistent storage
│
├── data/
│   ├── transactions.csv            # Transaction dataset
│   ├── accounts.csv                # Account profiles
│   ├── watchlist.csv               # Sanctions/PEP watchlist
│   ├── case_history.csv            # Historical case data
│   ├── ground_truth.csv            # Labelled data for evaluation
│   ├── case_memory.json            # MinHash LSH case memory
│   └── regulation_meta.json        # Regulation hash metadata
│
├── reports/                        # Generated STR PDF review copies
│
└── compliance-ui/                  # React frontend
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx                 # Main app layout + phase routing
        ├── main.tsx                # Entry point
        ├── types/pipeline.ts       # TypeScript types (Verdict, PipelineResult, etc.)
        ├── hooks/usePipeline.ts    # SSE hook for streaming pipeline events
        ├── lib/
        │   ├── api.ts              # API client (publish, queue status)
        │   └── csv.ts              # CSV parser + INR formatter
        └── components/
            ├── UploadZone.tsx      # Drag-and-drop CSV upload
            ├── TransactionTable.tsx # Paginated transaction list
            ├── LayerCard.tsx       # Per-layer status card
            └── ResultPanel.tsx     # Full verdict + evidence display
```

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the frontend)
- **Ollama** (for local LLM fallback and embeddings) — [install](https://ollama.ai)

### 1. Clone and install

```bash
git clone <repository-url>
cd Compliance-pipeline

# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd compliance-ui
npm install
cd ..
```

### 2. Pull Ollama models

```bash
ollama pull nomic-embed-text    # embeddings for L3 retrieval
ollama pull phi4:latest         # L3 legal reasoning fallback
ollama pull phi4-mini           # L4 SLM mapping
```

### 3. Environment variables

Create a `.env` file in the project root:

```bash
# Required for full Azure integration (optional for local dev)
AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>
AZURE_STORAGE_QUEUE_NAME=tx-events

# Gemini API (primary LLM for L3)
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL=gemini-2.5-flash

# Azure AI Search (optional — falls back to local ChromaDB)
SEARCH_ENDPOINT=https://<your-search>.search.windows.net
SEARCH_API_KEY=<your-search-key>

# Azure Cosmos DB (optional)
COSMOS_DB_ENDPOINT=https://<your-cosmos>.documents.azure.com:443/
COSMOS_DB_KEY=<your-cosmos-key>

# Ollama (defaults shown)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi4:latest
```

Create `compliance-ui/.env`:

```bash
VITE_API_URL=http://localhost:8000
```

### 4. Start the services

```bash
# Terminal 1: Start Ollama (if not running as a service)
ollama serve

# Terminal 2: Start the backend
uvicorn api:app --reload --port 8000

# Terminal 3: Start the frontend
cd compliance-ui
npm run dev
```

The frontend runs at `http://localhost:3000` and the API at `http://localhost:8000`.

### 5. Run the pipeline

1. Open the frontend in your browser
2. Upload a transaction CSV (must include `tx_id`, `amount_inr`, `sender_name`, `receiver_name`, etc.)
3. Select a transaction from the table
4. Click **"Run pipeline"** to process it through L0–L7
5. Watch real-time layer progress in the left sidebar
6. View the full verdict, regulatory citations, and STR PDF in the result panel

---

## Verdicts

| Verdict | Description |
|---------|-------------|
| `clean` | Transaction cleared — no suspicious indicators |
| `dismissed` | L2 flagged but L3 determined it was a false positive |
| `str_filed` | STR auto-filed with FIU-IND (confidence >= 0.70) |
| `human_review` | Held for compliance officer review (confidence 0.50–0.69) |
| `escalated` | Priority escalation — low confidence, needs immediate attention |

---

## Regulatory Framework

This pipeline is designed to comply with:

- **PMLA (Prevention of Money Laundering Act)** — STR filing obligations, KYC requirements
- **RBI Master Directions** — KYC/AML guidelines, enhanced due diligence thresholds
- **FIU-IND Directions** — Suspicious transaction reporting format (goAML TRF), 7-day filing deadline
- **FEMA (Foreign Exchange Management Act)** — LRS ceiling (USD 250,000), cross-border reporting
- **NPCI Circulars** — UPI-specific transaction monitoring rules

---

## Dataset Schema

The pipeline expects CSV files with these columns:

| Column | Type | Description |
|--------|------|-------------|
| `tx_id` | string | Unique transaction identifier |
| `timestamp` | string | ISO 8601 transaction time |
| `channel` | string | UPI, NEFT, RTGS, IMPS, or SWIFT |
| `amount_inr` | float | Transaction amount in INR |
| `sender_account_id` | string | Sender account identifier |
| `sender_name` | string | Sender name |
| `sender_bank` | string | Sender bank name |
| `sender_ifsc` | string | Sender IFSC code |
| `sender_pan` | string | Sender PAN |
| `receiver_name` | string | Receiver name |
| `receiver_account_external` | string | Receiver account identifier |
| `receiver_bank` | string | Receiver bank name |
| `receiver_pan` | string | Receiver PAN |
| `receiver_dob` | string | Receiver date of birth |
| `receiver_state` | string | Receiver state |
| `receiver_city` | string | Receiver city |
| `tx_location_state` | string | Transaction location state |
| `tx_location_city` | string | Transaction location city |
| `tx_location_country` | string | Transaction location country |
| `tx_location_lat` | string | Transaction latitude |
| `tx_location_lon` | string | Transaction longitude |
| `purpose_code` | string | Purpose of payment code |
| `device_id` | string | Device identifier |
| `is_cross_border` | string | "0" or "1" |
| `usd_equiv` | string | USD equivalent amount |
| `fx_usd_inr` | string | Exchange rate |
| `beneficiary_id` | string | Beneficiary identifier |

---

## Development

### Running L2 standalone

```bash
python -m L2_transaction_monitor.main
```

### Running L4 standalone (from mock L3 output)

```bash
python L4_report_generator/l4_report_generator.py
```

### Running L0 → L1 queue processing

```bash
# Publish transactions to queue
python L0_event_ingestion/event_receiver.py

# Process queue through L1
python L1_orchestrator/orchestrator.py
```

### Ingesting regulations into ChromaDB

```bash
python L3_regulation_interpreter/chroma_ingestion.py
```
