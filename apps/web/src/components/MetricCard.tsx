"use client";

export default function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="glass-panel flex flex-col gap-2">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</p>
      <p className="text-2xl font-semibold text-white">{value}</p>
      <p className="text-xs text-slate-400">{hint}</p>
    </div>
  );
}
