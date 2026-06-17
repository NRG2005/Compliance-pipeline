import { useRef, useState } from "react";
import { parseTransactionCSV } from "../lib/csv";
import type { Transaction } from "../types/pipeline";

interface Props {
  onLoaded: (rows: Transaction[]) => void;
}

export function UploadZone({ onLoaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  const process = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const rows = parseTransactionCSV(e.target?.result as string);
      if (rows.length) onLoaded(rows);
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const file = e.dataTransfer.files[0];
    if (file?.name.endsWith(".csv")) process(file);
  };

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      style={{
        border: `1.5px dashed ${drag ? "var(--blue-400)" : "var(--border)"}`,
        borderRadius: 12,
        padding: "2.5rem 1.5rem",
        textAlign: "center",
        cursor: "pointer",
        background: drag ? "var(--blue-50)" : "var(--surface)",
        transition: "all 0.18s",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        style={{ display: "none" }}
        onChange={(e) => e.target.files?.[0] && process(e.target.files[0])}
      />
      <div style={{ fontSize: 28, marginBottom: 8, color: "var(--text-muted)" }}>↑</div>
      <p style={{ fontWeight: 500, fontSize: 14, color: "var(--text-primary)", marginBottom: 4 }}>
        Drop transactions.csv here
      </p>
      <p style={{ fontSize: 12, color: "var(--text-muted)" }}>or click to browse</p>
      <p style={{ fontSize: 11, color: "var(--text-faint)", marginTop: 10 }}>
        Columns: tx_id · timestamp · channel · amount_inr · sender_account_id · sender_name · receiver_name · purpose_code
      </p>
    </div>
  );
}
