import { LAYER_META } from "./LayerCard";
import type { PipelineResult } from "../types/pipeline";

const VERDICT_CONFIG = {
  clean:        { label: "Transaction cleared",         icon: "✓", heroClass: "success" },
  str_filed:    { label: "STR auto-filed",              icon: "⚠", heroClass: "danger"  },
  human_review: { label: "Held for human review",       icon: "?", heroClass: "warning" },
  escalated:    { label: "Priority escalation",         icon: "⚠", heroClass: "danger"  },
  dismissed:    { label: "False positive — dismissed",  icon: "✓", heroClass: "success" },
};

const HERO_STYLE: Record<string, React.CSSProperties> = {
  success: { background: "#F0FDF4", border: "0.5px solid #86EFAC" },
  danger:  { background: "#FFF1F2", border: "0.5px solid #FCA5A5" },
  warning: { background: "#FEFCE8", border: "0.5px solid #FCD34D" },
};

const DOT_COLOR: Record<string, string> = {
  pass: "#22C55E",
  flag: "#EAB308",
  str:  "#EF4444",
  skip: "#D1D5DB",
  error:"#EF4444",
  idle: "#D1D5DB",
};

const BAND_LABEL: Record<string, { label: string; color: string }> = {
  auto_file:           { label: "≥ 0.90 · auto-file",       color: "#15803D" },
  file_review:         { label: "0.70–0.89 · file + review", color: "#1D4ED8" },
  human_first:         { label: "0.50–0.69 · human first",   color: "#854D0E" },
  priority_escalation: { label: "< 0.50 · priority review",  color: "#991B1B" },
  n_a:                 { label: "N/A · short-circuited",      color: "#6B7280" },
};

interface Props {
  result: PipelineResult;
  onReset: () => void;
}

export function ResultPanel({ result, onReset }: Props) {
  const cfg = VERDICT_CONFIG[result.verdict] ?? VERDICT_CONFIG.human_review;
  const band = BAND_LABEL[result.confidence_band] ?? BAND_LABEL.n_a;
  const score = result.composite_score;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Hero */}
      <div style={{ ...HERO_STYLE[cfg.heroClass], borderRadius: 12, padding: "1.25rem 1.5rem" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <span style={{ fontSize: 26, lineHeight: 1 }}>{cfg.icon}</span>
          <div>
            <p style={{ fontSize: 16, fontWeight: 500, color: "var(--text-primary)" }}>{cfg.label}</p>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>{result.verdict_detail}</p>
          </div>
          <div style={{ marginLeft: "auto", textAlign: "right", flexShrink: 0 }}>
            <p style={{ fontSize: 10, color: "var(--text-faint)" }}>Total time</p>
            <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
              {result.processing_time_ms >= 1000
                ? `${(result.processing_time_ms / 1000).toFixed(1)}s`
                : `${result.processing_time_ms}ms`}
            </p>
          </div>
        </div>
      </div>

      {/* 2-col grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {/* L3 Confidence */}
        <Card title="L3 confidence">
          {score !== null ? (
            <>
              <p style={{ fontSize: 26, fontWeight: 500, color: "var(--text-primary)", marginBottom: 4 }}>
                {score.toFixed(3)}
              </p>
              <p style={{ fontSize: 11, color: band.color, fontWeight: 500, marginBottom: 10 }}>{band.label}</p>
              {result.sub_scores.map((s) => (
                <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 110 }}>
                    {s.key} <span style={{ color: "var(--text-faint)" }}>×{s.weight}</span>
                  </span>
                  <div style={{ flex: 1, height: 4, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.round(s.value * 100)}%`,
                        background: "#B45309",
                        borderRadius: 99,
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 500, color: "var(--text-primary)", minWidth: 28, textAlign: "right" }}>
                    {s.value.toFixed(2)}
                  </span>
                </div>
              ))}
            </>
          ) : (
            <p style={{ fontSize: 12, color: "var(--text-faint)" }}>L1 short-circuit — L3 not invoked</p>
          )}
        </Card>

        {/* Audit chain */}
        <Card title="Audit chain">
          {result.layer_events.map((ev) => {
            const meta = LAYER_META[ev.layer];
            return (
              <div key={ev.layer} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <div
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    background: DOT_COLOR[ev.status] ?? "#D1D5DB",
                    flexShrink: 0,
                  }}
                />
                <span style={{ fontSize: 12, color: "var(--text-primary)", flex: 1 }}>{meta.name}</span>
                <span style={{ fontSize: 11, color: "var(--text-faint)" }}>
                  {ev.status === "skip" ? "skipped" : ev.status === "str" ? "filed" : ev.status === "flag" ? "flagged" : "passed"}
                </span>
              </div>
            );
          })}
          <p style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 8 }}>
            Block hash: <span style={{ fontFamily: "monospace" }}>{result.audit_block_hash.slice(0, 16)}…</span>
          </p>
        </Card>

        {/* L2 checks */}
        <Card title="L2 checks fired">
          {result.l2_checks_fired.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--text-faint)" }}>L2 not invoked</p>
          ) : (
            result.l2_checks_fired.map((c) => (
              <div key={c.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <span
                  style={{
                    fontSize: 11,
                    padding: "2px 7px",
                    borderRadius: 99,
                    background: c.result === "fail" ? "#FEE2E2" : "#DCFCE7",
                    color: c.result === "fail" ? "#991B1B" : "#15803D",
                    fontWeight: 500,
                  }}
                >
                  {c.label}
                </span>
              </div>
            ))
          )}
        </Card>

        {/* Regulatory basis */}
        <Card title="Regulatory basis">
          {result.regulatory_basis.map((r) => (
            <p key={r} style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
              · {r}
            </p>
          ))}
        </Card>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(result.verdict === "str_filed" || result.verdict === "escalated") && (
          <>
            <ActionButton
              primary
              label="View STR XML"
              onClick={() => window.open(`/api/results/${result.tx_id}/str`, "_blank")}
            />
            {result.str_pdf_url && (
              <ActionButton
                primary
                label="View STR PDF"
                onClick={() => window.open(`http://127.0.0.1:8000${result.str_pdf_url}`, "_blank")}
              />
            )}
          </>
        )}
        {result.verdict === "human_review" && (
          <ActionButton primary label="Open in review queue" onClick={() => window.open("/review", "_blank")} />
        )}
        <ActionButton label="Run another transaction" onClick={onReset} />
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--card-bg)",
        border: "0.5px solid var(--border)",
        borderRadius: 12,
        padding: "12px 14px",
      }}
    >
      <p
        style={{
          fontSize: 10,
          fontWeight: 600,
          color: "var(--text-faint)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: 10,
        }}
      >
        {title}
      </p>
      {children}
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  primary,
}: {
  label: string;
  onClick: () => void;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 12,
        padding: "7px 16px",
        borderRadius: 8,
        border: primary ? "none" : "0.5px solid var(--border)",
        background: primary ? "#1D4ED8" : "transparent",
        color: primary ? "#fff" : "var(--text-primary)",
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
