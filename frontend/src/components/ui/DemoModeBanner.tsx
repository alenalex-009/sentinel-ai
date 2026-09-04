export function DemoModeBanner() {
  return (
    <div className="flex items-center gap-2 rounded border border-amber-500/30 bg-amber-500/8 px-3 py-1.5 text-xs text-amber-400">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
      <span className="font-semibold">DEMO MODE</span>
      <span className="text-amber-400/60">— Illustrative data for SIH demonstration. Not live government data.</span>
    </div>
  )
}
