"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import MetricCard from "@/components/MetricCard";
import Panel from "@/components/Panel";

const nav = [
  { label: "Playground", href: "/playground" },
  { label: "Repair Timeline", href: "/repair-timeline" },
  { label: "Hallucinations", href: "/hallucination-inspector" },
  { label: "Grounding", href: "/grounding-viewer" },
  { label: "Agent Trace", href: "/agent-trace" },
  { label: "Benchmarks", href: "/benchmarks" },
  { label: "Dashboard", href: "/dashboard" },
];

const reliability = [
  { name: "00:00", score: 0.52 },
  { name: "00:06", score: 0.6 },
  { name: "00:12", score: 0.71 },
  { name: "00:18", score: 0.84 },
  { name: "00:24", score: 0.9 },
  { name: "00:30", score: 0.94 },
];

const scenarios = [
  "Hallucination removal",
  "Citation repair",
  "Unsupported claim detection",
  "Tool misuse correction",
  "Rollback protection",
  "Grounding-aware repair",
  "Adaptive memory improvements",
];

export default function Home() {
  return (
    <div className="min-h-screen bg-grid text-slate-100">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-black/40 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-400 via-cyan-400 to-amber-300 shadow-glow" />
            <span className="text-lg font-semibold tracking-tight">EvalOS</span>
          </Link>
          <nav className="hidden items-center gap-5 text-sm text-slate-300 lg:flex">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="transition hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-6 pb-24 pt-16">
        <section className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="flex flex-col gap-6"
          >
            <p className="text-xs uppercase tracking-[0.4em] text-emerald-300/80">
              EvalOS Reliability Runtime
            </p>
            <h1 className="text-4xl font-semibold leading-tight text-white sm:text-5xl">
              An observable AI reliability operating system for production agents.
            </h1>
            <p className="max-w-xl text-base text-slate-300 sm:text-lg">
              Selective repair, grounding verification, provenance tracking, and
              adaptive memory converge into a single runtime. Monitor failures,
              replay repairs, and ship stable outputs at scale.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                href="/playground"
                className="rounded-full bg-emerald-400 px-6 py-3 text-sm font-semibold text-black transition hover:bg-emerald-300"
              >
                Launch Playground
              </Link>
              <Link
                href="/benchmarks"
                className="rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-white transition hover:border-white/50"
              >
                Run Benchmarks
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="glass-panel flex flex-col gap-6"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Live Reliability Pulse
                </p>
                <h2 className="text-2xl font-semibold text-white">0.94</h2>
                <p className="text-sm text-slate-300">
                  grounded + repaired response quality
                </p>
              </div>
              <span className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs text-emerald-200">
                +28% lift
              </span>
            </div>
            <div className="h-40 min-w-0">
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                <AreaChart data={reliability}>
                  <defs>
                    <linearGradient id="reliability" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2fd4b6" stopOpacity={0.7} />
                      <stop offset="100%" stopColor="#2fd4b6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10 }} />
                  <YAxis hide domain={[0.4, 1]} />
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
                    dataKey="score"
                    stroke="#2fd4b6"
                    fill="url(#reliability)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs text-slate-300">
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                Rollback frequency: 0.08
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                Token efficiency: +18%
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                Hallucination rate: 0.12
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                Grounding score: 0.88
              </div>
            </div>
          </motion.div>
        </section>

        <section className="mt-16 grid gap-6 lg:grid-cols-3">
          <MetricCard
            label="Selective Repair"
            value="2.1x"
            hint="Faster convergence vs full retry"
          />
          <MetricCard
            label="Grounding Integrity"
            value="91%"
            hint="Citation + retrieval alignment"
          />
          <MetricCard
            label="Rollback Safety"
            value="8%"
            hint="Rollback frequency when repairs degrade"
          />
        </section>

        <section className="mt-16 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Panel
            title="Observable Repair Flow"
            description="See how selective repair isolates failed criteria while preserving stable sections."
          >
            <ol className="flex flex-col gap-3 text-sm text-slate-300">
              <li className="flex items-center gap-3">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                Generate baseline response + trace provenance
              </li>
              <li className="flex items-center gap-3">
                <span className="h-2 w-2 rounded-full bg-amber-300" />
                Evaluate criteria, detect unsupported claims
              </li>
              <li className="flex items-center gap-3">
                <span className="h-2 w-2 rounded-full bg-cyan-400" />
                Apply targeted repairs with rollback protection
              </li>
              <li className="flex items-center gap-3">
                <span className="h-2 w-2 rounded-full bg-emerald-200" />
                Snapshot final output + memory influence
              </li>
            </ol>
          </Panel>
          <Panel
            title="Trace Surfaces"
            description="Every repair is backed by auditable observability signals."
          >
            <div className="space-y-3 text-sm text-slate-300">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                trace.render() timeline with deltas, rollbacks, repair lineage
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                Claim-level grounding map + hallucination overlays
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                Memory influence dashboard for adaptive thresholds
              </div>
            </div>
          </Panel>
        </section>

        <section className="mt-16 grid gap-6 lg:grid-cols-2">
          <Panel
            title="Demo Scenarios"
            description="Curated demos for proof, visualization, and live story telling."
          >
            <div className="grid gap-2 text-sm text-slate-300">
              {scenarios.map((item) => (
                <div key={item} className="rounded-xl border border-white/10 px-3 py-2">
                  {item}
                </div>
              ))}
            </div>
          </Panel>
          <Panel
            title="Quickstart"
            description="Run EvalOS locally against your Ollama model."
          >
            <div className="space-y-3 text-xs text-slate-200">
              <pre className="rounded-xl border border-white/10 bg-black/60 p-3 font-mono text-[12px] text-emerald-200">
                {"export EVALOS_OLLAMA_BASE_URL=http://localhost:11434\n" +
                  "export EVALOS_OLLAMA_MODEL=llama3:latest\n" +
                  "uvicorn evalos.api.app:app --reload"}
              </pre>
              <pre className="rounded-xl border border-white/10 bg-black/60 p-3 font-mono text-[12px] text-amber-200">
                {"curl -X POST http://localhost:8000/generate \\\n+  -H 'Content-Type: application/json' \\\n+  -d '{\"prompt\":\"Explain zero trust\",\"optimize_for\":[\"accuracy\"]}'"}
              </pre>
            </div>
          </Panel>
        </section>
      </main>
    </div>
  );
}
