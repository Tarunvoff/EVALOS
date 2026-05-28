"use client";

import Link from "next/link";

const nav = [
  { label: "Playground", href: "/playground" },
  { label: "Repair Timeline", href: "/repair-timeline" },
  { label: "Hallucinations", href: "/hallucination-inspector" },
  { label: "Grounding", href: "/grounding-viewer" },
  { label: "Agent Trace", href: "/agent-trace" },
  { label: "Benchmarks", href: "/benchmarks" },
  { label: "Dashboard", href: "/dashboard" },
];

export default function Shell({
  children,
  title,
  subtitle,
}: {
  children: React.ReactNode;
  title: string;
  subtitle: string;
}) {
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

      <main className="mx-auto w-full max-w-6xl px-6 pb-24 pt-12">
        <div className="mb-10 flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.3em] text-emerald-300/80">
            Observable AI Reliability
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            {title}
          </h1>
          <p className="max-w-2xl text-base text-slate-300 sm:text-lg">
            {subtitle}
          </p>
        </div>
        {children}
      </main>
    </div>
  );
}
