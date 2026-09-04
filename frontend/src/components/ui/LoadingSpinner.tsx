export function LoadingSpinner({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-slate-500">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
      <span className="text-xs">{label}</span>
    </div>
  )
}
