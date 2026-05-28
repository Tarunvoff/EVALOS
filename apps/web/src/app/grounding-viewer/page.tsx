"use client";

import Shell from "@/components/Shell";
import Panel from "@/components/Panel";

const claims = [
  { id: "claim_1", status: "supported", doc: "doc_1" },
  { id: "claim_2", status: "partial", doc: "doc_2" },
  { id: "claim_3", status: "unsupported", doc: null },
];

export default function GroundingViewerPage() {
  return (
    <Shell
      title="RAG Grounding Viewer"
      subtitle="Track claim-level grounding, citations, and provenance across retrieved docs."
    >
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel
          title="Claim Map"
          description="Canonicalized claims aligned to supporting evidence."
        >
          <div className="space-y-2 text-sm text-slate-300">
            {claims.map((claim) => (
              <div
                key={claim.id}
                className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3"
              >
                <span>{claim.id}</span>
                <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  {claim.status}
                </span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title="Evidence Panel"
          description="Selected citation spans with context previews."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-xs">
              doc_1: "The system was launched in 1977 to study the outer Solar System."
            </div>
            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-xs">
              doc_2: "The mission continued beyond the heliopause by 2012."
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          title="Grounding Score"
          description="Weighted score with dependency penalties applied."
        >
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Grounding score: 0.88
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Citation precision: 0.81
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              Dependency penalty: 0.06
            </div>
          </div>
        </Panel>
        <Panel
          title="Provenance"
          description="Canonical claim lineage and source map."
        >
          <div className="space-y-2 text-xs text-slate-300">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              canonical_claim_1 {"<-"} claim_1 (caller)
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              canonical_claim_2 {"<-"} claim_2 (generated)
            </div>
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
