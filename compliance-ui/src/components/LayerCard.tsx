import { useEffect, useState } from "react";
import type { LayerState } from "../hooks/usePipeline";

interface LayerMeta {
  id: string;
  name: string;
  desc: string;
  accentBg: string;
  accentText: string;
}

export const LAYER_META: LayerMeta[] = [
  { id: "L0", name: "Event ingestion",        desc: "Service Bus · message lock · DLQ",          accentBg: "#F1EFE8", accentText: "#444441" },
  { id: "L1", name: "Orchestrator",            desc: "GPT-5-mini · MinHash+LSH · case memory",    accentBg: "#EAF3DE", accentText: "#27500A" },
  { id: "L2", name: "Transaction monitor",     desc: "T1 velocity · T2 watchlist · T3 risk · T4 geo", accentBg: "#E6F1FB", accentText: "#0C447C" },
  { id: "L3", name: "Regulation interpreter",  desc: "GPT-5.1 · BM25 hybrid · 4 sub-scores",     accentBg: "#FAEEDA", accentText: "#633806" },
  { id: "L4", name: "Report generator",        desc: "Jinja2 · lxml XSD · goAML XML",            accentBg: "#EEEDFE", accentText: "#3C3489" },
  { id: "L5", name: "Human review",            desc: "Next.js dashboard · 7-day deadline",        accentBg: "#E1F5EE", accentText: "#085041" },
  { id: "L6", name: "Audit logger",            desc: "SHA-256 chain · immutable Blob · GRS",      accentBg: "#F1EFE8", accentText: "#444441" },
  { id: "L7", name: "Regulatory watch",        desc: "Cron · Phi-4-mini · RBI/FIU-IND/FEMA",     accentBg: "#FAECE7", accentText: "#712B13" },
];

const STATUS_CHIP: Record<string, { label: string; bg: string; text: string }> = {
  running: { label: "Processing…", bg: "#DBEAFE", text: "#1D4ED8" },
  pass:    { label: "Passed",      bg: "#DCFCE7", text: "#15803D" },
  flag:    { label: "Flagged",     bg: "#FEF9C3", text: "#854D0E" },
  str:     { label: "Filed STR",   bg: "#FEE2E2", text: "#991B1B" },
  skip:    { label: "Skipped",     bg: "#F3F4F6", text: "#6B7280" },
  error:   { label: "Error",       bg: "#FEE2E2", text: "#991B1B" },
  idle:    { label: "",            bg: "transparent", text: "transparent" },
};

const CARD_BG: Record<string, string> = {
  running: "#EFF6FF",
  pass:    "#F0FDF4",
  flag:    "#FEFCE8",
  str:     "#FFF1F2",
  skip:    "transparent",
  error:   "#FFF1F2",
  idle:    "transparent",
};

const LAYER_NEON: string[] = [
  "#00E5FF", "#22D3EE", "#3B82F6", "#0EA5E9",
  "#60A5FA", "#0077FF", "#1D4ED8", "#38BDF8",
];

interface Props {
  index: number;
  state: LayerState;
  isLast: boolean;
}

export function LayerCard({ index, state, isLast }: Props) {
  const meta = LAYER_META[index];
  const chip = STATUS_CHIP[state.status] ?? STATUS_CHIP.idle;
  const isOpen = state.status !== "idle";
  const [dotCount, setDotCount] = useState(1);

  useEffect(() => {
    if (state.status !== "running") return;
    const id = setInterval(() => setDotCount((n) => (n % 3) + 1), 400);
    return () => clearInterval(id);
  }, [state.status]);

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "stretch" }}>
      {/* Spine */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 40, flexShrink: 0 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 9,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            fontWeight: 600,
            background: meta.accentBg,
            color: meta.accentText,
            border: state.status === "running" ? `1.5px solid ${meta.accentText}` : "0.5px solid transparent",
            flexShrink: 0,
            transition: "all 0.3s",
            boxShadow: state.status === "running" ? `0 0 0 3px ${meta.accentBg}` : "none",
          }}
        >
          {meta.id}
        </div>
        {!isLast && (
          <div style={{ width: 1, flex: 1, minHeight: 4, background: "var(--border)", marginTop: 2 }} />
        )}
      </div>

      {/* Card */}
      <div
        style={{
          flex: 1,
          border: `1px solid ${LAYER_NEON[index] ? LAYER_NEON[index] + "88" : "var(--border)"}`,
          borderRadius: 12,
          padding: "9px 13px",
          minHeight: 48,
          background: CARD_BG[state.status] ?? "transparent",
          opacity: state.status === "skip" ? 0.45 : 1,
          boxShadow:
            state.status === "running"
              ? `0 0 12px ${LAYER_NEON[index]}CC, 0 0 28px ${LAYER_NEON[index]}66, 0 0 52px ${LAYER_NEON[index]}2A`
              : `0 0 8px ${LAYER_NEON[index]}77, 0 0 20px ${LAYER_NEON[index]}33`,
          transition: "all 0.3s",
          marginBottom: isLast ? 0 : 3,
        }}
      >
        {/* Top row */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>{meta.name}</span>
            {state.status === "idle" && (
              <span style={{ fontSize: 11, color: "var(--text-faint)", marginLeft: 8 }}>{meta.desc}</span>
            )}
          </div>
          {chip.label && (
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 99,
                fontWeight: 500,
                background: chip.bg,
                color: chip.text,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {state.status === "running"
                ? "Processing" + ".".repeat(dotCount)
                : state.chip_label || chip.label}
            </span>
          )}
        </div>

        {/* Expandable detail */}
        {isOpen && state.detail && (
          <div style={{ marginTop: 5 }}>
            <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5 }}>{state.detail}</p>
            
            {state.str_pdf_url && (
              <a 
                href={`http://127.0.0.1:8000${state.str_pdf_url}`} 
                target="_blank" 
                rel="noopener noreferrer"
                style={{
                  display: "inline-block",
                  marginTop: "8px",
                  padding: "4px 10px",
                  background: "#EEEDFE",
                  color: "#3C3489",
                  borderRadius: "6px",
                  fontSize: 11,
                  fontWeight: 600,
                  textDecoration: "none",
                  border: "1px solid #c9c5fa"
                }}
              >
                📄 View STR Report (PDF)
              </a>
            )}

            {/* Sub-checks pills */}
            {state.sub_checks && state.sub_checks.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
                {state.sub_checks.map((c) => (
                  <span
                    key={c.label}
                    style={{
                      fontSize: 10,
                      padding: "2px 7px",
                      borderRadius: 99,
                      background: c.result === "fail" ? "#FEE2E2" : "#DCFCE7",
                      color: c.result === "fail" ? "#991B1B" : "#15803D",
                      fontWeight: 500,
                    }}
                  >
                    {c.label}
                  </span>
                ))}
              </div>
            )}

            {/* Sub-scores */}
            {state.sub_scores && state.sub_scores.length > 0 && (
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                {state.sub_scores.map((s) => (
                  <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 120 }}>
                      {s.key} <span style={{ color: "var(--text-faint)" }}>×{s.weight}</span>
                    </span>
                    <div
                      style={{
                        flex: 1,
                        height: 4,
                        background: "var(--border)",
                        borderRadius: 99,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.round(s.value * 100)}%`,
                          background: "#B45309",
                          borderRadius: 99,
                          transition: "width 0.6s ease",
                        }}
                      />
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 500, color: "var(--text-primary)", minWidth: 30, textAlign: "right" }}>
                      {s.value.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Latency */}
            {state.latency_ms !== undefined && state.latency_ms > 0 && (
              <p style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 4 }}>
                Latency: {state.latency_ms >= 1000 ? `${(state.latency_ms / 1000).toFixed(1)}s` : `${state.latency_ms}ms`}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
