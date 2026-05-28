"use client";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const comparisons = [
  { strategy: "vanilla", quality: 0.62, tokens: 620 },
  { strategy: "retry", quality: 0.71, tokens: 940 },
  { strategy: "best_of_n", quality: 0.78, tokens: 1280 },
  { strategy: "evalos", quality: 0.91, tokens: 780 },
];

const hallucination = [
  { strategy: "vanilla", rate: 0.33 },
  { strategy: "retry", rate: 0.26 },
  { strategy: "best_of_n", rate: 0.2 },
  { strategy: "evalos", rate: 0.11 },
];

export default function BenchmarksPage() {
  return (
    <Shell
      title="Benchmark Dashboard"
      subtitle="Compare vanilla, retry, best-of-N, and EvalOS runtime across multiple domains."
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Cost vs Quality"
          description="EvalOS keeps quality high without runaway token cost."
        >
          <div className="h-60 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
              <BarChart data={comparisons}>
                <XAxis dataKey="strategy" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  contentStyle={{
                    background: "rgba(10, 15, 25, 0.9)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 12,
                    color: "#e2e8f0",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="quality" fill="#2fd4b6" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel
          title="Hallucination Reduction"
          description="Hallucination rate drops sharply with EvalOS."
        >
          <div className="h-60 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
              <BarChart data={hallucination}>
                <XAxis dataKey="strategy" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  contentStyle={{
                    background: "rgba(10, 15, 25, 0.9)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 12,
                    color: "#e2e8f0",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="rate" fill="#f6c36b" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel
          title="Benchmark Outputs"
          description="JSON, CSV, and markdown summaries for each run."
        />
        <Panel
          title="Replay Support"
          description="Re-run any benchmark report for visualization."
        />
        <Panel
          title="Seeded Runs"
          description="Deterministic seeds applied across strategies."
        />
      </div>
    </Shell>
  );
}
