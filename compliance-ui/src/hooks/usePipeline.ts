import { useCallback, useRef, useState } from "react";
import { streamTransaction } from "../lib/api";
import type { LayerEvent, PipelineResult, StreamMessage, Transaction } from "../types/pipeline";

export type PipelinePhase = "idle" | "processing" | "result" | "error";

export interface LayerState {
  status: LayerEvent["status"];
  chip_label: string;
  detail: string;
  sub_checks: LayerEvent["sub_checks"];
  sub_scores: LayerEvent["sub_scores"];
  latency_ms?: number;
  str_pdf_url?: string;
}

const INITIAL_LAYERS: LayerState[] = Array.from({ length: 8 }, () => ({
  status: "idle",
  chip_label: "",
  detail: "",
  sub_checks: [],
  sub_scores: [],
}));

export function usePipeline() {
  const [phase, setPhase] = useState<PipelinePhase>("idle");
  const [layers, setLayers] = useState<LayerState[]>(INITIAL_LAYERS);
  const [activeLayer, setActiveLayer] = useState<number | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const updateLayer = useCallback((index: number, patch: Partial<LayerState>) => {
    setLayers((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], ...patch };
      return next;
    });
  }, []);

  const run = useCallback(
    (tx: Transaction) => {
      // Cancel any in-flight request
      abortRef.current?.abort();

      setPhase("processing");
      setLayers(INITIAL_LAYERS);
      setActiveLayer(null);
      setResult(null);
      setError(null);

      const handleMessage = (msg: StreamMessage) => {
        switch (msg.type) {
          case "layer_start":
            setActiveLayer(msg.layer);
            updateLayer(msg.layer, { status: "running", chip_label: "Processing…", detail: "" });
            break;

          case "layer_complete": {
            const ev = msg.event;
            setActiveLayer(null);
            updateLayer(ev.layer, {
              status: ev.status,
              chip_label: ev.chip_label,
              detail: ev.detail,
              sub_checks: ev.sub_checks ?? [],
              sub_scores: ev.sub_scores ?? [],
              latency_ms: ev.latency_ms,
            });
            break;
          }

          case "result":
            setResult(msg.result);
            setPhase("result");
            break;

          case "error":
            setError(msg.message);
            setPhase("error");
            break;
        }
      };

      const handleError = (err: Error) => {
        setError(err.message);
        setPhase("error");
      };

      abortRef.current = streamTransaction(tx, handleMessage, handleError);
    },
    [updateLayer]
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
    setLayers(INITIAL_LAYERS);
    setActiveLayer(null);
    setResult(null);
    setError(null);
  }, []);

  return { phase, layers, activeLayer, result, error, run, reset };
}
