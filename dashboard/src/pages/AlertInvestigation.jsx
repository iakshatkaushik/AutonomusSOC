import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchAlert, fetchUserLogs, triggerInvestigation, updateAlertStatus, downloadReportPdf } from '../api';

/* ═══════════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ═══════════════════════════════════════════════════════════════════════ */

const SEV_COLORS = {
  CRITICAL: { primary: '#F87171', glow: 'rgba(248,113,113,0.15)', bg: 'rgba(248,113,113,0.06)', border: 'rgba(248,113,113,0.12)' },
  HIGH:     { primary: '#FB923C', glow: 'rgba(251,146,60,0.15)',  bg: 'rgba(251,146,60,0.06)',  border: 'rgba(251,146,60,0.12)' },
  MEDIUM:   { primary: '#FACC15', glow: 'rgba(250,204,21,0.15)',  bg: 'rgba(250,204,21,0.06)',  border: 'rgba(250,204,21,0.12)' },
  LOW:      { primary: '#4ADE80', glow: 'rgba(74,222,128,0.15)',  bg: 'rgba(74,222,128,0.06)',  border: 'rgba(74,222,128,0.12)' },
};

const TYPE_ICONS = {
  LOGON: { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>, color: '#93B4FD', bg: 'rgba(99,135,241,0.08)' },
  FILE:  { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>, color: '#FDBA74', bg: 'rgba(251,146,60,0.08)' },
  EMAIL: { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>, color: '#6EE7B7', bg: 'rgba(52,211,153,0.08)' },
  HTTP:  { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>, color: '#C4B5FD', bg: 'rgba(167,139,250,0.08)' },
};

const containerV = { hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.08 } } };
const itemV = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } } };


/* ═══════════════════════════════════════════════════════════════════════
   RISK GAUGE — Animated radial with gradient stroke + glow
   ═══════════════════════════════════════════════════════════════════════ */

function RiskGauge({ score, size = 180 }) {
  const color = score >= 90 ? '#F87171' : score >= 70 ? '#FB923C' : score >= 40 ? '#FACC15' : '#4ADE80';
  const colorEnd = score >= 90 ? '#EF4444' : score >= 70 ? '#F97316' : score >= 40 ? '#EAB308' : '#22C55E';
  const r = (size - 16) / 2;
  const circ = 2 * Math.PI * r;
  const gradId = `rg-${score}`;

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      {/* Glow */}
      <div style={{
        position: 'absolute', inset: '10%', borderRadius: '50%',
        background: `radial-gradient(circle, ${color}12 0%, transparent 70%)`,
        filter: 'blur(8px)',
      }} />
      <svg width={size} height={size} style={{ position: 'relative', zIndex: 1 }}>
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} />
            <stop offset="100%" stopColor={colorEnd} />
          </linearGradient>
        </defs>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="10" />
        <motion.circle
          cx={size/2} cy={size/2} r={r} fill="none"
          stroke={`url(#${gradId})`} strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - (score / 100) * circ }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ filter: `drop-shadow(0 0 10px ${color}50)` }}
        />
        <text x={size/2} y={size/2 - 6} textAnchor="middle" fill={color} fontSize="36" fontWeight="800" fontFamily="Inter, sans-serif">
          {score.toFixed(0)}
        </text>
        <text x={size/2} y={size/2 + 16} textAnchor="middle" fill="#3A4357" fontSize="12" fontWeight="600">/100</text>
      </svg>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════════════════
   SECTION CARD WRAPPER
   ═══════════════════════════════════════════════════════════════════════ */

function Panel({ children, style = {} }) {
  return (
    <motion.div
      variants={itemV}
      style={{
        background: 'linear-gradient(145deg, #111827, #0F1420)',
        border: '1px solid rgba(255,255,255,0.04)',
        borderRadius: 20, padding: 24,
        position: 'relative', overflow: 'hidden',
        ...style,
      }}
    >
      {children}
    </motion.div>
  );
}

function SectionLabel({ icon, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
      <span style={{ color: '#526077' }}>{icon}</span>
      <span style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
        {children}
      </span>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

export default function AlertInvestigation() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [investigateError, setInvestigateError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const load = () => {
    setLoading(true);
    fetchAlert(id).then(d => {
      setAlert(d);
      setLoading(false);
      fetchUserLogs(d.user_id).then(l => setLogs(l.logs)).catch(() => {});
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, [id]);

  const handleInvestigate = () => {
    setInvestigating(true);
    setInvestigateError(null);
    triggerInvestigation(id)
      .then(() => { load(); setInvestigating(false); })
      .catch((err) => {
        setInvestigating(false);
        const msg = err?.response?.data?.detail || err?.message || 'Investigation failed.';
        setInvestigateError(msg);
        setTimeout(() => setInvestigateError(null), 15000);
      });
  };

  const handleStatus = (status) => {
    setStatusUpdating(true);
    updateAlertStatus(id, status)
      .then(() => { load(); setStatusUpdating(false); })
      .catch(() => setStatusUpdating(false));
  };

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '30vh' }}><div className="spinner" /></div>;
  if (!alert) return <p style={{ color: '#526077' }}>Alert not found.</p>;

  const sev = SEV_COLORS[alert.severity] || SEV_COLORS.MEDIUM;
  const report = alert.investigation_report;

  // Build event timeline
  const timeline = [];
  if (logs) {
    (logs.logon_events || []).forEach(e => timeline.push({ ...e, type: 'LOGON' }));
    (logs.file_events || []).forEach(e => timeline.push({ ...e, type: 'FILE' }));
    (logs.email_events || []).forEach(e => timeline.push({ ...e, type: 'EMAIL' }));
    (logs.http_events || []).forEach(e => timeline.push({ ...e, type: 'HTTP' }));
  }
  timeline.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));

  return (
    <motion.div
      variants={containerV} initial="hidden" animate="show"
      style={{ maxWidth: 1360, margin: '0 auto' }}
    >
      {/* ═══════════════════════════════════════════════════════════════
          BACK BUTTON
          ═══════════════════════════════════════════════════════════════ */}
      <motion.button
        variants={itemV}
        onClick={() => navigate(-1)}
        whileHover={{ x: -3 }}
        style={{
          background: 'none', border: 'none', color: '#526077', fontSize: '0.78rem',
          cursor: 'pointer', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6,
          fontWeight: 500,
        }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/>
        </svg>
        Back to alerts
      </motion.button>


      {/* ═══════════════════════════════════════════════════════════════
          HEADER — Alert Identity + Severity + Status
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemV}
        style={{
          padding: '24px 28px', borderRadius: 20, marginBottom: 24,
          background: `linear-gradient(145deg, #111827, #0F1420)`,
          border: `1px solid ${sev.border}`,
          position: 'relative', overflow: 'hidden',
        }}
      >
        {/* Severity accent line */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, transparent, ${sev.primary}40, transparent)`,
        }} />

        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
              <h1 style={{
                fontSize: '1.6rem', fontWeight: 800, letterSpacing: '-0.03em',
                background: 'linear-gradient(135deg, #E2E8F0 30%, #94A3B8)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>
                Alert #{alert.id}
              </h1>
              <span style={{ fontSize: '1rem', fontWeight: 800, color: '#6387F1' }}>
                {alert.user_id}
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: '#526077', fontWeight: 500 }}>
              {alert.alert_type.replace(/_/g, ' ')} · {alert.created_at}
            </p>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            {/* Severity badge */}
            <div style={{
              padding: '5px 14px', borderRadius: 10,
              background: sev.bg, border: `1px solid ${sev.border}`,
              fontSize: '0.62rem', fontWeight: 700, color: sev.primary,
              textTransform: 'uppercase', letterSpacing: '0.08em',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%', background: sev.primary,
                boxShadow: `0 0 6px ${sev.primary}`,
                ...(alert.severity === 'CRITICAL' ? { animation: 'pulseGlow 2s ease-in-out infinite' } : {}),
              }} />
              {alert.severity}
            </div>
            {/* Status badge */}
            <div style={{
              padding: '5px 14px', borderRadius: 10,
              background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.12)',
              fontSize: '0.62rem', fontWeight: 700, color: '#A78BFA',
              textTransform: 'uppercase', letterSpacing: '0.08em',
            }}>
              {alert.status}
            </div>
          </div>
        </div>
      </motion.div>


      {/* ═══════════════════════════════════════════════════════════════
          TOP ROW — Risk → Factors → Actions
          ═══════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 280px', gap: 16, marginBottom: 24 }}>

        {/* ── RISK ASSESSMENT ───────────────────────────────────────── */}
        <Panel>
          <SectionLabel icon={
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          }>
            Risk Assessment
          </SectionLabel>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
            <RiskGauge score={alert.risk_score} size={160} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', width: '100%' }}>
              {[
                { l: 'Type', v: alert.alert_type.replace(/_/g, ' ') },
                { l: 'Score', v: alert.risk_score.toFixed(1) },
                { l: 'Severity', v: alert.severity },
                { l: 'Status', v: alert.status },
              ].map(({ l, v }) => (
                <div key={l}>
                  <p style={{ fontSize: '0.55rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#3A4357', marginBottom: 2 }}>{l}</p>
                  <p style={{ fontSize: '0.78rem', fontWeight: 600, color: '#94A3B8', textTransform: 'capitalize' }}>{v}</p>
                </div>
              ))}
            </div>
          </div>
        </Panel>


        {/* ── BEHAVIORAL ANOMALY PROFILE ─────────────────────────── */}
        <Panel>
          <SectionLabel icon={
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
            </svg>
          }>
            Behavioral Anomaly Profile
          </SectionLabel>

          {(() => {
            // Derive anomaly dimensions from alert data
            const rs = alert.risk_score / 100;
            const dims = [
              { label: 'Access', full: 'Access Pattern', val: Math.min(rs * 1.05, 1), color: '#F87171' },
              { label: 'Data Mvmt', full: 'Data Movement', val: Math.min(rs * 0.95, 1), color: '#FB923C' },
              { label: 'Time', full: 'Time Anomaly', val: Math.min(rs * 1.1, 1), color: '#FACC15' },
              { label: 'Network', full: 'Network Activity', val: Math.min(rs * 0.7, 1), color: '#6387F1' },
              { label: 'Device', full: 'Device Usage', val: Math.min(rs * 0.85, 1), color: '#A78BFA' },
              { label: 'Comms', full: 'Communication', val: Math.min(rs * 0.6, 1), color: '#22D3EE' },
            ];

            // Mini radar
            const size = 230, cx = size/2, cy = size/2, radius = size * 0.36;
            const n = dims.length;
            const angleStep = (2 * Math.PI) / n;
            const getPoint = (i, v) => ({
              x: cx + radius * v * Math.cos(i * angleStep - Math.PI/2),
              y: cy + radius * v * Math.sin(i * angleStep - Math.PI/2),
            });
            const rings = [0.33, 0.66, 1.0];
            const dataPoints = dims.map((d, i) => getPoint(i, d.val));

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Radar */}
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                    {rings.map(r => (
                      <polygon key={r}
                        points={dims.map((_, i) => { const p = getPoint(i, r); return `${p.x},${p.y}`; }).join(' ')}
                        fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1"
                      />
                    ))}
                    {dims.map((_, i) => {
                      const p = getPoint(i, 1);
                      return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.03)" strokeWidth="1" />;
                    })}
                    <motion.polygon
                      points={dataPoints.map(p => `${p.x},${p.y}`).join(' ')}
                      fill="rgba(248,113,113,0.08)"
                      stroke="#F87171" strokeWidth="1.5"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.5, duration: 0.6 }}
                    />
                    {dataPoints.map((p, i) => (
                      <motion.circle key={i} cx={p.x} cy={p.y} r="3"
                        fill={dims[i].color} stroke="#0F1420" strokeWidth="1.5"
                        initial={{ scale: 0 }} animate={{ scale: 1 }}
                        transition={{ delay: 0.6 + i * 0.06, type: 'spring', stiffness: 300 }}
                        style={{ filter: `drop-shadow(0 0 3px ${dims[i].color}50)` }}
                      />
                    ))}
                    {dims.map((d, i) => {
                      const lp = getPoint(i, 1.25);
                      return (
                        <text key={d.label} x={lp.x} y={lp.y}
                          textAnchor="middle" dominantBaseline="middle"
                          style={{ fontSize: '0.45rem', fontWeight: 600, fill: '#3A4357' }}
                        >{d.label}</text>
                      );
                    })}
                  </svg>
                </div>

                {/* Threat Signal Tiles */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                  {dims.map((d, i) => {
                    const level = d.val >= 0.85 ? 'CRITICAL' : d.val >= 0.65 ? 'HIGH' : d.val >= 0.4 ? 'MEDIUM' : 'LOW';
                    const levColor = d.val >= 0.85 ? '#F87171' : d.val >= 0.65 ? '#FB923C' : d.val >= 0.4 ? '#FACC15' : '#4ADE80';
                    return (
                      <motion.div
                        key={d.full}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: 0.4 + i * 0.06 }}
                        style={{
                          padding: '10px 12px', borderRadius: 12,
                          background: `${d.color}05`,
                          border: `1px solid ${d.color}10`,
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        }}
                      >
                        <div>
                          <span style={{ fontSize: '0.65rem', fontWeight: 600, color: '#94A3B8', display: 'block', lineHeight: 1, marginBottom: 2 }}>{d.full}</span>
                          <span style={{ fontSize: '0.85rem', fontWeight: 800, color: d.color, fontVariantNumeric: 'tabular-nums' }}>
                            {(d.val * 100).toFixed(0)}%
                          </span>
                        </div>
                        <span style={{
                          padding: '2px 6px', borderRadius: 5,
                          background: `${levColor}10`, border: `1px solid ${levColor}15`,
                          fontSize: '0.45rem', fontWeight: 700, color: levColor,
                          textTransform: 'uppercase', letterSpacing: '0.05em',
                        }}>
                          {level}
                        </span>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            );
          })()}
        </Panel>


        {/* ── ACTIONS ───────────────────────────────────────────────── */}
        <Panel>
          <SectionLabel icon={
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          }>
            Actions
          </SectionLabel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* Primary CTA — Investigate */}
            <motion.button
              onClick={handleInvestigate}
              disabled={investigating}
              whileHover={{ scale: 1.02, boxShadow: '0 0 30px rgba(99,135,241,0.15)' }}
              whileTap={{ scale: 0.98 }}
              style={{
                width: '100%', padding: '14px 20px', borderRadius: 14,
                background: 'linear-gradient(135deg, #6387F1, #8B5CF6)',
                border: 'none', color: '#fff', fontSize: '0.82rem', fontWeight: 700,
                cursor: investigating ? 'wait' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                boxShadow: '0 4px 20px rgba(99,135,241,0.2)',
                opacity: investigating ? 0.7 : 1,
              }}
            >
              {investigating ? (
                <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} /> Running Agent...</>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                  </svg>
                  Investigate with AI
                </>
              )}
            </motion.button>

            {/* Secondary — Download PDF */}
            <motion.button
              onClick={() => { setDownloading(true); downloadReportPdf(id).then(() => setDownloading(false)).catch(() => setDownloading(false)); }}
              disabled={downloading}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              style={{
                width: '100%', padding: '12px 20px', borderRadius: 12,
                background: 'rgba(34,211,238,0.06)',
                border: '1px solid rgba(34,211,238,0.15)',
                color: '#22D3EE', fontSize: '0.78rem', fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
            >
              {downloading ? (
                <><div className="spinner spinner-sm" style={{ borderTopColor: '#22D3EE' }} /> Generating...</>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Download PDF Report
                </>
              )}
            </motion.button>

            {/* Error message */}
            <AnimatePresence>
              {investigateError && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  style={{
                    padding: '10px 14px', borderRadius: 10, fontSize: '0.7rem', lineHeight: 1.5,
                    background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.12)',
                    color: '#FCA5A5', wordBreak: 'break-word',
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }}>
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {investigateError}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Status buttons — ghost style */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 4 }}>
              {[
                { status: 'acknowledged', label: 'Acknowledge', color: '#A78BFA', icon: '✓' },
                { status: 'escalated', label: 'Escalate', color: '#F87171', icon: '⬆' },
                { status: 'dismissed', label: 'Dismiss', color: '#526077', icon: '✕' },
                { status: 'open', label: 'Re-open', color: '#6387F1', icon: '↺' },
              ].map(b => (
                <motion.button
                  key={b.status}
                  onClick={() => handleStatus(b.status)}
                  disabled={statusUpdating}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  style={{
                    padding: '9px 8px', borderRadius: 10, fontSize: '0.68rem', fontWeight: 600,
                    cursor: 'pointer',
                    background: `${b.color}08`, color: b.color,
                    border: `1px solid ${b.color}15`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                  }}
                >
                  <span style={{ fontSize: '0.7rem' }}>{b.icon}</span> {b.label}
                </motion.button>
              ))}
            </div>
          </div>
        </Panel>
      </div>


      {/* ═══════════════════════════════════════════════════════════════
          INVESTIGATION REPORT
          ═══════════════════════════════════════════════════════════════ */}
      {report ? (
        <Panel style={{ marginBottom: 24 }}>
          <SectionLabel icon={
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
            </svg>
          }>
            AI Investigation Report
          </SectionLabel>

          {/* Summary */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            style={{
              padding: '20px 24px', borderRadius: 14, marginBottom: 20,
              background: 'linear-gradient(135deg, rgba(99,135,241,0.06), rgba(139,92,246,0.04))',
              border: '1px solid rgba(99,135,241,0.1)',
            }}
          >
            <p style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#6387F1', marginBottom: 8 }}>Summary</p>
            <p style={{ fontSize: '0.85rem', lineHeight: 1.75, color: '#CBD5E1' }}>{report.summary}</p>
          </motion.div>

          {/* Key Findings */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 22 }}>
            {[
              { label: 'Threat Type', value: report.threat_scenario?.replace(/_/g, ' ') || 'Unknown', color: '#F87171' },
              { label: 'Confidence', value: `${((report.confidence || 0) * 100).toFixed(0)}%`, color: '#6387F1' },
              { label: 'Recommended', value: report.recommended_action?.replace(/_/g, ' ') || 'Monitor', color: '#4ADE80' },
              { label: 'LLM Model', value: report.llm_model || 'N/A', color: '#A78BFA' },
            ].map((item, i) => (
              <motion.div
                key={item.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + i * 0.08 }}
                style={{
                  padding: '14px 16px', borderRadius: 12,
                  background: `${item.color}04`,
                  border: `1px solid ${item.color}10`,
                }}
              >
                <p style={{ fontSize: '0.55rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#3A4357', marginBottom: 4 }}>{item.label}</p>
                <p style={{ fontSize: '0.82rem', fontWeight: 700, color: '#E2E8F0', textTransform: 'capitalize' }}>{item.value}</p>
              </motion.div>
            ))}
          </div>

          {/* Reasoning */}
          {report.reasoning && (
            <div style={{ marginBottom: 22 }}>
              <p style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077', marginBottom: 10 }}>Reasoning</p>
              <div style={{
                padding: '18px 22px', borderRadius: 14,
                background: 'rgba(255,255,255,0.015)',
                border: '1px solid rgba(255,255,255,0.03)',
                fontSize: '0.82rem', lineHeight: 1.85, color: '#94A3B8',
                whiteSpace: 'pre-wrap', maxHeight: 320, overflowY: 'auto',
              }}>
                {report.reasoning}
              </div>
            </div>
          )}

          {/* Evidence Chain */}
          {report.evidence_chain?.length > 0 && (
            <div style={{ marginBottom: 22 }}>
              <p style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077', marginBottom: 10 }}>Evidence Chain</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {report.evidence_chain.map((e, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + i * 0.05 }}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 12,
                      padding: '11px 16px', borderRadius: 10,
                      background: 'rgba(255,255,255,0.015)',
                      border: '1px solid rgba(255,255,255,0.03)',
                    }}
                  >
                    <span style={{
                      width: 22, height: 22, borderRadius: 7,
                      background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: 'monospace', color: '#22D3EE', fontWeight: 700, fontSize: '0.65rem',
                      flexShrink: 0,
                    }}>
                      {i + 1}
                    </span>
                    <span style={{ fontSize: '0.78rem', color: '#94A3B8', lineHeight: 1.6 }}>
                      {typeof e === 'string' ? e : JSON.stringify(e)}
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          )}

          {/* Recommended Actions + Correlated Users */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {report.recommended_actions_detail?.length > 0 && (
              <div>
                <p style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077', marginBottom: 10 }}>Recommended Actions</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {report.recommended_actions_detail.map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.78rem', color: '#94A3B8', lineHeight: 1.5 }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6387F1" strokeWidth="2.5" strokeLinecap="round" style={{ flexShrink: 0, marginTop: 3 }}>
                        <polyline points="9 18 15 12 9 6"/>
                      </svg>
                      <span>{a}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {report.correlated_users?.length > 0 && (
              <div>
                <p style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077', marginBottom: 10 }}>Correlated Users</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {report.correlated_users.map((u, i) => (
                    <span key={i} style={{
                      padding: '5px 14px', borderRadius: 8, fontSize: '0.72rem', fontWeight: 600,
                      background: 'rgba(167,139,250,0.06)', color: '#A78BFA', border: '1px solid rgba(167,139,250,0.12)',
                    }}>
                      {u}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Panel>
      ) : (
        /* Empty state — AI-ready */
        <Panel style={{ marginBottom: 24 }}>
          <div style={{ padding: '48px 24px', textAlign: 'center' }}>
            <motion.div
              animate={{ boxShadow: ['0 0 20px rgba(99,135,241,0.1)', '0 0 40px rgba(99,135,241,0.2)', '0 0 20px rgba(99,135,241,0.1)'] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                width: 64, height: 64, borderRadius: 20, margin: '0 auto 20px',
                background: 'linear-gradient(135deg, rgba(99,135,241,0.1), rgba(139,92,246,0.08))',
                border: '1px solid rgba(99,135,241,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6387F1" strokeWidth="1.5" strokeLinecap="round">
                <circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
              </svg>
            </motion.div>
            <p style={{ fontSize: '0.95rem', fontWeight: 700, color: '#E2E8F0', marginBottom: 6 }}>No investigation report yet</p>
            <p style={{ fontSize: '0.75rem', color: '#526077', marginBottom: 24 }}>Launch the AI agent to autonomously investigate this alert</p>
            <motion.button
              onClick={handleInvestigate}
              disabled={investigating}
              whileHover={{ scale: 1.03, boxShadow: '0 0 30px rgba(99,135,241,0.2)' }}
              whileTap={{ scale: 0.97 }}
              style={{
                padding: '14px 36px', borderRadius: 14,
                background: 'linear-gradient(135deg, #6387F1, #8B5CF6)',
                border: 'none', color: '#fff', fontSize: '0.82rem', fontWeight: 700,
                cursor: investigating ? 'wait' : 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 8,
                boxShadow: '0 4px 20px rgba(99,135,241,0.25)',
              }}
            >
              {investigating ? (
                <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} /> Running Agent...</>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                  </svg>
                  Run AI Investigation
                </>
              )}
            </motion.button>
            <AnimatePresence>
              {investigateError && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  style={{
                    padding: '12px 16px', borderRadius: 10, fontSize: '0.75rem', lineHeight: 1.6, marginTop: 16,
                    background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.12)',
                    color: '#FCA5A5', wordBreak: 'break-word', textAlign: 'left',
                  }}
                >
                  {investigateError}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Panel>
      )}


      {/* ═══════════════════════════════════════════════════════════════
          RAW EVENT TIMELINE — Vertical timeline with icons
          ═══════════════════════════════════════════════════════════════ */}
      <Panel style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
          <SectionLabel icon={
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          }>
            Event Timeline
          </SectionLabel>
          <span style={{ fontSize: '0.6rem', fontWeight: 600, color: '#3A4357', padding: '3px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
            {timeline.length} events
          </span>
        </div>

        <div style={{ maxHeight: 480, overflowY: 'auto', paddingRight: 8 }}>
          {timeline.length === 0 ? (
            <p style={{ fontSize: '0.78rem', color: '#526077', textAlign: 'center', padding: '40px 0' }}>No events found.</p>
          ) : (
            <div style={{ position: 'relative', paddingLeft: 32 }}>
              {/* Timeline line */}
              <div style={{
                position: 'absolute', left: 10, top: 8, bottom: 8, width: 1,
                background: 'linear-gradient(180deg, rgba(99,135,241,0.15), rgba(99,135,241,0.03))',
              }} />

              {timeline.slice(0, 80).map((e, i) => {
                const tc = TYPE_ICONS[e.type] || TYPE_ICONS.LOGON;
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(0.3 + i * 0.02, 1.5) }}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 14,
                      padding: '10px 14px', marginBottom: 2, borderRadius: 10,
                      transition: 'background 0.15s ease', cursor: 'default',
                      position: 'relative',
                    }}
                    onMouseEnter={ev => ev.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}
                  >
                    {/* Timeline dot */}
                    <div style={{
                      position: 'absolute', left: -28, top: 14,
                      width: 8, height: 8, borderRadius: '50%',
                      background: tc.bg, border: `2px solid ${tc.color}`,
                    }} />

                    {/* Type badge */}
                    <div style={{
                      padding: '4px 10px', borderRadius: 7, flexShrink: 0, minWidth: 60,
                      background: tc.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                      color: tc.color,
                    }}>
                      {tc.icon}
                      <span style={{ fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {e.type}
                      </span>
                    </div>

                    {/* Timestamp */}
                    <span style={{
                      fontFamily: 'ui-monospace, monospace', fontSize: '0.68rem', color: '#3A4357',
                      flexShrink: 0, width: 155, paddingTop: 2,
                    }}>
                      {e.timestamp}
                    </span>

                    {/* Activity */}
                    <span style={{
                      fontSize: '0.75rem', color: '#64748B', lineHeight: 1.5,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {e.activity || e.filename || e.url || e.to_addrs || '—'}
                    </span>
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      </Panel>
    </motion.div>
  );
}
