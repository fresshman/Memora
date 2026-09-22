export function EmptyState({ text = "请先导入对话内容" }: { text?: string }) {
  return (
    <div className="border border-dashed border-zinc-200 rounded-lg py-16 text-center text-sm text-zinc-400">
      {text}
    </div>
  );
}
