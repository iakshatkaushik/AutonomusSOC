import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="4" rx="1.5"/><rect x="14" y="11" width="7" height="10" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>
    </svg>
  )},
  { to: '/alerts', label: 'Alert Queue', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
    </svg>
  )},
];

export default function Sidebar() {
  return (
    <aside
      className="fixed left-0 top-0 h-full w-[260px] flex flex-col border-r z-50"
      style={{
        background: 'linear-gradient(180deg, #090d17 0%, #0c1019 100%)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      {/* ── Logo ── */}
      <div className="px-7 py-6 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
            style={{
              background: 'linear-gradient(135deg, rgba(99,135,241,0.15), rgba(139,92,246,0.15))',
              border: '1px solid rgba(99,135,241,0.2)',
            }}
          >
            🛡️
          </div>
          <div>
            <h1
              className="text-[15px] font-bold tracking-tight"
              style={{
                background: 'linear-gradient(135deg, #93b4fd, #c4b5fd)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              CyberSOC
            </h1>
            <p className="text-[9px] font-semibold tracking-[0.2em] uppercase" style={{ color: 'var(--text-muted)' }}>
              AUTONOMOUS AGENT
            </p>
          </div>
        </div>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 px-4 py-5 flex flex-col gap-1.5">
        <p className="px-3 mb-2 text-[9px] font-bold tracking-[0.15em] uppercase" style={{ color: 'var(--text-muted)' }}>
          Navigation
        </p>
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 group ${
                isActive
                  ? 'text-white'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`
            }
            style={({ isActive }) =>
              isActive
                ? {
                    background: 'linear-gradient(135deg, rgba(99,135,241,0.12), rgba(139,92,246,0.08))',
                    border: '1px solid rgba(99,135,241,0.15)',
                    boxShadow: '0 0 20px rgba(99,135,241,0.06)',
                  }
                : { border: '1px solid transparent' }
            }
          >
            <span className="opacity-70 group-hover:opacity-100 transition-opacity">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── System Status ── */}
      <div className="px-6 py-5 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <div
              className="absolute inset-0 w-2 h-2 rounded-full bg-emerald-400"
              style={{ animation: 'pulseGlow 2s ease-in-out infinite' }}
            />
          </div>
          <div>
            <p className="text-[11px] font-medium" style={{ color: 'var(--text-secondary)' }}>System Online</p>
            <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>All services running</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
