// types/pipeline.ts

export type Verdict = "clean" | "str_filed" | "human_review" | "escalated" | "dismissed";

export type ConfidenceBand =
  | "auto_file"
  | "file_review"
  | "human_first"
  | "priority_escalation"
  | "n_a";

export interface LayerEvent {
  layer: string;
  status: "pass" | "flag" | "str" | "skip" | "error" | "idle";
  /** Per-layer SHA-256 block hash (populated by L6) */
  block_hash?: string;
}

export interface SubScore {
  key: string;
  weight: number;
  value: number;
}

export interface L2Check {
  /** Matches keys in ALL_L2_CHECKS: C1_velocity, C2_watchlist … C6_geo */
  label: string;
  result: "fail" | "pass";
}

export interface RegulatoryCitation {
  /** e.g. "PMLA Rule 3(1)(b)" */
  rule: string;
  /** e.g. "Section 12 — Maintenance of Records" */
  section: string;
  /** e.g. "FIU-IND" | "RBI" | "FEMA" | "NPCI" */
  body: string;
  /** Plain-English description of why this rule applies */
  description: string;
  /** e.g. "Fallback — LLM not configured" — optional */
  applicability?: string;
}

export interface SimilarCase {
  id: string;
  account: string;
  verdict: string;
  confidence: number;
  days_ago: number;
}

export interface PipelineResult {
  tx_id: string;
  verdict: Verdict;
  verdict_detail: string;
  confidence_band: ConfidenceBand;
  composite_score: number | null;
  processing_time_ms: number;
  audit_block_hash: string;
  layer_events: LayerEvent[];
  sub_scores: SubScore[];
  l2_checks_fired: L2Check[];
  /** Legacy flat strings — used as fallback when regulatory_citation is absent */
  regulatory_basis: string[];

  // ── New fields ──────────────────────────────────────────────────────────

  /** Structured citation from L3. Supersedes regulatory_basis when present. */
  regulatory_citation?: RegulatoryCitation;

  /** GPT model used at L3, e.g. "GPT-5.1" */
  model_version?: string;

  /** Short hash of the regulation corpus version in effect, e.g. "a3f2c891" */
  regulation_hash?: string;

  /** Human-readable corpus freshness, e.g. "4h ago" */
  corpus_freshness?: string;

  /** Hours remaining before FIU-IND 7-day STR deadline. Omit for clean verdicts. */
  deadline_hours?: number;

  /** Per-layer processing time in seconds, keyed by layer name matching LayerEvent.layer */
  layer_latencies?: Record<string, number>;

  /** MinHash LSH similar cases from L1 case memory */
  similar_cases?: SimilarCase[];

  /** Raw goAML XML string from L4. Present when verdict is str_filed or escalated. */
  str_xml?: string;

  /** URL path to the generated STR PDF (served by FastAPI) */
  str_pdf_url?: string;
}