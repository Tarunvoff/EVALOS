"use client";

import { useMemo, useState } from "react";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";

type GenerationPayload = {
  text?: string;
  initial_text?: string;
  metrics?: {
    quality_after?: number;
    repair_efficiency?: number;
    grounding_score?: number;
    hallucination_rate?: number;
    citation_precision?: number;
    rollback_frequency?: number;
  };
  evaluation?: { failed?: string[] };
  rag?: {
    hallucination?: { hallucinated_spans?: string[] };
  };
};

const defaultPrompt =
  "Explain why multi-agent chains drift without grounding constraints.";

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [docs, setDocs] = useState("[]");
  const [responseText, setResponseText] = useState("");
  const [metrics, setMetrics] = useState<GenerationPayload["metrics"] | null>(null);
  const [failed, setFailed] = useState<string[]>([]);
  const [hallucinated, setHallucinated] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiBase = useMemo(
    () => process.env.NEXT_PUBLIC_EVALOS_API_BASE || "http://localhost:8000",
    []
  );

  const parsedDocs = useMemo(() => {
    try {
      const parsed = JSON.parse(docs);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [docs]);

  const handleRun = async () => {
    setLoading(true);
    setResponseText("");
    setFailed([]);
    setMetrics(null);
    setHallucinated([]);
    setError(null);
    try {
      if (isStreaming) {
        await streamGenerate();
      } else {
        const payload = await generateOnce();
        applyPayload(payload);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const generateOnce = async (): Promise<GenerationPayload> => {
    const response = await fetch(`${apiBase}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        optimize_for: ["accuracy", "grounding"],
        retrieved_documents: parsedDocs,
      }),
    });
    if (!response.ok) {
      throw new Error(`Request failed (${response.status})`);
    }
    return response.json();
  };

  const streamGenerate = async () => {
    const response = await fetch(`${apiBase}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        optimize_for: ["accuracy", "grounding"],
        retrieved_documents: parsedDocs,
        stream: true,
      }),
    });
    if (!response.ok) {
      throw new Error(`Request failed (${response.status})`);
    }
    if (!response.body) {
      throw new Error("Streaming response unavailable");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const lines = part.split("\n");
        const event = lines.find((line) => line.startsWith("event:"));
        const data = lines.find((line) => line.startsWith("data:"));
        if (!data) {
          continue;
        }
        const payload = JSON.parse(data.replace("data:", "").trim());
        if (event && event.includes("text")) {
          setResponseText((prev) => `${prev}${payload}`);
        }
        if (event && event.includes("done")) {
          applyPayload(payload);
        }
      }
    }
  };

  const applyPayload = (payload: GenerationPayload) => {
    if (payload.text) {
      setResponseText(payload.text);
    }
    if (payload.metrics) {
      setMetrics(payload.metrics);
    }
    if (payload.evaluation?.failed) {
      setFailed(payload.evaluation.failed);
    }
    if (payload.rag?.hallucination?.hallucinated_spans) {
      setHallucinated(payload.rag.hallucination.hallucinated_spans);
    }
  };

  return (
    <Shell
      title="Playground"
      subtitle="Stream a response, watch failures surface, and replay targeted repairs in real time."
    >
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel
          title="Request Inputs"
          description="Prompt, retrieval docs, and optional agent trace payload."
        >
          <div className="space-y-4">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              className="min-h-[120px] w-full rounded-xl border border-white/10 bg-black/60 p-3 text-sm text-slate-200"
            />
            <textarea
              value={docs}
              onChange={(event) => setDocs(event.target.value)}
              className="min-h-[120px] w-full rounded-xl border border-white/10 bg-black/60 p-3 font-mono text-xs text-slate-200"
            />
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={isStreaming}
                  onChange={(event) => setIsStreaming(event.target.checked)}
                />
                streaming
              </label>
            </div>
            <button
              onClick={handleRun}
              disabled={loading}
              className="w-full rounded-full bg-emerald-400 px-4 py-2 text-sm font-semibold text-black transition hover:bg-emerald-300 disabled:opacity-50"
            >
              {loading ? "Running..." : "Run EvalOS"}
            </button>
            {error ? (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">
                {error}
              </div>
            ) : null}
          </div>
        </Panel>
        <Panel
          title="Reliability Signals"
          description="Live metrics derived from the latest run."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Quality score: {metrics?.quality_after?.toFixed(2) ?? "-"}
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Grounding score: {metrics?.grounding_score?.toFixed(2) ?? "-"}
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Hallucination rate: {metrics?.hallucination_rate?.toFixed(2) ?? "-"}
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Repair efficiency: {metrics?.repair_efficiency?.toFixed(2) ?? "-"}
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Response" description="Streamed response text.">
          <div className="rounded-xl border border-white/10 bg-black/60 p-3 text-sm text-slate-200">
            {responseText || "No output yet."}
          </div>
        </Panel>
        <Panel
          title="Failed Criteria + Hallucinations"
          description="Why the response was repaired."
        >
          <div className="space-y-2 text-sm text-slate-300">
            {failed.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                No failed criteria detected.
              </div>
            ) : (
              failed.map((item) => (
                <div key={item} className="rounded-xl border border-white/10 bg-white/5 p-3">
                  {item}
                </div>
              ))
            )}
            {hallucinated.length > 0 && (
              <div className="rounded-xl border border-white/10 bg-red-500/10 p-3 text-xs text-red-200">
                Hallucinated spans: {hallucinated.join(" | ")}
              </div>
            )}
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
