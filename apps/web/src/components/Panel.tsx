"use client";

export default function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="glass-panel flex h-full min-w-0 flex-col gap-4">
      <div>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-sm text-slate-300">{description}</p>
      </div>
      {children}
    </div>
  );
}
