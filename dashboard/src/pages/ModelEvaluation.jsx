import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

/* ═══════════════════════════════════════════════════════════════════════
   XGBOOST EVALUATION DATA — From held-out test set evaluation
   ═══════════════════════════════════════════════════════════════════════ */

const TEST_METRICS = [
  { key: 'accuracy',    label: 'Accuracy',              value: 0.9950, description: 'Overall correct classifications' },
  { key: 'precision',   label: 'Precision',             value: 0.9333, description: 'Of all flagged users, 93.3% are actual insiders' },
  { key: 'recall',      label: 'Recall / Sensitivity',  value: 1.0000, description: '100% of insiders are detected on the holdout set' },
  { key: 'specificity', label: 'Specificity',           value: 0.9946, description: '99.46% of normal users are correctly ignored' },
  { key: 'f1',          label: 'F1-Score',              value: 0.9655, description: 'Harmonic mean of precision and recall' },
  { key: 'macro_prec',  label: 'Macro Precision',       value: 0.9667, description: 'Class-averaged precision across insider + normal' },
  { key: 'macro_rec',   label: 'Macro Recall',          value: 0.9973, description: 'Class-averaged recall across insider + normal' },
  { key: 'roc_auc',     label: 'ROC-AUC',              value: 0.9996, description: 'Area under the ROC curve — near perfect discrimination' },
  { key: 'pr_auc',      label: 'PR-AUC',               value: 0.9952, description: 'Precision-Recall AUC — critical for imbalanced data' },
  { key: 'confidence',  label: 'Confidence Score',      value: 0.9713, description: 'Avg probability for positive classifications — highly confident' },
];

const OVERFIT_METRICS = [
  { key: 'auc_gap',   label: 'Train-Val AUC Gap',    value: 0.0004, maxVal: 0.1,  description: 'Incredibly small gap → model generalizes remarkably well' },
  { key: 'ece',        label: 'ECE (Calibration Error)', value: 0.0095, maxVal: 0.1, description: '90% confidence ≈ 90% true probability — outstanding calibration' },
  { key: 'val_std',    label: 'Val AUC Stability STD', value: 0.0032, maxVal: 0.05, description: 'Consistent performance across all 5 folds' },
];


/* ═══════════════════════════════════════════════════════════════════════
   ANIMATED NUMBER COUNTER
   ═══════════════════════════════════════════════════════════════════════ */
function AnimatedNumber({ value, decimals = 4, suffix = '', delay = 0 }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    const timeout = setTimeout(() => {
      let start = 0;
      const duration = 1200;
      const startTime = performance.now();
      const animate = (now) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        setDisplay(eased * value);
        if (progress < 1) requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
    }, delay);
    return () => clearTimeout(timeout);
  }, [value, delay]);

  return <span ref={ref}>{display.toFixed(decimals)}{suffix}</span>;
}


/* ═══════════════════════════════════════════════════════════════════════
   CIRCULAR GAUGE
   ═══════════════════════════════════════════════════════════════════════ */
function CircularGauge({ value, size = 120, strokeWidth = 8, color, delay = 0 }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      {/* Track */}
      <circle cx={size/2} cy={size/2} r={radius}
        fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth={strokeWidth} />
      {/* Value */}
      <motion.circle
        cx={size/2} cy={size/2} r={radius}
        fill="none" stroke={color} strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: circumference * (1 - value) }}
        transition={{ delay, duration: 1.5, ease: [0.16, 1, 0.3, 1] }}
        style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
      />
    </svg>
  );
}


/* ═══════════════════════════════════════════════════════════════════════
   RADAR CHART (Pure SVG)
   ═══════════════════════════════════════════════════════════════════════ */
function RadarChart({ metrics, size = 320 }) {
  const cx = size / 2, cy = size / 2, radius = size * 0.38;
  const n = metrics.length;
  const angleStep = (2 * Math.PI) / n;

  const getPoint = (i, val) => {
    const angle = i * angleStep - Math.PI / 2;
    return {
      x: cx + radius * val * Math.cos(angle),
      y: cy + radius * val * Math.sin(angle),
    };
  };

  // Grid rings
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Data polygon
  const dataPoints = metrics.map((m, i) => getPoint(i, m.value));
  const pathD = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Grid rings */}
      {rings.map(r => (
        <polygon
          key={r}
          points={metrics.map((_, i) => { const p = getPoint(i, r); return `${p.x},${p.y}`; }).join(' ')}
          fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1"
        />
      ))}
      {/* Axis lines */}
      {metrics.map((_, i) => {
        const p = getPoint(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.03)" strokeWidth="1" />;
      })}
      {/* Data fill */}
      <motion.polygon
        points={dataPoints.map(p => `${p.x},${p.y}`).join(' ')}
        fill="rgba(99,135,241,0.08)"
        stroke="#6387F1"
        strokeWidth="2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.8 }}
      />
      {/* Data dots */}
      {dataPoints.map((p, i) => (
        <motion.circle
          key={i} cx={p.x} cy={p.y} r="4"
          fill="#6387F1" stroke="#06080f" strokeWidth="2"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.6 + i * 0.08, type: 'spring', stiffness: 300 }}
          style={{ filter: 'drop-shadow(0 0 4px rgba(99,135,241,0.4))' }}
        />
      ))}
      {/* Labels */}
      {metrics.map((m, i) => {
        const labelPoint = getPoint(i, 1.18);
        return (
          <text
            key={m.label}
            x={labelPoint.x} y={labelPoint.y}
            textAnchor="middle" dominantBaseline="middle"
            style={{ fontSize: '0.55rem', fontWeight: 600, fill: '#526077' }}
          >
            {m.label}
          </text>
        );
      })}
    </svg>
  );
}


/* ═══════════════════════════════════════════════════════════════════════
   FRAMER VARIANTS
   ═══════════════════════════════════════════════════════════════════════ */
const containerVariants = { hidden: {}, show: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } } };
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};


/* ═══════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */
export default function ModelEvaluation() {
  // Radar subset
  const radarMetrics = TEST_METRICS.filter(m =>
    ['accuracy', 'precision', 'recall', 'specificity', 'f1', 'roc_auc'].includes(m.key)
  );

  return (
    <motion.div
      variants={containerVariants} initial="hidden" animate="show"
      style={{ maxWidth: 1360, margin: '0 auto' }}
    >
      {/* ═══════════════════════════════════════════════════════════════
          HEADER
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div variants={itemVariants} style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <h1 style={{
            fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.03em',
            background: 'linear-gradient(135deg, #E2E8F0 30%, #94A3B8)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            Model Evaluation
          </h1>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 14px', borderRadius: 20,
            background: 'rgba(99,135,241,0.06)',
            border: '1px solid rgba(99,135,241,0.12)',
          }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6387F1" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
            </svg>
            <span style={{ fontSize: '0.6rem', fontWeight: 600, color: '#6387F1', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              XGBoost + SHAP
            </span>
          </div>
        </div>
        <p style={{ fontSize: '0.78rem', color: '#526077', fontWeight: 500, maxWidth: 600 }}>
          Held-out test set evaluation — 5-fold stratified cross-validation with hybrid sampling
        </p>
      </motion.div>


      {/* ═══════════════════════════════════════════════════════════════
          HERO GAUGES — Top 4 metrics
          ═══════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {[
          { label: 'Accuracy', value: 0.9950, color: '#6387F1' },
          { label: 'Recall', value: 1.0000, color: '#4ADE80' },
          { label: 'F1-Score', value: 0.9655, color: '#A78BFA' },
          { label: 'ROC-AUC', value: 0.9996, color: '#38BDF8' },
        ].map((g, i) => (
          <motion.div
            key={g.label}
            variants={itemVariants}
            whileHover={{ scale: 1.02, boxShadow: `0 0 30px ${g.color}15` }}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-default)',
              borderRadius: 20, padding: '28px 20px',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              position: 'relative', overflow: 'hidden',
            }}
          >
            {/* Bottom glow */}
            <div style={{
              position: 'absolute', bottom: 0, left: '15%', right: '15%', height: 2,
              background: `linear-gradient(90deg, transparent, ${g.color}30, transparent)`,
            }} />

            <div style={{ position: 'relative', marginBottom: 16 }}>
              <CircularGauge value={g.value} size={100} strokeWidth={6} color={g.color} delay={0.3 + i * 0.15} />
              <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontSize: '1.4rem', fontWeight: 800, color: g.color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                  <AnimatedNumber value={g.value * 100} decimals={1} delay={300 + i * 150} />
                </span>
                <span style={{ fontSize: '0.5rem', fontWeight: 700, color: '#3A4357' }}>%</span>
              </div>
            </div>

            <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {g.label}
            </span>
          </motion.div>
        ))}
      </div>


      {/* ═══════════════════════════════════════════════════════════════
          RADAR + FULL METRICS TABLE
          ═══════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 20, marginBottom: 24 }}>
        {/* Radar Chart */}
        <motion.div
          variants={itemVariants}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 20, padding: '20px 12px',
            display: 'flex', flexDirection: 'column', alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, alignSelf: 'flex-start', paddingLeft: 12 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#526077" strokeWidth="2" strokeLinecap="round">
              <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
            </svg>
            <span style={{ fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
              Performance Radar
            </span>
          </div>
          <RadarChart metrics={radarMetrics} size={300} />
        </motion.div>

        {/* Full Metrics Table */}
        <motion.div
          variants={itemVariants}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 20, overflow: 'hidden',
          }}
        >
          {/* Scanning line */}
          <motion.div
            style={{
              position: 'relative', top: 0, left: 0, right: 0, height: 1,
              background: 'linear-gradient(90deg, transparent, rgba(99,135,241,0.3), transparent)',
            }}
            animate={{ x: ['-100%', '100%'] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'linear' }}
          />

          <div style={{ padding: '18px 24px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#526077" strokeWidth="2" strokeLinecap="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            <span style={{ fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
              Test Metrics
            </span>
          </div>

          <div style={{ padding: '12px 0' }}>
            {TEST_METRICS.map((m, i) => {
              const pct = m.value * 100;
              const color = pct >= 99 ? '#4ADE80' : pct >= 95 ? '#6387F1' : pct >= 90 ? '#A78BFA' : '#FACC15';
              return (
                <motion.div
                  key={m.key}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 24px',
                    borderBottom: '1px solid rgba(255,255,255,0.02)',
                    transition: 'background 0.2s ease',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.015)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  {/* Metric name */}
                  <span style={{ flex: '0 0 180px', fontSize: '0.75rem', fontWeight: 600, color: '#94A3B8' }}>
                    {m.label}
                  </span>

                  {/* Bar */}
                  <div style={{ flex: 1, height: 5, borderRadius: 4, background: 'rgba(255,255,255,0.03)', overflow: 'hidden' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ delay: 0.5 + i * 0.08, duration: 1, ease: [0.16, 1, 0.3, 1] }}
                      style={{
                        height: '100%', borderRadius: 4,
                        background: `linear-gradient(90deg, ${color}80, ${color})`,
                        boxShadow: `0 0 8px ${color}30`,
                      }}
                    />
                  </div>

                  {/* Value */}
                  <span style={{
                    flex: '0 0 80px', textAlign: 'right',
                    fontSize: '0.82rem', fontWeight: 800, color,
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    <AnimatedNumber value={m.value * 100} decimals={2} suffix="%" delay={500 + i * 80} />
                  </span>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </div>


      {/* ═══════════════════════════════════════════════════════════════
          OVERFITTING ANALYSIS
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemVariants}
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 20, padding: 28,
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" strokeWidth="2" strokeLinecap="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
            Overfitting &amp; Calibration Analysis
          </span>
          <div style={{
            marginLeft: 'auto', padding: '3px 12px', borderRadius: 8,
            background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.12)',
            fontSize: '0.55rem', fontWeight: 700, color: '#4ADE80',
            textTransform: 'uppercase', letterSpacing: '0.08em',
          }}>
            ✓ NO OVERFITTING DETECTED
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {OVERFIT_METRICS.map((m, i) => {
            const barPct = Math.min((m.value / m.maxVal) * 100, 100);
            // For overfitting metrics, LOWER is better — so the color is green for low values
            const color = m.value < 0.01 ? '#4ADE80' : m.value < 0.05 ? '#FACC15' : '#F87171';
            return (
              <motion.div
                key={m.key}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + i * 0.12 }}
                style={{
                  padding: 20, borderRadius: 14,
                  background: `${color}04`,
                  border: `1px solid ${color}10`,
                }}
              >
                <span style={{ fontSize: '0.58rem', fontWeight: 700, color: '#3A4357', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 12 }}>
                  {m.label}
                </span>

                {/* Big value */}
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 12 }}>
                  <span style={{ fontSize: '1.8rem', fontWeight: 800, color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                    <AnimatedNumber value={m.value * 100} decimals={2} suffix="%" delay={600 + i * 120} />
                  </span>
                </div>

                {/* Progress bar (inverted — green when LOW) */}
                <div style={{ width: '100%', height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.03)', overflow: 'hidden', marginBottom: 10 }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${barPct}%` }}
                    transition={{ delay: 0.8 + i * 0.12, duration: 1, ease: [0.16, 1, 0.3, 1] }}
                    style={{
                      height: '100%', borderRadius: 4,
                      background: `linear-gradient(90deg, ${color}80, ${color})`,
                    }}
                  />
                </div>

                {/* Description */}
                <p style={{ fontSize: '0.62rem', color: '#526077', fontWeight: 500, lineHeight: 1.5 }}>
                  {m.description}
                </p>
              </motion.div>
            );
          })}
        </div>
      </motion.div>


      {/* ═══════════════════════════════════════════════════════════════
          CONFUSION MATRIX
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemVariants}
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 20, padding: 28,
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#526077" strokeWidth="2" strokeLinecap="round">
            <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
          </svg>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#526077' }}>
            Confusion Matrix — Holdout Test Set
          </span>
          <div style={{
            marginLeft: 'auto', padding: '3px 12px', borderRadius: 8,
            background: 'rgba(99,135,241,0.06)', border: '1px solid rgba(99,135,241,0.12)',
            fontSize: '0.55rem', fontWeight: 700, color: '#6387F1',
            textTransform: 'uppercase', letterSpacing: '0.08em',
          }}>
            200 Test Samples
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: 60, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Matrix Grid */}
          <div>
            {/* Column headers */}
            <div style={{ display: 'flex', marginBottom: 6, paddingLeft: 90 }}>
              <span style={{ width: 130, textAlign: 'center', fontSize: '0.6rem', fontWeight: 700, color: '#526077', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Predicted Normal
              </span>
              <span style={{ width: 130, textAlign: 'center', fontSize: '0.6rem', fontWeight: 700, color: '#526077', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Predicted Insider
              </span>
            </div>

            {/* Row 1: Actual Normal */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ width: 90, textAlign: 'right', paddingRight: 14, fontSize: '0.6rem', fontWeight: 700, color: '#526077', textTransform: 'uppercase', letterSpacing: '0.05em', lineHeight: 1.3 }}>
                Actual<br/>Normal
              </span>
              {/* TN = 185 */}
              <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.4, type: 'spring', stiffness: 200, damping: 15 }}
                whileHover={{ scale: 1.05 }}
                style={{
                  width: 130, height: 100, borderRadius: 14, marginRight: 6,
                  background: 'linear-gradient(145deg, rgba(74,222,128,0.06), rgba(74,222,128,0.02))',
                  border: '1px solid rgba(74,222,128,0.15)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: 'default', position: 'relative', overflow: 'hidden',
                }}
              >
                <div style={{ position: 'absolute', bottom: 0, left: '10%', right: '10%', height: 2, background: 'linear-gradient(90deg, transparent, rgba(74,222,128,0.3), transparent)' }} />
                <span style={{ fontSize: '2rem', fontWeight: 800, color: '#4ADE80', lineHeight: 1 }}>185</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 700, color: '#3A4357', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>True Neg</span>
                <span style={{ fontSize: '0.55rem', fontWeight: 600, color: '#4ADE80', marginTop: 2, opacity: 0.7 }}>92.50%</span>
              </motion.div>
              {/* FP = 1 */}
              <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.5, type: 'spring', stiffness: 200, damping: 15 }}
                whileHover={{ scale: 1.05 }}
                style={{
                  width: 130, height: 100, borderRadius: 14,
                  background: 'linear-gradient(145deg, rgba(248,113,113,0.06), rgba(248,113,113,0.02))',
                  border: '1px solid rgba(248,113,113,0.15)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: 'default', position: 'relative', overflow: 'hidden',
                }}
              >
                <span style={{ fontSize: '2rem', fontWeight: 800, color: '#F87171', lineHeight: 1 }}>1</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 700, color: '#3A4357', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>False Pos</span>
                <span style={{ fontSize: '0.55rem', fontWeight: 600, color: '#F87171', marginTop: 2, opacity: 0.7 }}>0.50%</span>
              </motion.div>
            </div>

            {/* Row 2: Actual Insider */}
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ width: 90, textAlign: 'right', paddingRight: 14, fontSize: '0.6rem', fontWeight: 700, color: '#526077', textTransform: 'uppercase', letterSpacing: '0.05em', lineHeight: 1.3 }}>
                Actual<br/>Insider
              </span>
              {/* FN = 0 */}
              <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.6, type: 'spring', stiffness: 200, damping: 15 }}
                whileHover={{ scale: 1.05 }}
                style={{
                  width: 130, height: 100, borderRadius: 14, marginRight: 6,
                  background: 'linear-gradient(145deg, rgba(74,222,128,0.12), rgba(74,222,128,0.04))',
                  border: '1px solid rgba(74,222,128,0.25)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: 'default', position: 'relative', overflow: 'hidden',
                  boxShadow: '0 0 20px rgba(74,222,128,0.06)',
                }}
              >
                <div style={{ position: 'absolute', bottom: 0, left: '10%', right: '10%', height: 2, background: 'linear-gradient(90deg, transparent, rgba(74,222,128,0.4), transparent)' }} />
                <span style={{ fontSize: '2rem', fontWeight: 800, color: '#4ADE80', lineHeight: 1 }}>0</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 700, color: '#3A4357', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>False Neg</span>
                <span style={{ fontSize: '0.55rem', fontWeight: 600, color: '#4ADE80', marginTop: 2, opacity: 0.7 }}>0.00%</span>
              </motion.div>
              {/* TP = 14 */}
              <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.7, type: 'spring', stiffness: 200, damping: 15 }}
                whileHover={{ scale: 1.05 }}
                style={{
                  width: 130, height: 100, borderRadius: 14,
                  background: 'linear-gradient(145deg, rgba(99,135,241,0.08), rgba(99,135,241,0.02))',
                  border: '1px solid rgba(99,135,241,0.2)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: 'default', position: 'relative', overflow: 'hidden',
                }}
              >
                <div style={{ position: 'absolute', bottom: 0, left: '10%', right: '10%', height: 2, background: 'linear-gradient(90deg, transparent, rgba(99,135,241,0.3), transparent)' }} />
                <span style={{ fontSize: '2rem', fontWeight: 800, color: '#6387F1', lineHeight: 1 }}>14</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 700, color: '#3A4357', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>True Pos</span>
                <span style={{ fontSize: '0.55rem', fontWeight: 600, color: '#6387F1', marginTop: 2, opacity: 0.7 }}>7.00%</span>
              </motion.div>
            </div>
          </div>

          {/* Annotations */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.8 }}
            style={{ maxWidth: 280 }}
          >
            {[
              { color: '#4ADE80', title: 'Zero False Negatives', desc: 'Every single insider was correctly flagged — no threats were missed.', icon: '✓' },
              { color: '#6387F1', title: 'Only 1 False Positive', desc: 'Out of 186 normal users, only 1 was incorrectly flagged — 99.46% specificity.', icon: '◎' },
              { color: '#A78BFA', title: '99.5% Accuracy', desc: '199 out of 200 test samples classified correctly.', icon: '★' },
            ].map((note, i) => (
              <motion.div
                key={note.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.9 + i * 0.12 }}
                style={{
                  padding: '12px 16px', borderRadius: 12, marginBottom: 8,
                  background: `${note.color}05`,
                  border: `1px solid ${note.color}10`,
                  display: 'flex', gap: 12, alignItems: 'flex-start',
                }}
              >
                <span style={{
                  width: 24, height: 24, borderRadius: 8, flexShrink: 0,
                  background: `${note.color}10`, border: `1px solid ${note.color}18`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.7rem', color: note.color,
                }}>
                  {note.icon}
                </span>
                <div>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#E2E8F0', display: 'block', marginBottom: 2 }}>{note.title}</span>
                  <span style={{ fontSize: '0.6rem', fontWeight: 500, color: '#526077', lineHeight: 1.5 }}>{note.desc}</span>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </motion.div>

      {/* ═══════════════════════════════════════════════════════════════
          INTERPRETATION INSIGHTS
          ═══════════════════════════════════════════════════════════════ */}
      <motion.div
        variants={itemVariants}
        style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16,
          marginBottom: 24,
        }}
      >
        {[
          {
            icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>,
            title: 'Perfect Recall',
            text: 'The model catches every single insider threat in the holdout test set — zero false negatives.',
            color: '#4ADE80',
          },
          {
            icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
            title: 'Outstanding Calibration',
            text: 'ECE of 0.0095 means a 90% confidence score accurately reflects ~90% actual probability.',
            color: '#6387F1',
          },
          {
            icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
            title: 'Robust Generalization',
            text: 'Train-Val AUC gap of 0.0004 — the model performs near-identically on unseen data.',
            color: '#A78BFA',
          },
        ].map((card, i) => (
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 + i * 0.1 }}
            whileHover={{ scale: 1.01, boxShadow: `0 0 24px ${card.color}10` }}
            style={{
              padding: 22, borderRadius: 16,
              background: 'var(--bg-card)',
              border: `1px solid ${card.color}12`,
              transition: 'border-color 0.3s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 10,
                background: `${card.color}10`,
                border: `1px solid ${card.color}18`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: card.color,
              }}>
                {card.icon}
              </div>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#E2E8F0' }}>{card.title}</span>
            </div>
            <p style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 500, lineHeight: 1.6 }}>
              {card.text}
            </p>
          </motion.div>
        ))}
      </motion.div>

      <div style={{ height: 40 }} />
    </motion.div>
  );
}
