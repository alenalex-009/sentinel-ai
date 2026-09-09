export function DemoModeBanner() {
  return (
    <div
      className="hidden items-center gap-2 rounded border border-amber-500/30 bg-amber-500/8 px-3 py-1.5 text-xs text-amber-300 xl:flex"
      title="Illustrative data for SIH demonstration — not live government data."
    >
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
      <span className="font-semibold tracking-wide uppercase">DEMO</span>
      <span className="hidden max-w-[260px] truncate text-amber-300/70 2xl:inline">
        Illustrative data for SIH demonstration — not live government data.
      </span>
    </div>
  )
}
