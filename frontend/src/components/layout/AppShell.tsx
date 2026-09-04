import { Outlet } from 'react-router-dom'
import { GlobalNav } from './GlobalNav'
import { TopBar } from './TopBar'

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950">
      {/* 68px global navigation rail */}
      <GlobalNav />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden" style={{ marginLeft: '68px' }}>
        <TopBar />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
