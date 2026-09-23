import {
  IconBulb,
  IconTodo,
  IconKey,
  IconAlert,
  IconFile,
} from "./icons";

interface ReportCardProps {
  sections: Record<string, string>;
  report: string;
}

const META = [
  { k: "结论", Icon: IconBulb, chip: "bg-brand-50 text-brand-600" },
  { k: "待办", Icon: IconTodo, chip: "bg-sky-50 text-sky-600" },
  { k: "关键", Icon: IconKey, chip: "bg-amber-50 text-amber-600" },
  { k: "风险", Icon: IconAlert, chip: "bg-red-50 text-red-600" },
];
const FALLBACK = { Icon: IconFile, chip: "bg-slate-100 text-slate-500" };

export function ReportCard({ sections, report }: ReportCardProps) {
  const entries = Object.entries(sections);
  if (
    entries.length === 0 ||
    (entries.length === 1 && entries[0][0] === "报告")
  ) {
    return (
      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-700">
        {report}
      </pre>
    );
  }

  return (
    <div className="space-y-4">
      {entries.map(([title, content]) => {
        const m = META.find((x) => title.includes(x.k)) ?? FALLBACK;
        const { Icon } = m;
        return (
          <div key={title} className="card overflow-hidden">
            <div className="flex items-center gap-2.5 border-b border-slate-100 px-5 py-3.5">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-lg ${m.chip}`}
              >
                <Icon className="h-[18px] w-[18px]" />
              </span>
              <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            </div>
            <div className="px-5 py-4">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-700">
                {content}
              </pre>
            </div>
          </div>
        );
      })}
    </div>
  );
}
