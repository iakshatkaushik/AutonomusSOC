import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import useBreakpoint from '../hooks/useBreakpoint';

/* ── SVG Icons ── */
const OverviewIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="4" rx="1.5"/><rect x="14" y="11" width="7" height="10" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>
  </svg>
);

const AlertIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
  </svg>
);

const ShieldIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <defs>
      <linearGradient id="shield-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#6387F1" />
        <stop offset="100%" stopColor="#A78BFA" />
      </linearGradient>
    </defs>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="url(#shield-grad)" fill="none"/>
    <path d="M9 12l2 2 4-4" stroke="url(#shield-grad)" fill="none"/>
  </svg>
);

const EvalIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
  </svg>
);

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: <OverviewIcon /> },
  { to: '/alerts', label: 'Alert Queue', icon: <AlertIcon /> },
  { to: '/evaluation', label: 'Evaluation', icon: <EvalIcon /> },
];


/* ── Animated Background Particles ── */
function FloatingParticles() {
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
      {[...Array(6)].map((_, i) => (
        <motion.div
          key={i}
          style={{
            position: 'absolute',
            width: 2,
            height: 2,
            borderRadius: '50%',
            background: `rgba(99, 135, 241, ${0.08 + Math.random() * 0.12})`,
            left: `${15 + Math.random() * 70}%`,
            top: `${10 + Math.random() * 80}%`,
          }}
          animate={{
            y: [0, -30 - Math.random() * 40, 0],
            x: [0, (Math.random() - 0.5) * 20, 0],
            opacity: [0.1, 0.4, 0.1],
          }}
          transition={{
            duration: 6 + Math.random() * 6,
            repeat: Infinity,
            delay: i * 1.2,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}


/* ── Live Clock ── */
function LiveClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <span style={{
      fontSize: '0.65rem', fontWeight: 600, color: '#3A4357',
      fontVariantNumeric: 'tabular-nums', letterSpacing: '0.05em',
    }}>
      {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
    </span>
  );
}


export default function Sidebar({ mobileOpen = false, onClose = () => {} }) {
  const location = useLocation();
  const { isMobile } = useBreakpoint();

  useEffect(() => {
    if (isMobile) onClose();
  }, [location.pathname, isMobile]);

  const isVisible = !isMobile || mobileOpen;

  return (
    <>
      {isMobile && mobileOpen && <div className="sidebar-overlay" onClick={onClose} />}
      <aside
        className={`sidebar-shell ${isVisible ? 'open' : ''}`}
        style={{
          position: 'fixed', left: 0, top: 0, height: '100%', width: 260,
          display: 'flex', flexDirection: 'column',
          background: 'linear-gradient(180deg, #080C16 0%, #0A0F1A 40%, #0C1019 100%)',
          borderRight: '1px solid rgba(255,255,255,0.03)',
          zIndex: 50,
          overflow: 'hidden',
        }}
      >
        {isMobile && (
          <button
            type="button"
            className="sidebar-close-btn"
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      {/* Floating particles */}
      <FloatingParticles />

      {/* Subtle gradient accent on left edge */}
      <div style={{
        position: 'absolute', left: 0, top: '10%', bottom: '10%', width: 1,
        background: 'linear-gradient(180deg, transparent, rgba(99,135,241,0.15), rgba(167,139,250,0.1), transparent)',
        pointerEvents: 'none',
      }} />

      {/* ── Logo ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        style={{
          padding: '24px 28px',
          borderBottom: '1px solid rgba(255,255,255,0.03)',
          position: 'relative',
        }}
      >
        {/* Background glow behind logo */}
        <div style={{
          position: 'absolute', top: 10, left: 20, width: 60, height: 60,
          background: 'radial-gradient(circle, rgba(99,135,241,0.08) 0%, transparent 70%)',
          borderRadius: '50%', pointerEvents: 'none', filter: 'blur(10px)',
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, position: 'relative' }}>
          <motion.div
            whileHover={{ scale: 1.05, rotate: 3 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            style={{
              width: 38, height: 38, borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'linear-gradient(135deg, rgba(99,135,241,0.1), rgba(167,139,250,0.1))',
              border: '1px solid rgba(99,135,241,0.15)',
              boxShadow: '0 0 20px rgba(99,135,241,0.06)',
            }}
          >
            <ShieldIcon />
          </motion.div>
          <div>
            <h1 style={{
              fontSize: '1rem', fontWeight: 800, letterSpacing: '-0.02em',
              background: 'linear-gradient(135deg, #93b4fd 0%, #c4b5fd 60%, #93b4fd 100%)',
              backgroundSize: '200% 100%',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              lineHeight: 1.2,
            }}>
              CyberSOC
            </h1>
            <p style={{
              fontSize: '0.55rem', fontWeight: 700, letterSpacing: '0.22em',
              textTransform: 'uppercase', color: '#3A4357', marginTop: 2,
            }}>
              AUTONOMOUS AGENT
            </p>
          </div>
        </div>
      </motion.div>


      {/* ── Navigation ── */}
      <nav style={{ flex: 1, padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 4, position: 'relative' }}>
        <p style={{
          padding: '0 12px', marginBottom: 8,
          fontSize: '0.55rem', fontWeight: 700, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: '#2D3A52',
        }}>
          Navigation
        </p>

        {NAV_ITEMS.map(({ to, label, icon }, i) => {
          const isActive = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={{ textDecoration: 'none' }}
            >
              <motion.div
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + i * 0.08, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                whileHover={!isActive ? { x: 4, background: 'rgba(255,255,255,0.025)' } : {}}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '11px 16px', borderRadius: 12,
                  fontSize: '0.82rem', fontWeight: isActive ? 600 : 500,
                  color: isActive ? '#E2E8F0' : '#64748B',
                  position: 'relative',
                  background: isActive
                    ? 'linear-gradient(135deg, rgba(99,135,241,0.1), rgba(139,92,246,0.06))'
                    : 'transparent',
                  border: isActive
                    ? '1px solid rgba(99,135,241,0.12)'
                    : '1px solid transparent',
                  boxShadow: isActive ? '0 0 20px rgba(99,135,241,0.06)' : 'none',
                  transition: 'color 0.2s ease, border-color 0.2s ease',
                  cursor: 'pointer',
                }}
              >
                {/* Active indicator bar */}
                {isActive && (
                  <motion.div
                    layoutId="activeIndicator"
                    style={{
                      position: 'absolute', left: -16, top: '20%', bottom: '20%',
                      width: 3, borderRadius: 2,
                      background: 'linear-gradient(180deg, #6387F1, #A78BFA)',
                      boxShadow: '0 0 12px rgba(99,135,241,0.4)',
                    }}
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                <span style={{ opacity: isActive ? 1 : 0.5, transition: 'opacity 0.2s ease', color: isActive ? '#6387F1' : 'inherit' }}>
                  {icon}
                </span>
                {label}
              </motion.div>
            </NavLink>
          );
        })}

        {/* Divider */}
        <div style={{
          height: 1, margin: '16px 12px',
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)',
        }} />

        {/* AI Status Card */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          style={{
            padding: '14px 16px', borderRadius: 12,
            background: 'linear-gradient(135deg, rgba(99,135,241,0.04), rgba(167,139,250,0.03))',
            border: '1px solid rgba(99,135,241,0.06)',
            marginTop: 4,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6387F1" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 1v4m0 14v4m-9.2-5.8l2.8-2.8m12.8-4.8l2.8-2.8M1 12h4m14 0h4M4.2 4.2l2.8 2.8m9.2 9.2l2.8 2.8"/>
              </svg>
            </motion.div>
            <span style={{ fontSize: '0.62rem', fontWeight: 700, color: '#526077', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              AI Engine
            </span>
          </div>

          {/* Progress bars */}
          {[
            { label: 'Threat Detection', value: 92, color: '#6387F1' },
            { label: 'Anomaly Scan', value: 78, color: '#A78BFA' },
            { label: 'Pattern Analysis', value: 85, color: '#38BDF8' },
          ].map((item, idx) => (
            <div key={item.label} style={{ marginBottom: idx < 2 ? 10 : 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: '0.58rem', color: '#526077', fontWeight: 500 }}>{item.label}</span>
                <span style={{ fontSize: '0.58rem', color: item.color, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{item.value}%</span>
              </div>
              <div style={{
                width: '100%', height: 3, borderRadius: 4,
                background: 'rgba(255,255,255,0.03)',
                overflow: 'hidden',
              }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${item.value}%` }}
                  transition={{ delay: 0.8 + idx * 0.2, duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                  style={{
                    height: '100%', borderRadius: 4,
                    background: `linear-gradient(90deg, ${item.color}80, ${item.color})`,
                    boxShadow: `0 0 8px ${item.color}30`,
                  }}
                />
              </div>
            </div>
          ))}
        </motion.div>
      </nav>


      {/* ── System Status Footer ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7, duration: 0.5 }}
        style={{
          padding: '16px 24px',
          borderTop: '1px solid rgba(255,255,255,0.03)',
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Pulsing dot */}
            <span style={{ position: 'relative', width: 8, height: 8, display: 'inline-block' }}>
              <span style={{
                position: 'absolute', inset: 0, borderRadius: '50%',
                backgroundColor: '#4ADE80',
                animation: 'pulseGlow 2s ease-in-out infinite',
              }} />
              <span style={{
                position: 'absolute', inset: 0, borderRadius: '50%',
                backgroundColor: '#4ADE80',
              }} />
            </span>
            <div>
              <p style={{ fontSize: '0.68rem', fontWeight: 600, color: '#94A3B8', lineHeight: 1.3 }}>
                System Online
              </p>
              <p style={{ fontSize: '0.55rem', color: '#3A4357', fontWeight: 500 }}>
                All services active
              </p>
            </div>
          </div>
          <LiveClock />
        </div>
      </motion.div>
      </aside>
    </>
  );
}
