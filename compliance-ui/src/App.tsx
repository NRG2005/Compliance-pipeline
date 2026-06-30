import { useEffect, useRef, useState } from "react";
import { publishToQueue } from "./lib/api";
import { LayerCard, LAYER_META } from "./components/LayerCard";
import { ResultPanel } from "./components/ResultPanel";
import { TransactionTable } from "./components/TransactionTable";
import { UploadZone } from "./components/UploadZone";
import { usePipeline } from "./hooks/usePipeline";
import { formatINR } from "./lib/csv";
import type { Transaction } from "./types/pipeline";

const NEON_BLOB_COLORS = [
  "#22D3EE", "#7C3AED", "#3B82F6", "#8B5CF6",
  "#0EA5E9", "#4F46E5", "#60A5FA", "#6D28D9",
];

type Blob = { x: number; y: number; vx: number; vy: number; r: number; color: string | null; phase: number };

function NeonBlobBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: -9999, y: -9999 });
  const prevMouseRef = useRef({ x: -9999, y: -9999 });
  const blobsRef = useRef<Blob[]>([]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      prevMouseRef.current = { ...mouseRef.current };
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const init = () => {
      const W = canvas.offsetWidth || 900;
      const H = canvas.offsetHeight || 600;
      canvas.width = W;
      canvas.height = H;
      const neon: Blob[] = NEON_BLOB_COLORS.map((color, i) => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 1.0, vy: (Math.random() - 0.5) * 1.0,
        r: 130 + Math.random() * 220,
        color, phase: (i / NEON_BLOB_COLORS.length) * Math.PI * 2,
      }));
      const dark: Blob[] = Array.from({ length: 5 }, (_, i) => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.6, vy: (Math.random() - 0.5) * 0.6,
        r: 110 + Math.random() * 190,
        color: null, phase: i * 1.3,
      }));
      blobsRef.current = [...neon, ...dark];
    };

    init();

    let raf: number;
    let t = 0;

    const draw = () => {
      t += 0.006;
      const W = canvas.width;
      const H = canvas.height;
      const mouse = mouseRef.current;
      ctx.clearRect(0, 0, W, H);

      // Mouse velocity this frame — how fast the pointer moved
      const mvx = mouse.x - prevMouseRef.current.x;
      const mvy = mouse.y - prevMouseRef.current.y;
      const mouseSpeed = Math.hypot(mvx, mvy);

      for (const b of blobsRef.current) {
        // Repel blobs based on pointer proximity × pointer speed
        const bdx = b.x - mouse.x;
        const bdy = b.y - mouse.y;
        const bdist = Math.hypot(bdx, bdy) || 1;
        const proximity = Math.max(0, 1 - bdist / 380);
        const force = mouseSpeed * proximity * 0.45;
        b.vx += (bdx / bdist) * force;
        b.vy += (bdy / bdist) * force;

        b.x += b.vx + Math.sin(t * 0.65 + b.phase) * 0.8;
        b.y += b.vy + Math.cos(t * 0.5 + b.phase * 1.4) * 0.8;
        b.vx *= 0.952;
        b.vy *= 0.952;

        if (b.x < -b.r) b.x = W + b.r;
        if (b.x > W + b.r) b.x = -b.r;
        if (b.y < -b.r) b.y = H + b.r;
        if (b.y > H + b.r) b.y = -b.r;

        if (b.color) {
          const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
          g.addColorStop(0, b.color + "99");
          g.addColorStop(0.5, b.color + "3A");
          g.addColorStop(1, b.color + "00");
          ctx.fillStyle = g;
        } else {
          const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
          g.addColorStop(0, "rgba(2,3,9,0.88)");
          g.addColorStop(0.55, "rgba(2,3,9,0.45)");
          g.addColorStop(1, "rgba(2,3,9,0)");
          ctx.fillStyle = g;
        }

        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    };

    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    });
    ro.observe(canvas);
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        filter: "blur(58px) saturate(1.3)",
        opacity: 0.82,
        pointerEvents: "none",
        zIndex: 0,
      }}
    />
  );
}

export default function App() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  void queueStatus;
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
        <main style={{ padding: "1.75rem 2rem", overflowY: "auto", position: "relative" }}>
          {/* Neon blob background — only visible in idle phase free space */}
          {phase === "idle" && <NeonBlobBg />}

          {/* Phase: Upload */}
          {phase === "idle" && (
            <div style={{ maxWidth: 680, margin: "0 auto", position: "relative", zIndex: 1 }}>
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
                      background: "linear-gradient(90deg, #00E5FF, #6A00FF)",
                      color: "#fff",
                      border: "none",
                      borderRadius: 10,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      opacity: tx ? 1 : 0.4,
                      boxShadow: tx ? "0 0 14px rgba(0,229,255,0.6), 0 0 26px rgba(106,0,255,0.35)" : "none",
                      transition: "opacity 0.15s, box-shadow 0.2s",
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
              <div style={{ height: 4, background: "var(--border)", borderRadius: 99, overflow: "hidden", marginBottom: 16 }}>
                <div
                  style={{
                    height: "100%",
                    width: `${progress}%`,
                    background: "linear-gradient(90deg, #ff004c, #ff8a00, #ffe600, #00ff85, #00e5ff, #6a00ff, #ff00e5, #ff004c)",
                    backgroundSize: "300% 100%",
                    animation: "rainbowSlide 2s linear infinite",
                    boxShadow: "0 0 8px rgba(0,229,255,0.55), 0 0 16px rgba(255,0,229,0.4)",
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
        @keyframes rainbowSlide { to { background-position: 300% 0; } }
        @keyframes neonPulse {
          0%, 100% { box-shadow: 0 0 4px rgba(0,229,255,0.35), 0 0 12px rgba(0,229,255,0.15); }
          50%      { box-shadow: 0 0 8px rgba(0,229,255,0.55), 0 0 22px rgba(0,229,255,0.28); }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        /* ── Neon theme: deep black + cyan/electric-blue glow ───────────────── */
        :root {
          --bg: #05060A;
          --card-bg: #0B0E16;
          --surface: #11151F;
          --border: rgba(0,229,255,0.18);
          --text-primary: #E8FBFF;
          --text-muted: #7FA8B8;
          --text-faint: #4E6B78;
          --blue-50: #06222B;
          --blue-400: #22D3EE;
          --blue-600: #00E5FF;
          --green-600: #00FFA3;
          --amber-600: #FFB020;
        }
        /* Keep the same neon look regardless of OS light/dark preference */
        @media (prefers-color-scheme: light) {
          :root {
            --bg: #05060A;
            --card-bg: #0B0E16;
            --surface: #11151F;
            --border: rgba(0,229,255,0.18);
            --text-primary: #E8FBFF;
            --text-muted: #7FA8B8;
            --text-faint: #4E6B78;
            --blue-50: #06222B;
          }
        }
        body {
          background:
            radial-gradient(900px 500px at 18% -10%, rgba(0,229,255,0.10), transparent 60%),
            radial-gradient(900px 600px at 100% 0%, rgba(34,211,238,0.08), transparent 55%),
            radial-gradient(700px 500px at 50% 120%, rgba(0,229,255,0.06), transparent 60%),
            var(--bg);
          background-attachment: fixed;
          color: var(--text-primary);
        }
        /* Cyan glow on the primary-accent surfaces (uses existing #1D4ED8 brand chip too) */
        header { box-shadow: 0 1px 0 rgba(0,229,255,0.12), 0 8px 24px -18px rgba(0,229,255,0.4); }
        ::selection { background: rgba(0,229,255,0.30); color: #FFFFFF; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb {
          background: linear-gradient(180deg, #00E5FF, #22D3EE);
          border-radius: 99px;
        }
        ::-webkit-scrollbar-track { background: transparent; }
      `}</style>
    </div>
  );
}