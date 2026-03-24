import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchAlerts } from '../api';

/* ═══════════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ═══════════════════════════════════════════════════════════════════════ */

const SEV = {
  CRITICAL: { color: '#F87171', glow: 'rgba(248,113,113,0.20)', bg: 'rgba(248,113,113,0.05)', border: 'rgba(248,113,113,0.12)', gradient: 'linear-gradient(90deg, #F87171, #EF4444)' },
  HIGH:     { color: '#FB923C', glow: 'rgba(251,146,60,0.20)',  bg: 'rgba(251,146,60,0.05)',  border: 'rgba(251,146,60,0.12)',  gradient: 'linear-gradient(90deg, #FB923C, #F97316)' },
  MEDIUM:   { color: '#FACC15', glow: 'rgba(250,204,21,0.20)',  bg: 'rgba(250,204,21,0.05)',  border: 'rgba(250,204,21,0.12)',  gradient: 'linear-gradient(90deg, #FACC15, #EAB308)' },
  LOW:      { color: '#4ADE80', glow: 'rgba(74,222,128,0.20)',  bg: 'rgba(74,222,128,0.05)',  border: 'rgba(74,222,128,0.12)',  gradient: 'linear-gradient(90deg, #4ADE80, #22C55E)' },
};

const STATUS_META = {
  open:         { color: '#6387F1', bg: 'rgba(99,135,241,0.08)',  border: 'rgba(99,135,241,0.15)' },
  acknowledged: { color: '#A78BFA', bg: 'rgba(167,139,250,0.08)', border: 'rgba(167,139,250,0.15)' },
  escalated:    { color: '#F87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.15)' },
  dismissed:    { color: '#526077', bg: 'rgba(82,96,119,0.08)',   border: 'rgba(82,96,119,0.15)' },
};

const SEVERITIES = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const STATUSES = ['ALL', 'open', 'acknowledged', 'dismissed', 'escalated'];


/* ═══════════════════════════════════════════════════════════════════════
   SUB-COMPONENTS
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Pulsing Dot ── */
function PulsingDot({ color, size = 6 }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block', width: size, height: size, flexShrink: 0 }}>
      <span style={{
        position: 'absolute', inset: -2, borderRadius: '50%', backgroundColor: color,
        animation: 'pulseGlow 2s ease-in-out infinite', opacity: 0.5,
      }} />
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%', backgroundColor: color,
      }} />
    </span>
  );
}

/* ── Filter Pill ── */
function FilterPill({ label, active, onClick, accentColor }) {
  const baseColor = accentColor || '#6387F1';
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 500, damping: 25 }}
      style={{
        padding: '6px 16px', borderRadius: 20,
        fontSize: '0.68rem', fontWeight: 600,
        cursor: 'pointer', textTransform: 'capitalize',
        transition: 'all 0.2s ease',
        background: active ? `${baseColor}12` : 'rgba(255,255,255,0.02)',
        color: active ? baseColor : '#64748B',
        border: `1px solid ${active ? `${baseColor}30` : 'rgba(255,255,255,0.04)'}`,
        boxShadow: active ? `0 0 16px ${baseColor}15` : 'none',
        letterSpacing: '0.02em',
      }}
    >
      {label}
    </motion.button>
  );
}

/* ── Stat Mini Card ── */
function StatChip({ icon, label, value, color }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '8px 14px', borderRadius: 10,
      background: `${color}06`,
      border: `1px solid ${color}12`,
    }}>
      <span style={{ color, opacity: 0.7 }}>{icon}</span>
      <span style={{ fontSize: '0.6rem', color: '#526077', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════════════════
   MOTION VARIANTS
   ═══════════════════════════════════════════════════════════════════════ */

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } },
};

const rowVariants = {
  hidden: { opacity: 0, x: -8 },
  show: (i) => ({
    opacity: 1, x: 0,
    transition: { delay: i * 0.025, duration: 0.35, ease: [0.16, 1, 0.3, 1] },
  }),
};


/* ═══════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

export default function AlertQueue() {
  const [alerts, setAlerts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sevFilter, setSevFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [page, setPage] = useState(0);
  const perPage = 20;
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    const params = { limit: perPage, offset: page * perPage };
    if (sevFilter !== 'ALL') params.severity = sevFilter;
    if (statusFilter !== 'ALL') params.status = statusFilter;
    fetchAlerts(params)
      .then(d => { setAlerts(d.alerts); setTotal(d.total); setLoading(false); })
      .catch(() => setLoading(false));
  }, [sevFilter, statusFilter, page]);

  const totalPages = Math.ceil(total / perPage);

  // Count severity breakdowns from current page for stat chips
  const sevCounts = {};
  alerts.forEach(a => { sevCounts[a.severity] = (sevCounts[a.severity] || 0) + 1; });

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
      <motion.div variants={itemVariants} style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
              <h1 style={{
                fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.03em',
                background: 'linear-gradient(135deg, #E2E8F0 30%, #94A3B8)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>
                Alert Queue
              </h1>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 12px', borderRadius: 20,
                background: 'rgba(99,135,241,0.06)',
                border: '1px solid rgba(99,135,241,0.12)',
              }}>
                <PulsingDot color="#6387F1" />
                <span style={{ fontSize: '0.6rem', fontWeight: 600, color: '#6387F1', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  Monitoring
                </span>
              </div>
            </div>
            <p style={{ fontSize: '0.78rem', color: '#526077', fontWeight: 500 }}>
              {total.toLocaleString()} alerts detected across all severity levels
            </p>
          </div>

          {/* Summary stat chips */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <StatChip
              icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/></svg>}
              label="Critical" value={sevCounts.CRITICAL || 0} color="#F87171"
            />
            <StatChip
              icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>}
              label="High" value={sevCounts.HIGH || 0} color="#FB923C"
            />
            <StatChip
              icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>}
              label="Medium" value={sevCounts.MEDIUM || 0} color="#FACC15"
            />
          </div>
        </div>
      </motion.div>


      {/* ═══════════════════════════════════════════════════════════════
          FILTERS
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemVariants}
        style={{
          display: 'flex', flexWrap: 'wrap', gap: 20, marginBottom: 20,
          padding: '16px 20px', borderRadius: 14,
          background: 'linear-gradient(145deg, rgba(17,24,39,0.5), rgba(15,20,32,0.3))',
          border: '1px solid rgba(255,255,255,0.03)',
        }}
      >
        {/* Severity filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3A4357" strokeWidth="2" strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#3A4357' }}>
              Severity
            </span>
          </div>
          <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.04)' }} />
          <div style={{ display: 'flex', gap: 5 }}>
            {SEVERITIES.map(s => (
              <FilterPill
                key={s} label={s} active={sevFilter === s}
                onClick={() => { setSevFilter(s); setPage(0); }}
                accentColor={s === 'ALL' ? '#6387F1' : SEV[s]?.color}
              />
            ))}
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 28, background: 'rgba(255,255,255,0.04)', alignSelf: 'center' }} />

        {/* Status filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3A4357" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <span style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#3A4357' }}>
              Status
            </span>
          </div>
          <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.04)' }} />
          <div style={{ display: 'flex', gap: 5 }}>
            {STATUSES.map(s => (
              <FilterPill
                key={s} label={s} active={statusFilter === s}
                onClick={() => { setStatusFilter(s); setPage(0); }}
                accentColor={s === 'ALL' ? '#6387F1' : STATUS_META[s]?.color}
              />
            ))}
          </div>
        </div>
      </motion.div>


      {/* ═══════════════════════════════════════════════════════════════
          ALERT TABLE
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemVariants}
        style={{
          background: 'linear-gradient(145deg, #111827 0%, #0F1420 100%)',
          border: '1px solid rgba(255,255,255,0.04)',
          borderRadius: 20,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Scanning top line */}
        <motion.div
          style={{
            position: 'absolute', top: 0, left: 0, right: 0, height: 1,
            background: 'linear-gradient(90deg, transparent, rgba(99,135,241,0.3), transparent)',
          }}
          animate={{ x: ['-100%', '100%'] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'linear' }}
        />

        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '80px 0', gap: 12 }}>
            <div className="spinner" />
            <span style={{ fontSize: '0.75rem', color: '#526077', fontWeight: 500 }}>Loading alerts...</span>
          </div>
        ) : (
          <div className="overflow-x-auto w-full">
            <table style={{ width: '100%', minWidth: 1000, borderCollapse: 'separate', borderSpacing: '0 2px' }}>
              <thead>
                <tr>
                  {['ID', 'User', 'Alert Type', 'Severity', 'Risk Score', 'Status', 'Investigation'].map(h => (
                    <th key={h} style={{
                      padding: '14px 20px', textAlign: 'left',
                      fontSize: '0.6rem', fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: '0.1em',
                      color: '#3A4357',
                      borderBottom: '1px solid rgba(255,255,255,0.03)',
                      background: 'rgba(10,14,24,0.5)',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <AnimatePresence mode="popLayout">
                  {alerts.map((a, i) => {
                    const sev = SEV[a.severity] || SEV.MEDIUM;
                    const statusMeta = STATUS_META[a.status] || STATUS_META.open;
                    const isHighRisk = a.risk_score >= 80;
                    const riskColor = a.risk_score >= 90 ? '#F87171' : a.risk_score >= 70 ? '#FB923C' : a.risk_score >= 40 ? '#FACC15' : '#4ADE80';

                    return (
                      <motion.tr
                        key={a.id}
                        custom={i}
                        variants={rowVariants}
                        initial="hidden"
                        animate="show"
                        exit={{ opacity: 0, x: -8 }}
                        onClick={() => navigate(`/alerts/${a.id}`)}
                        style={{
                          cursor: 'pointer',
                          background: isHighRisk && i < 3
                            ? `linear-gradient(90deg, ${sev.bg}, transparent 60%)`
                            : 'transparent',
                          transition: 'background 0.2s ease',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = `linear-gradient(90deg, ${sev.bg}, rgba(255,255,255,0.015) 50%, transparent)`;
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = isHighRisk && i < 3
                            ? `linear-gradient(90deg, ${sev.bg}, transparent 60%)`
                            : 'transparent';
                        }}
                      >
                        {/* ID */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <span style={{ fontFamily: "'Inter', monospace", fontSize: '0.7rem', color: '#3A4357', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                            #{a.id}
                          </span>
                        </td>

                        {/* User */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <div style={{
                              width: 28, height: 28, borderRadius: 8,
                              background: `linear-gradient(135deg, ${riskColor}12, ${riskColor}06)`,
                              border: `1px solid ${riskColor}18`,
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              fontSize: '0.55rem', fontWeight: 800, color: riskColor,
                              flexShrink: 0,
                            }}>
                              {a.user_id.substring(0, 2)}
                            </div>
                            <span style={{ fontWeight: 600, fontSize: '0.82rem', color: '#E2E8F0' }}>
                              {a.user_id}
                            </span>
                          </div>
                        </td>

                        {/* Alert Type */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <span style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>
                            {a.alert_type.replace(/_/g, ' ')}
                          </span>
                        </td>

                        {/* Severity */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            {(a.severity === 'CRITICAL' || a.severity === 'HIGH') && (
                              <PulsingDot color={sev.color} size={5} />
                            )}
                            <span style={{
                              display: 'inline-block', padding: '4px 12px', borderRadius: 8,
                              fontSize: '0.62rem', fontWeight: 700,
                              letterSpacing: '0.06em', textTransform: 'uppercase',
                              background: sev.bg,
                              color: sev.color,
                              border: `1px solid ${sev.border}`,
                              boxShadow: (a.severity === 'CRITICAL' || a.severity === 'HIGH') ? `0 0 12px ${sev.glow}` : 'none',
                            }}>
                              {a.severity}
                            </span>
                          </div>
                        </td>

                        {/* Risk Score */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <div style={{
                              width: 60, height: 5, borderRadius: 999,
                              background: 'rgba(255,255,255,0.04)', overflow: 'hidden',
                            }}>
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${a.risk_score}%` }}
                                transition={{ delay: 0.3 + i * 0.03, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                                style={{
                                  height: '100%', borderRadius: 999,
                                  background: sev.gradient,
                                  boxShadow: `0 0 6px ${riskColor}40`,
                                }}
                              />
                            </div>
                            <span style={{
                              fontFamily: "'Inter', monospace", fontSize: '0.78rem',
                              fontWeight: 700, color: riskColor,
                              fontVariantNumeric: 'tabular-nums', width: 32, textAlign: 'right',
                            }}>
                              {a.risk_score.toFixed(1)}
                            </span>
                          </div>
                        </td>

                        {/* Status */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <span style={{
                            display: 'inline-block', padding: '4px 12px', borderRadius: 8,
                            fontSize: '0.62rem', fontWeight: 700,
                            letterSpacing: '0.04em', textTransform: 'uppercase',
                            background: statusMeta.bg,
                            color: statusMeta.color,
                            border: `1px solid ${statusMeta.border}`,
                          }}>
                            {a.status}
                          </span>
                        </td>

                        {/* Investigation */}
                        <td style={{ padding: '14px 20px', verticalAlign: 'middle', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          {a.has_investigation ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <div style={{
                                width: 18, height: 18, borderRadius: 6,
                                background: 'rgba(52,211,153,0.08)',
                                border: '1px solid rgba(52,211,153,0.15)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                              }}>
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#34D399" strokeWidth="3" strokeLinecap="round">
                                  <path d="M20 6L9 17l-5-5"/>
                                </svg>
                              </div>
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#34D399' }}>
                                Complete
                              </span>
                            </div>
                          ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <div style={{
                                width: 18, height: 18, borderRadius: 6,
                                background: 'rgba(82,96,119,0.06)',
                                border: '1px solid rgba(82,96,119,0.1)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                              }}>
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#3A4357" strokeWidth="2" strokeLinecap="round">
                                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                                </svg>
                              </div>
                              <span style={{ fontSize: '0.7rem', fontWeight: 500, color: '#3A4357' }}>
                                Pending
                              </span>
                            </div>
                          )}
                        </td>
                      </motion.tr>
                    );
                  })}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </motion.div>


      {/* ═══════════════════════════════════════════════════════════════
          PAGINATION
          ═══════════════════════════════════════════════════════════════ */}
      {totalPages > 1 && (
        <motion.div
          variants={itemVariants}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: 20,
          }}
        >
          <motion.button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            whileHover={page > 0 ? { scale: 1.03 } : {}}
            whileTap={page > 0 ? { scale: 0.97 } : {}}
            style={{
              padding: '9px 20px', borderRadius: 10,
              fontSize: '0.72rem', fontWeight: 600,
              cursor: page === 0 ? 'not-allowed' : 'pointer',
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.05)',
              color: page === 0 ? '#2D3A52' : '#94A3B8',
              transition: 'all 0.2s ease',
              display: 'flex', alignItems: 'center', gap: 6,
              opacity: page === 0 ? 0.4 : 1,
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>
            Previous
          </motion.button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, idx) => {
              let pageNum;
              if (totalPages <= 7) {
                pageNum = idx;
              } else if (page < 3) {
                pageNum = idx;
              } else if (page > totalPages - 4) {
                pageNum = totalPages - 7 + idx;
              } else {
                pageNum = page - 3 + idx;
              }
              const isCurrent = pageNum === page;
              return (
                <motion.button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    fontSize: '0.72rem', fontWeight: isCurrent ? 700 : 500,
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: isCurrent ? 'linear-gradient(135deg, rgba(99,135,241,0.15), rgba(167,139,250,0.1))' : 'transparent',
                    color: isCurrent ? '#6387F1' : '#526077',
                    border: isCurrent ? '1px solid rgba(99,135,241,0.2)' : '1px solid transparent',
                    boxShadow: isCurrent ? '0 0 12px rgba(99,135,241,0.08)' : 'none',
                    transition: 'all 0.2s ease',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {pageNum + 1}
                </motion.button>
              );
            })}
          </div>

          <motion.button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            whileHover={page < totalPages - 1 ? { scale: 1.03 } : {}}
            whileTap={page < totalPages - 1 ? { scale: 0.97 } : {}}
            style={{
              padding: '9px 20px', borderRadius: 10,
              fontSize: '0.72rem', fontWeight: 600,
              cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.05)',
              color: page >= totalPages - 1 ? '#2D3A52' : '#94A3B8',
              transition: 'all 0.2s ease',
              display: 'flex', alignItems: 'center', gap: 6,
              opacity: page >= totalPages - 1 ? 0.4 : 1,
            }}
          >
            Next
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="9 18 15 12 9 6"/></svg>
          </motion.button>
        </motion.div>
      )}

      {/* Bottom spacing */}
      <div style={{ height: 40 }} />
    </motion.div>
  );
}
