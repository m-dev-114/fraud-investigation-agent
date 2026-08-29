import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, List, Search, Network, ScrollText, BarChart3, PlayCircle, ShieldAlert,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/transactions', label: 'Transactions', icon: List },
  { to: '/demo', label: 'Try Demo Investigation', icon: PlayCircle },
  { to: '/network', label: 'Fraud Network', icon: Network },
  { to: '/audit', label: 'Audit', icon: ScrollText },
  { to: '/model', label: 'Model', icon: BarChart3 },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="w-60 shrink-0 border-r border-border flex flex-col">
        <div className="flex items-center gap-2 px-4 h-16 border-b border-border">
          <ShieldAlert className="h-6 w-6 text-primary" />
          <div>
            <div className="font-semibold text-sm leading-tight">Fraud Analyst</div>
            <div className="text-xs text-muted-foreground leading-tight">Console</div>
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 text-xs text-muted-foreground border-t border-border">
          Synthetic data only. No real payments processed.
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
