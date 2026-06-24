import { useState } from "react";
import { publishToQueue, getQueueStatus } from "./lib/api";
import { LayerCard, LAYER_META } from "./components/LayerCard";
import { ResultPanel } from "./components/ResultPanel";
import { TransactionTable } from "./components/TransactionTable";
import { UploadZone } from "./components/UploadZone";
import { usePipeline } from "./hooks/usePipeline";
import { formatINR } from "./lib/csv";
import type { Transaction } from "./types/pipeline";

export default function App() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState(0);
  const { phase, layers, result, error, run, reset } = usePipeline();

  const filteredRows = rows.filter((r) =>
    r.tx_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    r.sender_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    r.receiver_name.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  const itemsPerPage = 50;
  const totalPages = Math.ceil(filteredRows.length / itemsPerPage);
  const displayRows = filteredRows.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
  const tx = displayRows[selectedRow] ?? displayRows[0];

  const progress = phase === "processing"
    ? (layers.filter((l) => l.status !== "idle").length / LAYER_META.length) * 100
    : phase === "result" ? 100 : 0;

  const handleReset = () => {
    reset();
    setRows([]);
    setSearchQuery("");
    setCurrentPage(1);
    setSelectedRow(0);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg)",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      {/* Topbar */}
      <header
        style={{
          borderBottom: "0.5px solid var(--border)",
          padding: "0 2rem",
          height: 52,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--card-bg)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: "#1D4ED8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>CP</span>
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
            Compliance Pipeline
          </span>
          <span
            style={{
              fontSize: 10,
              padding: "2px 7px",
              borderRadius: 99,
              background: "var(--surface)",
              color: "var(--text-muted)",
              border: "0.5px solid var(--border)",
            }}
          >
            RBI · FIU-IND · FEMA · NPCI
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#22C55E" }} />
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Azure Central India</span>
        </div>
      </header>

      {/* Main layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "340px 1fr",
          gap: 0,
          minHeight: "calc(100vh - 52px)",
        }}
      >
        {/* Left sidebar — pipeline spine */}
        <aside
          style={{
            borderRight: "0.5px solid var(--border)",
            padding: "1.5rem 1.25rem",
            background: "var(--card-bg)",
            overflowY: "auto",
          }}
        >
          <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
            Pipeline layers
          </p>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {LAYER_META.map((_, i) => (
              <LayerCard
                key={i}
                index={i}
                state={layers[i]}
                isLast={i === LAYER_META.length - 1}
              />
            ))}
          </div>
        </aside>

        {/* Right main area */}
        <main style={{ padding: "1.75rem 2rem", overflowY: "auto" }}>
          {/* Phase: Upload */}
          {phase === "idle" && (
            <div style={{ maxWidth: 680, margin: "0 auto" }}>
              <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                Submit a transaction
              </h1>
              <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 20 }}>
                Upload a CSV or select a transaction to run through the full L0–L7 compliance pipeline.
              </p>

              <UploadZone onLoaded={async (r) => {
                  setRows(r);
                  setSelectedRow(0);
                  setQueueStatus("Publishing to queue…");
                  try {
                    const res = await publishToQueue(r);
                    setQueueStatus(res.message);
                  } catch {
                    setQueueStatus("Queue publish skipped — running in-process");
                  }
                }} />

              {rows.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ marginBottom: 12 }}>
                    <input
                      type="text"
                      placeholder="Search by TX ID, sender, or receiver name..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setSelectedRow(0);
                      }}
                      style={{
                        width: "100%",
                        padding: "10px 14px",
                        fontSize: 13,
                        borderRadius: 10,
                        border: "0.5px solid var(--border)",
                        background: "var(--card-bg)",
                        color: "var(--text-primary)",
                        outline: "none",
                      }}
                    />
                  </div>
                  <TransactionTable rows={displayRows} selected={selectedRow} onSelect={setSelectedRow} totalCount={filteredRows.length} />
                  
                  {totalPages > 1 && (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12 }}>
                      <button
                        onClick={() => {
                          setCurrentPage(p => Math.max(1, p - 1));
                          setSelectedRow(0);
                        }}
                        disabled={currentPage === 1}
                        style={{
                          padding: "6px 12px",
                          fontSize: 12,
                          background: "var(--card-bg)",
                          border: "0.5px solid var(--border)",
                          borderRadius: 6,
                          color: currentPage === 1 ? "var(--text-faint)" : "var(--text-primary)",
                          cursor: currentPage === 1 ? "not-allowed" : "pointer"
                        }}
                      >
                        ← Previous
                      </button>
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        Page {currentPage} of {totalPages}
                      </span>
                      <button
                        onClick={() => {
                          setCurrentPage(p => Math.min(totalPages, p + 1));
                          setSelectedRow(0);
                        }}
                        disabled={currentPage === totalPages}
                        style={{
                          padding: "6px 12px",
                          fontSize: 12,
                          background: "var(--card-bg)",
                          border: "0.5px solid var(--border)",
                          borderRadius: 6,
                          color: currentPage === totalPages ? "var(--text-faint)" : "var(--text-primary)",
                          cursor: currentPage === totalPages ? "not-allowed" : "pointer"
                        }}
                      >
                        Next →
                      </button>
                    </div>
                  )}

                  <button
                    onClick={() => tx && run(tx)}
                    disabled={!tx}
                    style={{
                      marginTop: 14,
                      width: "100%",
                      padding: "11px",
                      background: "#1D4ED8",
                      color: "#fff",
                      border: "none",
                      borderRadius: 10,
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer",
                      opacity: tx ? 1 : 0.4,
                      transition: "opacity 0.15s",
                    }}
                  >
                    Run pipeline → {tx ? `${tx.tx_id} · ${formatINR(tx.amount_inr)}` : "select a row above"}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Phase: Processing */}
          {phase === "processing" && tx && (
            <div style={{ maxWidth: 680, margin: "0 auto" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, paddingBottom: 14, borderBottom: "0.5px solid var(--border)" }}>
                <div>
                  <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                    {formatINR(tx.amount_inr)} · {tx.channel}
                  </p>
                  <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                    {tx.sender_name} → {tx.receiver_name} · {tx.tx_id}
                  </p>
                </div>
                <div
                  style={{
                    marginLeft: "auto",
                    fontSize: 11,
                    color: "var(--text-muted)",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      display: "inline-block",
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      border: "1.5px solid #1D4ED8",
                      borderTopColor: "transparent",
                      animation: "spin 0.7s linear infinite",
                    }}
                  />
                  Processing…
                </div>
              </div>

              {/* Progress strip */}
              <div style={{ height: 2, background: "var(--border)", borderRadius: 99, overflow: "hidden", marginBottom: 16 }}>
                <div
                  style={{
                    height: "100%",
                    width: `${progress}%`,
                    background: "#1D4ED8",
                    borderRadius: 99,
                    transition: "width 0.4s ease",
                  }}
                />
              </div>

              <p style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 10 }}>
                Detailed layer activity is visible in the pipeline panel on the left.
              </p>
            </div>
          )}

          {/* Phase: Result */}
          {phase === "result" && result && (
            <div style={{ maxWidth: 680, margin: "0 auto" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div>
                  <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                    {tx ? `${formatINR(tx.amount_inr)} · ${tx.channel}` : result.tx_id}
                  </p>
                  <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                    {tx ? `${tx.sender_name} → ${tx.receiver_name} · ` : ""}{result.tx_id}
                  </p>
                </div>
                <button
                  onClick={handleReset}
                  style={{ fontSize: 12, padding: "5px 12px", border: "0.5px solid var(--border)", borderRadius: 8, background: "transparent", color: "var(--text-muted)", cursor: "pointer" }}
                >
                  ← New transaction
                </button>
              </div>
              <ResultPanel result={result} onReset={handleReset} />
            </div>
          )}

          {/* Phase: Error */}
          {phase === "error" && (
            <div style={{ maxWidth: 680, margin: "0 auto" }}>
              <div style={{ background: "#FFF1F2", border: "0.5px solid #FCA5A5", borderRadius: 12, padding: "1.25rem 1.5rem" }}>
                <p style={{ fontWeight: 500, color: "#991B1B", marginBottom: 6 }}>Pipeline error</p>
                <p style={{ fontSize: 12, color: "#B91C1C" }}>{error}</p>
                <button
                  onClick={handleReset}
                  style={{ marginTop: 12, fontSize: 12, padding: "6px 14px", border: "0.5px solid #FCA5A5", borderRadius: 8, background: "transparent", color: "#991B1B", cursor: "pointer" }}
                >
                  Try again
                </button>
              </div>
            </div>
          )}
        </main>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
          --bg: #F8F9FA;
          --card-bg: #FFFFFF;
          --surface: #F1F3F5;
          --border: rgba(0,0,0,0.1);
          --text-primary: #111827;
          --text-muted: #6B7280;
          --text-faint: #9CA3AF;
          --blue-50: #EFF6FF;
          --blue-400: #60A5FA;
          --blue-600: #2563EB;
          --green-600: #16A34A;
          --amber-600: #D97706;
        }
        @media (prefers-color-scheme: dark) {
          :root {
            --bg: #0F1117;
            --card-bg: #1A1D27;
            --surface: #252836;
            --border: rgba(255,255,255,0.08);
            --text-primary: #F1F5F9;
            --text-muted: #94A3B8;
            --text-faint: #64748B;
            --blue-50: #1E2A45;
          }
        }
        body { background: var(--bg); color: var(--text-primary); }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
      `}</style>
    </div>
  );
}