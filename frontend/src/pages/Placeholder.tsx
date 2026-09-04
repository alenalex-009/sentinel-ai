interface PlaceholderProps {
  title: string
  description: string
}

export function Placeholder({ title, description }: PlaceholderProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-600">
      <div className="text-4xl font-bold font-mono text-slate-800">SA</div>
      <h1 className="text-base font-semibold text-slate-500">{title}</h1>
      <p className="text-xs text-slate-600 max-w-xs text-center">{description}</p>
      <span className="rounded border border-slate-800 px-2 py-1 text-xs text-slate-700">Phase 2</span>
    </div>
  )
}
