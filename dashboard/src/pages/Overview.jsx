import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { fetchOverview } from '../api';
import useBreakpoint from '../hooks/useBreakpoint';

/* ═══════════════════════════════════════════════════════════════════════
   DESIGN SYSTEM — Colors & Constants
   ═══════════════════════════════════════════════════════════════════════ */

const SEV = {
  CRITICAL: { color: '#F87171', glow: 'rgba(248,113,113,0.25)', bg: 'rgba(248,113,113,0.06)', border: 'rgba(248,113,113,0.15)' },
  HIGH:     { color: '#FB923C', glow: 'rgba(251,146,60,0.25)',  bg: 'rgba(251,146,60,0.06)',  border: 'rgba(251,146,60,0.15)' },
  MEDIUM:   { color: '#FACC15', glow: 'rgba(250,204,21,0.25)',  bg: 'rgba(250,204,21,0.06)',  border: 'rgba(250,204,21,0.15)' },
  LOW:      { color: '#4ADE80', glow: 'rgba(74,222,128,0.25)',  bg: 'rgba(74,222,128,0.06)',  border: 'rgba(74,222,128,0.15)' },
};

const STAT_ICONS = {
  'Total Alerts': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
  ),
  'Open Alerts': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
  ),
  'Investigated': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M21 12a9 9 0 1 1-6.22-8.56"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
  ),
  'Total Users': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
  ),
};

const SEV_ICONS = {
  CRITICAL: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
  ),
  HIGH: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
  ),
  MEDIUM: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
  ),
  LOW: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
  ),
};


/* ═══════════════════════════════════════════════════════════════════════
   ANIMATED COMPONENTS
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Animated Number Counter ── */
function AnimatedNumber({ value, duration = 1.2 }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    let start = 0;
    const end = typeof value === 'number' ? value : parseInt(value) || 0;
    const startTime = performance.now();
    const dur = duration * 1000;

    function step(now) {
      const progress = Math.min((now - startTime) / dur, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(start + (end - start) * eased));
      if (progress < 1) ref.current = requestAnimationFrame(step);
    }
    ref.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(ref.current);
  }, [value, duration]);

  return <>{display.toLocaleString()}</>;
}


/* ── Radial Severity Ring ── */
function SeverityRing({ data }) {
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{ position: 'relative', width: 220, height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={72}
            outerRadius={96}
            paddingAngle={3}
            dataKey="value"
            strokeWidth={0}
            animationBegin={300}
            animationDuration={1200}
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={SEV[entry.name]?.color || '#526077'} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: '#141C2E',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 12,
              fontSize: 12,
              boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
              padding: '8px 14px',
            }}
            itemStyle={{ color: '#E2E8F0' }}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Center label */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)', textAlign: 'center',
      }}>
        <div style={{ fontSize: '2rem', fontWeight: 800, color: '#E2E8F0', lineHeight: 1, letterSpacing: '-0.03em' }}>
          <AnimatedNumber value={total} />
        </div>
        <div style={{ fontSize: '0.6rem', fontWeight: 600, color: '#526077', textTransform: 'uppercase', letterSpacing: '0.15em', marginTop: 4 }}>
          Alerts
        </div>
      </div>
    </div>
  );
}


/* ── Pulsing Dot ── */
function PulsingDot({ color, size = 8 }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block', width: size, height: size }}>
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%', backgroundColor: color,
        animation: 'pulseGlow 2s ease-in-out infinite',
      }} />
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%', backgroundColor: color,
      }} />
    </span>
  );
}


/* ── Mini Sparkline (SVG) ── */
function MiniSparkline({ value, max = 100, color }) {
  const pts = Array.from({ length: 12 }, (_, i) => {
    const v = Math.max(0, value + (Math.sin(i * 0.8) * value * 0.15) + (Math.random() - 0.5) * value * 0.1);
    return v;
  });
  const svgW = 80, svgH = 24;
  const maxVal = Math.max(...pts, 1);
  const points = pts.map((v, i) => `${(i / (pts.length - 1)) * svgW},${svgH - (v / maxVal) * svgH}`).join(' ');

  return (
    <svg width={svgW} height={svgH} style={{ opacity: 0.7 }}>
      <defs>
        <linearGradient id={`spark-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${svgH} ${points} ${svgW},${svgH}`}
        fill={`url(#spark-${color.replace('#','')})`}
      />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}


/* ── Scanning Line Animation ── */
function ScanLine() {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
      overflow: 'hidden', borderRadius: 'inherit', pointerEvents: 'none',
    }}>
      <motion.div
        style={{
          position: 'absolute', left: 0, right: 0, height: 1,
          background: 'linear-gradient(90deg, transparent, rgba(99,135,241,0.3), transparent)',
        }}
        animate={{ top: ['-2%', '102%'] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
      />
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════════════════
   MOTION VARIANTS
   ═══════════════════════════════════════════════════════════════════════ */

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

const glowHover = {
  rest: { boxShadow: '0 0 0px rgba(99,135,241,0)' },
  hover: { boxShadow: '0 0 30px rgba(99,135,241,0.12)', borderColor: 'rgba(255,255,255,0.1)' },
};


/* ═══════════════════════════════════════════════════════════════════════
   MAIN OVERVIEW COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

export default function Overview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { isMobile, isTablet } = useBreakpoint();

  useEffect(() => {
    fetchOverview().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <div className="spinner" />
      </div>
    );
  }
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>Failed to load data.</p>;

  const sevData = Object.entries(data.severity_counts).map(([name, value]) => ({ name, value }));
  const totalAlerts = data.total_alerts;

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      style={{ maxWidth: 1360, margin: '0 auto' }}
    >
      {/* ═══════════════════════════════════════════════════════════════
          HEADER
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div variants={itemVariants} style={{ marginBottom: 36 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <h1 style={{
            fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.03em',
            background: 'linear-gradient(135deg, #E2E8F0 30%, #94A3B8)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            Threat Overview
          </h1>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 12px', borderRadius: 20,
            background: 'rgba(74,222,128,0.06)',
            border: '1px solid rgba(74,222,128,0.15)',
          }}>
            <PulsingDot color="#4ADE80" />
            <span style={{ fontSize: '0.65rem', fontWeight: 600, color: '#4ADE80', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Live
            </span>
          </div>
        </div>
        <p style={{ fontSize: '0.8rem', color: '#526077', fontWeight: 500 }}>
          Real-time insider threat monitoring — {data.total_users.toLocaleString()} users tracked
        </p>
      </motion.div>

      {/* ═══════════════════════════════════════════════════════════════
          HERO ROW — Radial + Severity Cards
          ═══════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: isTablet ? '1fr' : '280px 1fr', gap: 20, marginBottom: 24 }}>

        {/* ── Radial Donut ── */}
        <motion.div
          variants={itemVariants}
          initial="rest" whileHover="hover" animate="rest"
          style={{
            background: 'linear-gradient(145deg, #111827 0%, #0F1420 100%)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 20,
            padding: '24px 20px',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            position: 'relative', overflow: 'hidden',
          }}
        >
          <ScanLine />
          <SeverityRing data={sevData} />
          <div style={{
            display: 'flex', gap: 14, marginTop: 16,
          }}>
            {sevData.map(d => (
              <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: SEV[d.name]?.color }} />
                <span style={{ fontSize: '0.6rem', color: '#526077', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {d.name}
                </span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* ── Severity Cards Grid ── */}
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)', gridTemplateRows: isMobile ? 'auto' : 'repeat(2, 1fr)', gap: 14 }}>
          {Object.entries(data.severity_counts).map(([sev, count]) => {
            const s = SEV[sev];
            return (
              <motion.div
                key={sev}
                variants={itemVariants}
                whileHover={{
                  scale: 1.015,
                  boxShadow: `0 0 35px ${s.glow}`,
                  borderColor: `${s.color}30`,
                }}
                style={{
                  background: `linear-gradient(145deg, ${s.bg}, transparent)`,
                  border: `1px solid ${s.border}`,
                  borderRadius: 16,
                  padding: '20px 22px',
                  cursor: 'pointer',
                  position: 'relative',
                  overflow: 'hidden',
                  display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                }}
                transition={{ type: 'spring', stiffness: 400, damping: 25 }}
              >
                {/* Top row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#526077' }}>
                    {sev}
                  </span>
                  <div style={{ color: s.color, opacity: 0.7 }}>
                    {SEV_ICONS[sev]}
                  </div>
                </div>

                {/* Number + sparkline */}
                <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 8 }}>
                  <span style={{ fontSize: '2rem', fontWeight: 800, color: s.color, lineHeight: 1, letterSpacing: '-0.02em' }}>
                    <AnimatedNumber value={count} />
                  </span>
                  <MiniSparkline value={count} color={s.color} />
                </div>

                {/* Subtle gradient accent line at bottom */}
                <div style={{
                  position: 'absolute', bottom: 0, left: '10%', right: '10%', height: 2,
                  background: `linear-gradient(90deg, transparent, ${s.color}40, transparent)`,
                  borderRadius: 1,
                }} />
              </motion.div>
            );
          })}
        </div>
      </div>


      {/* ═══════════════════════════════════════════════════════════════
          STAT STRIP — 4 metrics with icons
          ═══════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : (isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)'), gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Total Alerts', value: data.total_alerts, color: '#6387F1', gradient: 'rgba(99,135,241,0.08)' },
          { label: 'Open Alerts', value: data.open_alerts, color: '#38BDF8', gradient: 'rgba(56,189,248,0.08)' },
          { label: 'Investigated', value: data.total_investigated, color: '#A78BFA', gradient: 'rgba(167,139,250,0.08)' },
          { label: 'Total Users', value: data.total_users, color: '#34D399', gradient: 'rgba(52,211,153,0.08)' },
        ].map((stat) => (
          <motion.div
            key={stat.label}
            variants={itemVariants}
            whileHover={{ scale: 1.02, boxShadow: `0 0 25px ${stat.color}15` }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            style={{
              background: `linear-gradient(145deg, #111827, #0F1420)`,
              border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: 14,
              padding: '18px 20px',
              display: 'flex', alignItems: 'center', gap: 14,
            }}
          >
            <div style={{
              width: 40, height: 40, borderRadius: 12,
              background: stat.gradient,
              border: `1px solid ${stat.color}20`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: stat.color, flexShrink: 0,
            }}>
              {STAT_ICONS[stat.label]}
            </div>
            <div>
              <p style={{ fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077', marginBottom: 4 }}>
                {stat.label}
              </p>
              <p style={{ fontSize: '1.4rem', fontWeight: 800, color: stat.color, lineHeight: 1, letterSpacing: '-0.02em' }}>
                <AnimatedNumber value={stat.value} duration={0.9} />
              </p>
            </div>
          </motion.div>
        ))}
      </div>


      {/* ═══════════════════════════════════════════════════════════════
          TWO-COLUMN — AI Threat Matrix + Top Risky Users
          ═══════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: isTablet ? '1fr' : '1fr 1.15fr', gap: 20, marginBottom: 24 }}>

        {/* ── AI Threat Matrix ── */}
        <motion.div
          variants={itemVariants}
          style={{
            background: 'linear-gradient(145deg, #111827 0%, #0F1420 100%)',
            border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: 20,
            padding: 24,
            position: 'relative', overflow: 'hidden',
          }}
        >
          <ScanLine />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6387F1" strokeWidth="2" strokeLinecap="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
            </svg>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
              AI Threat Matrix
            </span>
          </div>

          {/* Threat type rows */}
          {[
            { type: 'DATA EXFILTRATION', count: data.recent_alerts.filter(a => a.alert_type === 'DATA_EXFILTRATION').length, color: '#F87171' },
            { type: 'ANOMALY', count: data.recent_alerts.filter(a => a.alert_type === 'ANOMALY').length, color: '#FB923C' },
            { type: 'DISGRUNTLED SABOTAGE', count: data.recent_alerts.filter(a => a.alert_type === 'DISGRUNTLED_SABOTAGE').length, color: '#FACC15' },
          ].map((t, i) => {
            const maxCount = Math.max(data.total_alerts, 1);
            const pct = (t.count / maxCount) * 100;
            return (
              <motion.div
                key={t.type}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 + i * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  padding: '14px 16px', borderRadius: 12, marginBottom: 8,
                  background: 'rgba(255,255,255,0.015)',
                  border: '1px solid rgba(255,255,255,0.03)',
                  position: 'relative', overflow: 'hidden',
                }}
              >
                {/* Background fill */}
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.max(pct, 3)}%` }}
                  transition={{ delay: 0.7 + i * 0.15, duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                  style={{
                    position: 'absolute', top: 0, left: 0, bottom: 0,
                    background: `linear-gradient(90deg, ${t.color}08, ${t.color}15)`,
                    borderRadius: 12,
                  }}
                />
                <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <PulsingDot color={t.color} size={6} />
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94A3B8', letterSpacing: '0.02em' }}>
                      {t.type}
                    </span>
                  </div>
                  <span style={{ fontSize: '1rem', fontWeight: 800, color: t.color, fontVariantNumeric: 'tabular-nums' }}>
                    {t.count}
                  </span>
                </div>
              </motion.div>
            );
          })}

          {/* AI Status */}
          <div style={{
            marginTop: 16, padding: '12px 16px', borderRadius: 10,
            background: 'rgba(99,135,241,0.04)',
            border: '1px solid rgba(99,135,241,0.08)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6387F1" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4m-9.2-5.8l2.8-2.8m12.8-4.8l2.8-2.8M1 12h4m14 0h4M4.2 4.2l2.8 2.8m9.2 9.2l2.8 2.8"/>
              </svg>
            </motion.div>
            <span style={{ fontSize: '0.68rem', color: '#6387F1', fontWeight: 600 }}>
              AI Engine analyzing {data.total_users.toLocaleString()} behavior patterns
            </span>
          </div>
        </motion.div>


        {/* ── Top Risky Users ── */}
        <motion.div
          variants={itemVariants}
          style={{
            background: 'linear-gradient(145deg, #111827 0%, #0F1420 100%)',
            border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: 20,
            padding: 24,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F87171" strokeWidth="2" strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
              Highest Risk Users
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {data.top_risky_users.map((u, i) => {
              const riskColor = u.risk_score >= 90 ? '#F87171' : u.risk_score >= 70 ? '#FB923C' : u.risk_score >= 40 ? '#FACC15' : '#4ADE80';
              return (
                <motion.div
                  key={u.user_id}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  onClick={() => {
                    const a = data.recent_alerts.find(a => a.user_id === u.user_id);
                    navigate(a ? `/alerts/${a.id}` : '/alerts');
                  }}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', borderRadius: 10, cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    background: 'transparent',
                    borderBottom: '1px solid rgba(255,255,255,0.025)',
                  }}
                  whileHover={{
                    background: 'rgba(255,255,255,0.025)',
                    x: 4,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{
                      fontSize: '0.65rem', fontWeight: 700, color: '#3A4357',
                      width: 20, textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                    }}>
                      {String(i + 1).padStart(2, '0')}
                    </span>

                    {/* Avatar circle */}
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: `linear-gradient(135deg, ${riskColor}15, ${riskColor}08)`,
                      border: `1px solid ${riskColor}20`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '0.6rem', fontWeight: 800, color: riskColor,
                    }}>
                      {u.user_id.substring(0, 2)}
                    </div>

                    <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#E2E8F0', fontFamily: "'Inter', monospace" }}>
                      {u.user_id}
                    </span>
                    {u.is_insider && (
                      <span style={{
                        fontSize: '0.55rem', fontWeight: 700, padding: '2px 7px', borderRadius: 5,
                        background: 'rgba(248,113,113,0.08)', color: '#F87171',
                        border: '1px solid rgba(248,113,113,0.15)',
                        letterSpacing: '0.06em',
                      }}>
                        THREAT
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {/* Circular progress */}
                    <svg width="26" height="26" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="3" />
                      <circle
                        cx="18" cy="18" r="14" fill="none"
                        stroke={riskColor}
                        strokeWidth="3"
                        strokeDasharray={`${(u.risk_score / 100) * 88} 88`}
                        strokeLinecap="round"
                        transform="rotate(-90 18 18)"
                        style={{ transition: 'stroke-dasharray 1s ease' }}
                      />
                    </svg>
                    <span style={{
                      fontSize: '0.82rem', fontWeight: 800, color: riskColor,
                      fontVariantNumeric: 'tabular-nums', width: 28, textAlign: 'right',
                    }}>
                      {u.risk_score.toFixed(0)}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </div>


      {/* ═══════════════════════════════════════════════════════════════
          RECENT ALERTS TABLE
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemVariants}
        style={{
          background: 'linear-gradient(145deg, #111827 0%, #0F1420 100%)',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: 20,
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '22px 24px 0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#526077" strokeWidth="2" strokeLinecap="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
              Recent Activity Feed
            </span>
          </div>
          <button
            onClick={() => navigate('/alerts')}
            style={{
              fontSize: '0.65rem', fontWeight: 600, color: '#6387F1', background: 'rgba(99,135,241,0.06)',
              border: '1px solid rgba(99,135,241,0.12)', borderRadius: 8, padding: '5px 12px',
              cursor: 'pointer', transition: 'all 0.2s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,135,241,0.12)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(99,135,241,0.06)'; }}
          >
            View All
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>User</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Risk Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_alerts.slice(0, 10).map((a, i) => (
                <motion.tr
                  key={a.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + i * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  onClick={() => navigate(`/alerts/${a.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: '#3A4357' }}>#{a.id}</span>
                  </td>
                  <td style={{ fontWeight: 600, fontSize: '0.82rem' }}>{a.user_id}</td>
                  <td style={{ fontSize: '0.75rem', color: '#94A3B8' }}>{a.alert_type.replace(/_/g, ' ')}</td>
                  <td><span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span></td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{
                        width: 52, height: 4, borderRadius: 999,
                        background: 'rgba(255,255,255,0.04)', overflow: 'hidden',
                      }}>
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${a.risk_score}%` }}
                          transition={{ delay: 0.8 + i * 0.05, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                          style={{
                            height: '100%', borderRadius: 999,
                            background: a.risk_score >= 90 ? '#F87171' : a.risk_score >= 70 ? '#FB923C' : '#FACC15',
                          }}
                        />
                      </div>
                      <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 700, color: '#94A3B8', fontVariantNumeric: 'tabular-nums' }}>
                        {a.risk_score.toFixed(1)}
                      </span>
                    </div>
                  </td>
                  <td><span className={`badge badge-status-${a.status}`}>{a.status}</span></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Bottom spacing */}
      <div style={{ height: 40 }} />
    </motion.div>
  );
}
