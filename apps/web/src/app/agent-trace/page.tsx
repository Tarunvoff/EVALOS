"use client";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";

const plan = [
  { step: 1, tool: "search_docs", goal: "Locate relevant policy" },
  { step: 2, tool: "calc", goal: "Compute compliance score" },
  { step: 3, tool: "reasoning", goal: "Explain final decision" },
];

export default function AgentTracePage() {
  return (
    <Shell
      title="Agent Trace Viewer"
      subtitle="Inspect plan steps, tool calls, and reasoning consistency across agents."
    >
      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <Panel
          title="Plan Steps"
          description="Ordered plan with tool expectations."
        >
          <div className="space-y-2 text-sm text-slate-300">
            {plan.map((item) => (
              <div
                key={item.step}
                className="rounded-xl border border-white/10 bg-white/5 p-3"
              >
                <div className="flex items-center justify-between">
                  <span>Step {item.step}</span>
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
                    {item.tool}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{item.goal}</p>
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title="Tool Calls"
          description="Live tool execution signals and outcomes."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-xs">
              search_docs {"->"} status: success, latency: 182ms
            </div>
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-xs">
              calc {"->"} status: success, latency: 42ms
            </div>
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-xs">
              reasoning {"->"} alignment score: 0.87
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          title="Reliability Scores"
          description="Agent reliability evaluation metrics."
        >
          <div className="grid gap-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              tool_correctness_score: 0.93
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              planning_score: 0.88
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              reasoning_consistency_score: 0.79
            </div>
          </div>
        </Panel>
        <Panel
          title="Hallucinated Tools"
          description="Detect tool usage not present in allowed set."
        >
          <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-slate-300">
            None detected in this trace.
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
