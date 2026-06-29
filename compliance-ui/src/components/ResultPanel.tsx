import { useState } from "react";
import { LAYER_META } from "./LayerCard";
import type { PipelineResult } from "../types/pipeline";

// ─── Verdict config ────────────────────────────────────────────────────────
const VERDICT_CONFIG = {
  clean:        { label: "Transaction cleared",        icon: "✓", heroClass: "success" },
  str_filed:    { label: "STR auto-filed",             icon: "⚠", heroClass: "danger"  },
  human_review: { label: "Held for human review",      icon: "?", heroClass: "warning" },
  escalated:    { label: "Priority escalation",        icon: "⚠", heroClass: "danger"  },
  dismissed:    { label: "False positive — dismissed", icon: "✓", heroClass: "success" },
};

const HERO_STYLE: Record<string, React.CSSProperties> = {
  success: { background: "#F0FDF4", border: "0.5px solid #86EFAC" },
  danger:  { background: "#FFF1F2", border: "0.5px solid #FCA5A5" },
  warning: { background: "#FEFCE8", border: "0.5px solid #FCD34D" },
};

const HERO_TEXT: Record<string, string> = {
  success: "#15803D",
  danger:  "#991B1B",
  warning: "#854D0E",
};

// ─── Status dot colours ────────────────────────────────────────────────────
const DOT_COLOR: Record<string, string> = {
  pass:  "#22C55E",
  flag:  "#EAB308",
  str:   "#EF4444",
  skip:  "#D1D5DB",
  error: "#EF4444",
  idle:  "#D1D5DB",
};

const STATUS_LABEL: Record<string, string> = {
  pass:  "passed",
  flag:  "flagged",
  str:   "filed",
  skip:  "skipped",
  error: "error",
  idle:  "idle",
};

// ─── Confidence band ───────────────────────────────────────────────────────
const BAND_LABEL: Record<string, { label: string; color: string }> = {
  auto_file:           { label: "≥ 0.90 · auto-file",        color: "#15803D" },
  file_review:         { label: "0.70–0.89 · file + review", color: "#1D4ED8" },
  human_first:         { label: "0.50–0.69 · human first",   color: "#854D0E" },
  priority_escalation: { label: "< 0.50 · priority review",  color: "#991B1B" },
  n_a:                 { label: "N/A · short-circuited",      color: "#6B7280" },
};

// ─── All 6 L2 checks (always shown, fired or not) ─────────────────────────
const ALL_L2_CHECKS = ["C1_velocity", "C2_watchlist", "C3_risk", "C4_newaccount", "C5_crossborder", "C6_geo"];
const L2_LABELS: Record<string, string> = {
  C1_velocity:    "Velocity / structuring",
  C2_watchlist:   "Watchlist match",
  C3_risk:        "Risk score",
  C4_newaccount:  "New account high-value",
  C5_crossborder: "Cross-border FEMA",
  C6_geo:         "Geo anomaly",
};

// ─── Props ────────────────────────────────────────────────────────────────
interface Props {
  result: PipelineResult;
  onReset: () => void;
}

// ─── Subcomponents ────────────────────────────────────────────────────────
function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div style={{ background: "var(--card-bg)", border: "0.5px solid var(--border)", borderRadius: 12, padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>
          {title}
        </p>
        {action}
      </div>
      {children}
    </div>
  );
}

function ActionButton({ label, onClick, primary, danger}: { label: string; onClick: () => void; primary?: boolean; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 12, padding: "7px 16px", borderRadius: 8,
        border: primary || danger ? "none" : "0.5px solid var(--border)",
        background: primary ? "#2fc30a" : danger ? "#DC2626" : "transparent",
        color: primary || danger ? "#fff" : "var(--text-primary)",
        cursor: "pointer",
        fontWeight: primary ? 500 : 400,
        transition: "opacity 0.15s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
      onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
    >
      {label}
    </button>
  );
}

function DeadlineBadge({ hours }: { hours: number }) {
  const days = Math.floor(hours / 24);
  const hrs = hours % 24;
  const urgent = hours < 48;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 500,
      padding: "3px 9px", borderRadius: 99,
      background: urgent ? "#FEE2E2" : "#FEF9C3",
      color: urgent ? "#991B1B" : "#854D0E",
    }}>
      ⏱ {days}d {hrs}h to file STR with FIU-IND
    </span>
  );
}

// ─── Main component ───────────────────────────────────────────────────────
export function ResultPanel({ result, onReset }: Props) {
  const [hashVisible, setHashVisible] = useState(false);
  const [xmlOpen, setXmlOpen] = useState(false);

  const cfg  = VERDICT_CONFIG[result.verdict] ?? VERDICT_CONFIG.human_review;
  const band = BAND_LABEL[result.confidence_band] ?? BAND_LABEL.n_a;
  const score = result.composite_score;
  const heroTextColor = HERO_TEXT[cfg.heroClass];

  // Build a set of fired check codes for quick lookup
  const firedSet = new Set(result.l2_checks_fired.map((c) => c.label));

  // Latency timeline
  const latencies = result.layer_latencies ?? {};
  const totalLatency = Object.values(latencies).reduce((a, b) => a + b, 0);
  const latencyLayers = result.layer_events.filter((ev) => (latencies[ev.layer] ?? 0) > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <div style={{ ...HERO_STYLE[cfg.heroClass], borderRadius: 12, padding: "1.25rem 1.5rem" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <span style={{ fontSize: 26, lineHeight: 1, color: heroTextColor }}>{cfg.icon}</span>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 16, fontWeight: 500, color: heroTextColor, margin: 0 }}>{cfg.label}</p>
            <p style={{ fontSize: 12, color: heroTextColor, opacity: 0.75, marginTop: 3 }}>{result.verdict_detail}</p>
            {/* Deadline badge — only shown when STR filing is required */}
            {result.deadline_hours != null && (result.verdict === "str_filed" || result.verdict === "escalated" || result.verdict === "human_review") && (
              <div style={{ marginTop: 8 }}>
                <DeadlineBadge hours={result.deadline_hours} />
              </div>
            )}
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <p style={{ fontSize: 10, color: heroTextColor, opacity: 0.6, margin: 0 }}>Total time</p>
            <p style={{ fontSize: 13, fontWeight: 500, color: heroTextColor, margin: 0 }}>
              {result.processing_time_ms >= 1000
                ? `${(result.processing_time_ms / 1000).toFixed(1)}s`
                : `${result.processing_time_ms}ms`}
            </p>
          </div>
        </div>
      </div>

      {/* ── 2-col grid ───────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>

        {/* L3 Confidence breakdown */}
        <Card title="L3 confidence">
          {score !== null ? (
            <>
              <p style={{ fontSize: 26, fontWeight: 500, color: "var(--text-primary)", marginBottom: 4 }}>
                {score.toFixed(3)}
              </p>
              <p style={{ fontSize: 11, color: band.color, fontWeight: 500, marginBottom: 12 }}>{band.label}</p>

              {/* Sub-score bars */}
              {result.sub_scores.map((s) => (
                <div key={s.key} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {s.key} <span style={{ color: "var(--text-faint)" }}>×{s.weight}</span>
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 500, color: "var(--text-primary)" }}>
                      {s.value.toFixed(2)}
                    </span>
                  </div>
                  <div style={{ height: 5, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${Math.round(s.value * 100)}%`, background: "#B45309", borderRadius: 99 }} />
                  </div>
                </div>
              ))}

              {/* Routing threshold explainer */}
              <div style={{ marginTop: 12, padding: "8px 10px", background: "var(--border)", borderRadius: 8, fontSize: 11, color: "var(--text-faint)", lineHeight: 1.6 }}>
                ≥ 0.90 auto-file · 0.70–0.89 file + review · 0.50–0.69 hold · &lt; 0.50 priority escalation
              </div>
            </>
          ) : (
            <p style={{ fontSize: 12, color: "var(--text-faint)" }}>L1 short-circuit — L3 not invoked</p>
          )}
        </Card>

        {/* Audit chain */}
        <Card
          title="Audit chain"
          action={
            <button
              onClick={() => setHashVisible((v) => !v)}
              style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, border: "0.5px solid var(--border)", background: "transparent", color: "var(--text-faint)", cursor: "pointer" }}
            >
              {hashVisible ? "Hide hashes" : "Show hashes"}
            </button>
          }
        >
          {/* Latency timeline bar */}
          {totalLatency > 0 && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ fontSize: 10, color: "var(--text-faint)", marginBottom: 4 }}>
                Per-layer latency · total {totalLatency.toFixed(1)}s
              </p>
              <div style={{ display: "flex", height: 5, borderRadius: 3, overflow: "hidden", gap: 1 }}>
                {latencyLayers.map((ev) => (
                  <div
                    key={ev.layer}
                    title={`${LAYER_META[ev.layer]?.name ?? ev.layer}: ${latencies[ev.layer]}s`}
                    style={{
                      flex: latencies[ev.layer],
                      background: ev.status === "pass" ? "#22C55E" : ev.status === "flag" ? "#EAB308" : "#D1D5DB",
                      minWidth: 3,
                    }}
                  />
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--text-faint)", marginTop: 3 }}>
                {latencyLayers.map((ev) => (
                  <span key={ev.layer}>{latencies[ev.layer]}s</span>
                ))}
              </div>
            </div>
          )}

          {/* Layer rows */}
          {result.layer_events.map((ev) => {
            const meta = LAYER_META[ev.layer];
            return (
              <div key={ev.layer} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: DOT_COLOR[ev.status] ?? "#D1D5DB", flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: "var(--text-primary)", flex: 1 }}>{meta?.name ?? ev.layer}</span>
                {hashVisible && ev.block_hash && (
                  <span style={{ fontFamily: "monospace", fontSize: 10, color: "var(--text-faint)", background: "var(--border)", padding: "1px 5px", borderRadius: 4 }}>
                    {ev.block_hash.slice(0, 8)}…
                  </span>
                )}
                <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{STATUS_LABEL[ev.status] ?? ev.status}</span>
              </div>
            );
          })}

          <p style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 8, fontFamily: "monospace" }}>
            Block hash: {result.audit_block_hash.slice(0, 16)}… · SHA-256
          </p>
        </Card>

        {/* L2 checks — all 6, fired or not */}
        <Card title="L2 checks">
          {result.l2_checks_fired.length === 0 && !result.layer_events.some((e) => e.layer === "l2") ? (
            <p style={{ fontSize: 12, color: "var(--text-faint)" }}>L2 not invoked</p>
          ) : (
            ALL_L2_CHECKS.map((code) => {
              const fired = firedSet.has(code);
              return (
                <div key={code} style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5, fontSize: 12 }}>
                  <span style={{ fontSize: 14, color: fired ? "#EF4444" : "#D1D5DB", lineHeight: 1 }}>
                    {fired ? "●" : "○"}
                  </span>
                  <span style={{ color: fired ? "var(--text-primary)" : "var(--text-faint)" }}>
                    {L2_LABELS[code] ?? code}
                  </span>
                  {fired && (
                    <span style={{ marginLeft: "auto", fontSize: 10, padding: "2px 7px", borderRadius: 99, background: "#FEE2E2", color: "#991B1B", fontWeight: 500 }}>
                      fired
                    </span>
                  )}
                </div>
              );
            })
          )}
        </Card>

        {/* Regulatory basis + model snapshot */}
        <Card title="Regulatory basis">
          {result.regulatory_citation ? (
            <>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10 }}>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", margin: 0 }}>
                    {result.regulatory_citation.rule}
                  </p>
                  <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "2px 0 0" }}>
                    {result.regulatory_citation.section}
                  </p>
                </div>
                <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 99, background: "#DBEAFE", color: "#1D4ED8", fontWeight: 500, whiteSpace: "nowrap" }}>
                  {result.regulatory_citation.body}
                </span>
              </div>
              <p style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6, margin: "0 0 10px" }}>
                {result.regulatory_citation.description}
              </p>
              {result.regulatory_citation.applicability && (
                <p style={{ fontSize: 11, color: "var(--text-faint)", borderTop: "0.5px solid var(--border)", paddingTop: 8, margin: 0 }}>
                  {result.regulatory_citation.applicability}
                </p>
              )}
            </>
          ) : (
            result.regulatory_basis.map((r) => (
              <p key={r} style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>· {r}</p>
            ))
          )}

          {/* Model & rule snapshot */}
          <div style={{ marginTop: 12, borderTop: "0.5px solid var(--border)", paddingTop: 10 }}>
            <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              Model &amp; rule snapshot
            </p>
            {[
              ["Model",              result.model_version ?? "—"],
              ["Regulation version", result.regulation_hash ?? "—"],
              ["Corpus updated",     result.corpus_freshness ?? "—"],
            ].map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 11 }}>
                <span style={{ color: "var(--text-faint)" }}>{k}</span>
                <span style={{ color: "var(--text-muted)", fontFamily: k === "Regulation version" ? "monospace" : undefined, fontWeight: 500 }}>{v}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ── Similar cases from case memory ───────────────────────────── */}
      {result.similar_cases && result.similar_cases.length > 0 && (
        <div style={{ background: "var(--card-bg)", border: "0.5px solid var(--border)", borderRadius: 12, padding: "12px 14px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            Similar cases from case memory
          </p>
          <p style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 10 }}>
            L1 MinHash LSH matched {result.similar_cases.length} past transaction{result.similar_cases.length !== 1 ? "s" : ""}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {result.similar_cases.map((c) => (
              <div
                key={c.id}
                style={{ padding: "8px 10px", background: "var(--border)", borderRadius: 8, fontSize: 11 }}
              >
                <p style={{ fontFamily: "monospace", color: "var(--text-muted)", margin: 0 }}>{c.id}</p>
                <p style={{ color: "var(--text-faint)", margin: "2px 0 6px" }}>{c.account} · {c.days_ago}d ago</p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{
                    fontSize: 10, padding: "2px 6px", borderRadius: 99, fontWeight: 500,
                    background: c.verdict === "clean" ? "#DCFCE7" : "#FEF9C3",
                    color:      c.verdict === "clean" ? "#15803D"  : "#854D0E",
                  }}>
                    {c.verdict}
                  </span>
                  <span style={{ color: "var(--text-faint)" }}>conf {c.confidence.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── STR XML inline preview ────────────────────────────────────── */}
      {result.str_xml && (
        <div style={{ background: "var(--card-bg)", border: "0.5px solid var(--border)", borderRadius: 12, padding: "12px 14px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>
              STR XML (goAML)
            </p>
            <button
              onClick={() => setXmlOpen((v) => !v)}
              style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, border: "0.5px solid var(--border)", background: "transparent", color: "var(--text-faint)", cursor: "pointer" }}
            >
              {xmlOpen ? "Collapse" : "Preview XML"}
            </button>
          </div>
          {xmlOpen && (
            <pre style={{
              marginTop: 10, padding: 10, background: "var(--border)", borderRadius: 8,
              fontSize: 11, fontFamily: "monospace", color: "var(--text-muted)",
              overflowX: "auto", lineHeight: 1.6, whiteSpace: "pre",
            }}>
              {result.str_xml}
            </pre>
          )}
        </div>
      )}

      {/* ── Actions ───────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(result.verdict === "str_filed" || result.verdict === "escalated") && (
          <>
            <ActionButton
              primary
              label="Approve for filing"
              onClick={() => window.open(`/api/results/${result.tx_id}/approve`, "_blank")}
            />
            <ActionButton
              danger
              label="Reject"
              onClick={() => window.open(`/api/results/${result.tx_id}/reject`, "_blank")}
            />
            <ActionButton
              label="Escalate"
              onClick={() => window.open(`/api/results/${result.tx_id}/escalate`, "_blank")}
            />
            {result.str_xml && (
              <ActionButton
                label="Download STR XML"
                onClick={() => {
                  const blob = new Blob([result.str_xml!], { type: "application/xml" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `STR_${result.tx_id}.xml`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              />
            )}
            {result.str_pdf_url && (
              <ActionButton
                label="View STR PDF"
                onClick={() => window.open(`http://127.0.0.1:8000${result.str_pdf_url}`, "_blank")}
              />
            )}
          </>
        )}
        {result.verdict === "human_review" && (
          <>
            <ActionButton primary label="Approve for filing" onClick={() => window.open("/review", "_blank")} />
            <ActionButton label="Reject" onClick={() => {}} />
            <ActionButton label="Escalate" onClick={() => {}} />
          </>
        )}
        <ActionButton label="Run another transaction" onClick={onReset} />
      </div>
    </div>
  );
}