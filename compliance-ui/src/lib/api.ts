import type { PipelineResult, StreamMessage, Transaction } from "../types/pipeline";

// ─── Base URL ─────────────────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ─── Helper ───────────────────────────────────────────────────────────────────
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ─── Endpoints ────────────────────────────────────────────────────────────────

/**
 * POST /api/publish
 * Called once after CSV upload — publishes ALL rows to Azure Queue Storage (tx-events).
 * This is the correct L0 behaviour: all transactions enter the queue first,
 * then L1 polls and processes them one at a time.
 */
export async function publishToQueue(
  rows: Transaction[]
): Promise<{ status: string; published: number; total: number; message: string }> {
  return apiFetch("/api/publish", {
    method: "POST",
    body: JSON.stringify({ rows }),
  });
}

/**
 * GET /api/queue/status
 * Returns the current number of messages in the tx-events queue.
 * Use this to show the queue depth in the UI.
 */
export async function getQueueStatus(): Promise<{
  status: string;
  queue_length: number | null;
  queue_name: string;
}> {
  return apiFetch("/api/queue/status");
}

/**
 * POST /api/transactions/stream
 * Submit a single transaction and receive layer events via Server-Sent Events.
 * Call this after publishToQueue() — one transaction at a time.
 */
export function streamTransaction(
  tx: Transaction,
  onMessage: (msg: StreamMessage) => void,
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE}/api/transactions/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tx),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Stream failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const chunk of lines) {
          const dataLine = chunk.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const msg = JSON.parse(dataLine.slice(5).trim()) as StreamMessage;
            onMessage(msg);
          } catch {
            // skip malformed chunk
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError(err as Error);
      }
    }
  })();

  return controller;
}

/**
 * GET /api/health
 */
export async function healthCheck(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/api/health");
}