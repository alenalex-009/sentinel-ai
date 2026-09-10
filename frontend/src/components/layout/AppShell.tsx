import { Outlet } from 'react-router-dom'
import { GlobalNav } from './GlobalNav'
import { TopBar } from './TopBar'

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950">
      {/* Fixed 56px nav rail (GlobalNav); content column fills the rest */}
      <GlobalNav />
      <div className="flex flex-1 flex-col overflow-hidden pl-[68px]">
        <TopBar />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
