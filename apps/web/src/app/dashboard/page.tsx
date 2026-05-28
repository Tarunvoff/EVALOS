"use client";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const timeline = [
  { t: "0h", value: 0.72 },
  { t: "2h", value: 0.76 },
  { t: "4h", value: 0.81 },
  { t: "6h", value: 0.86 },
  { t: "8h", value: 0.9 },
  { t: "10h", value: 0.92 },
];

export default function DashboardPage() {
  return (
    <Shell
      title="Reliability Dashboard"
      subtitle="Grafana-style visibility into system reliability, hallucinations, and repairs."
    >
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Panel
          title="System Reliability"
          description="Quality score over time across production runs."
        >
          <div className="h-56 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
              <AreaChart data={timeline}>
                <defs>
                  <linearGradient id="systemReliability" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2fd4b6" stopOpacity={0.7} />
                    <stop offset="100%" stopColor="#2fd4b6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis domain={[0.6, 1]} tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(10, 15, 25, 0.9)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 12,
                    color: "#e2e8f0",
                    fontSize: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#2fd4b6"
                  fill="url(#systemReliability)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel
          title="Live Trace Monitor"
          description="Streaming trace metadata from the last request."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Model: llama3:latest
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Repair attempts: 2
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Rollback: false
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Grounding score: 0.88
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel
          title="Hallucination Analytics"
          description="Trend line of hallucination rates by domain."
        />
        <Panel
          title="Repair Analytics"
          description="Convergence and efficiency across strategies."
        />
        <Panel
          title="Model Comparison"
          description="Compare reliability across local and hosted models."
        />
      </div>
    </Shell>
  );
}
