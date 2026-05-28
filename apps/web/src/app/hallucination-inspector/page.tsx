"use client";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";

const spans = [
  "Fictional treaty signed in 2032",
  "Claimed clinical trial success for Zorvexil",
  "Unsupported market share statistic",
];

export default function HallucinationInspectorPage() {
  return (
    <Shell
      title="Hallucination Inspector"
      subtitle="Surface unsupported claims and quantify hallucination risk per response."
    >
      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <Panel
          title="Detected Spans"
          description="Claims flagged as unsupported by grounding analysis."
        >
          <div className="space-y-2 text-sm text-slate-300">
            {spans.map((span) => (
              <div key={span} className="rounded-xl border border-white/10 bg-white/5 p-3">
                {span}
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title="Risk Summary"
          description="Aggregate hallucination metrics for the response."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Hallucination rate: 0.31 (high)
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Unsupported claims: 3 / 9
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Repair applied: yes (RAG repair engine)
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          title="Overlay Preview"
          description="Visual highlight of hallucinated spans inside the response."
        >
          <div className="rounded-xl border border-white/10 bg-black/60 p-4 text-sm text-slate-200">
            The treaty was signed in <span className="bg-red-500/30 px-1">2032</span>
            , enabling a new Mars colony framework.
          </div>
        </Panel>
        <Panel
          title="Repair Suggestions"
          description="Targeted fixes recommended by EvalOS."
        >
          <div className="space-y-2 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Remove unsupported timeline claims unless provided in documents.
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Add citations for any factual statements.
            </div>
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
