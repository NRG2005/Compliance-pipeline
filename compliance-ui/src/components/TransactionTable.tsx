import { formatINR } from "../lib/csv";
import type { Transaction } from "../types/pipeline";

interface Props {
  rows: Transaction[];
  selected: number;
  onSelect: (i: number) => void;
  totalCount?: number;
}

const CHANNEL_COLOR: Record<string, string> = {
  UPI: "var(--green-600)",
  NEFT: "var(--blue-600)",
  RTGS: "var(--amber-600)",
};

const NEON_ROW_COLORS = [
  "#00E5FF", "#FF00E5", "#00FF85", "#FFE600", "#FF8A00",
  "#6A00FF", "#FF004C", "#19FFD8", "#B4FF00", "#FF5CC8",
];

export function TransactionTable({ rows, selected, onSelect, totalCount }: Props) {
  const displayCount = totalCount ?? rows.length;

  return (
    <div style={{ border: "0.5px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
      <div
        style={{
          padding: "8px 14px",
          background: "var(--surface)",
          fontSize: 11,
          fontWeight: 500,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          borderBottom: "0.5px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>Loaded transactions</span>
        <span>Showing {rows.length} of {displayCount} row{displayCount !== 1 ? "s" : ""}</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr>
              {["tx_id", "channel", "amount", "sender", "receiver", "purpose"].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "7px 12px",
                    textAlign: "left",
                    color: "var(--text-faint)",
                    fontWeight: 500,
                    borderBottom: "0.5px solid var(--border)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((tx, i) => {
              const neon = NEON_ROW_COLORS[i % NEON_ROW_COLORS.length];
              const isSel = i === selected;
              return (
              <tr
                key={tx.tx_id}
                onClick={() => onSelect(i)}
                style={{
                  cursor: "pointer",
                  background: isSel ? `${neon}22` : "transparent",
                  borderBottom: "0.5px solid var(--border)",
                  borderLeft: `3px solid ${neon}`,
                  boxShadow: isSel ? `inset 0 0 18px ${neon}33, 0 0 10px ${neon}55` : "none",
                  transition: "background 0.15s, box-shadow 0.2s",
                }}
              >
                <td style={{ padding: "7px 12px", fontFamily: "monospace", color: neon, fontWeight: 600, textShadow: `0 0 6px ${neon}99` }}>
                  {tx.tx_id}
                </td>
                <td style={{ padding: "7px 12px" }}>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 7px",
                      borderRadius: 99,
                      fontWeight: 600,
                      color: CHANNEL_COLOR[tx.channel] ?? "var(--text-muted)",
                      background: "var(--surface)",
                      border: "0.5px solid currentColor",
                    }}
                  >
                    {tx.channel}
                  </span>
                </td>
                <td style={{ padding: "7px 12px", fontWeight: 500, color: "var(--text-primary)" }}>
                  {formatINR(tx.amount_inr)}
                </td>
                <td style={{ padding: "7px 12px", color: "var(--text-primary)" }}>{tx.sender_name}</td>
                <td style={{ padding: "7px 12px", color: "var(--text-primary)" }}>{tx.receiver_name}</td>
                <td style={{ padding: "7px 12px", fontFamily: "monospace", color: "var(--text-muted)" }}>
                  {tx.purpose_code}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
