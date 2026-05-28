"use client";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";

const attempts = [
  { attempt: 1, before: 0.58, after: 0.71, notes: "Fixed unsupported claims" },
  { attempt: 2, before: 0.71, after: 0.89, notes: "Added citations" },
  { attempt: 3, before: 0.89, after: 0.93, notes: "Tightened reasoning" },
];

export default function RepairTimelinePage() {
  return (
    <Shell
      title="Repair Timeline Viewer"
      subtitle="Visualize repair attempts, rollbacks, and improvement deltas at a glance."
    >
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel
          title="Timeline"
          description="Chronological trace of repair attempts with score deltas."
        >
          <div className="space-y-3 text-sm text-slate-300">
            {attempts.map((item) => (
              <div
                key={item.attempt}
                className="rounded-xl border border-white/10 bg-white/5 p-3"
              >
                <div className="flex items-center justify-between">
                  <span>Attempt {item.attempt}</span>
                  <span className="text-emerald-300">
                    {item.before.toFixed(2)} -> {item.after.toFixed(2)}
                  </span>
                </div>
                <div className="text-xs text-slate-400">{item.notes}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title="Rollback Guard"
          description="Repairs that reduce quality are automatically reverted."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Rollback frequency: 0.08
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Last rollback: Attempt 4, reason=repair_degraded_score
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Saved tokens vs full retry: 412
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          title="Repair Deltas"
          description="Diff preview with affected sections highlighted."
        >
          <div className="space-y-2 text-xs text-slate-300">
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono">
              s2: replaced vague claim with cited statistic
            </div>
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono">
              s3: removed unsupported timeline reference
            </div>
          </div>
        </Panel>
        <Panel
          title="Strategies Applied"
          description="Memory-driven strategies injected into repair prompt."
        >
          <div className="space-y-2 text-xs text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              grounding -> align claims with retrieved docs
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              citation -> include span-level evidence
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              reasoning -> add causal justification
            </div>
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
