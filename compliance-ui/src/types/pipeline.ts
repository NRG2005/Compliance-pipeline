// ── Transaction ──────────────────────────────────────────────────────────────
export interface Transaction {
  tx_id: string;
  timestamp: string;
  channel: "UPI" | "NEFT" | "RTGS";
  amount_inr: number;
  sender_account_id: string;
  sender_name: string;
  sender_bank: string;
  sender_ifsc: string;
  sender_vpa?: string;
  sender_pan?: string;
  sender_dob?: string;
  receiver_name: string;
  receiver_account_external: string;
  receiver_bank: string;
  receiver_pan?: string;
  receiver_dob?: string;
  receiver_vpa?: string;
  receiver_state: string;
  receiver_city: string;
  tx_location_state: string;
  tx_location_city: string;
  tx_location_country?: string;
  tx_location_lat?: string;
  tx_location_lon?: string;
  purpose_code: string;
  device_id: string;
  is_cross_border?: string;
  usd_equiv?: string;
  fx_usd_inr?: string;
  beneficiary_id?: string;
  tx_status: string;
}

// ── Layer event (streamed from backend) ──────────────────────────────────────
export type LayerStatus = "idle" | "running" | "pass" | "flag" | "str" | "skip" | "error";

export interface SubCheck {
  label: string;
  result: "pass" | "fail";
  score?: number;
}

export interface SubScore {
  key: string;
  value: number;
  weight: number;
}

export interface LayerEvent {
  layer: 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
  status: LayerStatus;
  chip_label: string;
  detail: string;
  sub_checks?: SubCheck[];
  sub_scores?: SubScore[];
  latency_ms?: number;
  str_pdf_url?: string;
}

// ── Final result ─────────────────────────────────────────────────────────────
export type Verdict = "clean" | "str_filed" | "human_review" | "escalated" | "dismissed";
export type ConfidenceBand = "auto_file" | "file_review" | "human_first" | "priority_escalation" | "n_a";

export interface PipelineResult {
  tx_id: string;
  verdict: Verdict;
  verdict_label: string;
  verdict_detail: string;
  confidence_band: ConfidenceBand;
  composite_score: number | null;
  sub_scores: SubScore[];
  l2_checks_fired: SubCheck[];
  regulatory_basis: string[];
  str_xml_path?: string;
  audit_block_hash: string;
  processing_time_ms: number;
  layer_events: LayerEvent[];
}

// ── SSE stream message ────────────────────────────────────────────────────────
export type StreamMessage =
  | { type: "layer_start"; layer: number }
  | { type: "layer_complete"; event: LayerEvent }
  | { type: "result"; result: PipelineResult }
  | { type: "error"; message: string };
