interface ReportCardProps {
  sections: Record<string, string>;
  report: string;
}

export function ReportCard({ sections, report }: ReportCardProps) {
  const entries = Object.entries(sections);
  if (
    entries.length === 0 ||
    (entries.length === 1 && entries[0][0] === "报告")
  ) {
    return (
      <pre className="whitespace-pre-wrap text-sm text-zinc-700 leading-relaxed font-sans">
        {report}
      </pre>
    );
  }
  return (
    <div className="space-y-4">
      {entries.map(([title, content]) => (
        <div
          key={title}
          className="border border-zinc-200 rounded-lg bg-white p-4"
        >
          <h3 className="text-sm font-semibold text-zinc-900 mb-2 pb-2 border-b border-zinc-100">
            {title}
          </h3>
          <pre className="whitespace-pre-wrap text-sm text-zinc-700 leading-relaxed font-sans">
            {content}
          </pre>
        </div>
      ))}
    </div>
  );
}
