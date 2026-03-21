import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { fetchAlert, fetchUserLogs, triggerInvestigation, updateAlertStatus } from '../api';

/* ── Risk Gauge SVG ─────────────────────────────────────────────────── */
function RiskGauge({ score }) {
  const color = score >= 90 ? '#f87171' : score >= 70 ? '#fb923c' : score >= 40 ? '#facc15' : '#4ade80';
  const r = 56;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <svg width="160" height="160" viewBox="0 0 130 130">
        <circle cx="65" cy="65" r={r} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="10" />
        <circle cx="65" cy="65" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 65 65)"
          style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16, 1, 0.3, 1)', filter: `drop-shadow(0 0 10px ${color}60)` }}
        />
        <text x="65" y="60" textAnchor="middle" fill={color} fontSize="32" fontWeight="800" fontFamily="Inter">{score.toFixed(0)}</text>
        <text x="65" y="78" textAnchor="middle" fill="#526077" fontSize="11" fontWeight="500">/100</text>
      </svg>
      <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-muted)' }}>
        Risk Score
      </span>
    </div>
  );
}

/* ── Card Section ───────────────────────────────────────────────────── */
function Section({ title, icon, children, delay = 0 }) {
  return (
    <div className="card animate-fade-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="card-inner">
        <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '1rem' }}>{icon}</span>{title}
        </p>
        {children}
      </div>
    </div>
  );
}

export default function AlertInvestigation() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [investigateError, setInvestigateError] = useState(null);

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
        const msg = err?.response?.data?.detail || err?.message || 'Investigation failed. Please try again.';
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
  if (!alert) return <p style={{ color: 'var(--text-muted)' }}>Alert not found.</p>;

  const report = alert.investigation_report;
  const factors = alert.contributing_factors || [];
  const shapData = factors.map((f, i) => {
    if (typeof f === 'string') return { name: f.substring(0, 30), value: 1 };
    return { name: (f.factor || f.feature || `Factor ${i}`).substring(0, 30), value: Math.abs(parseFloat(f.deviation || f.shap_value || 1)) };
  }).slice(0, 7);

  const timeline = [];
  if (logs) {
    (logs.logon_events || []).forEach(e => timeline.push({ ...e, type: 'LOGON' }));
    (logs.file_events || []).forEach(e => timeline.push({ ...e, type: 'FILE' }));
    (logs.email_events || []).forEach(e => timeline.push({ ...e, type: 'EMAIL' }));
    (logs.http_events || []).forEach(e => timeline.push({ ...e, type: 'HTTP' }));
  }
  timeline.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));

  const TYPE_COLORS = { LOGON: { bg: 'rgba(99,135,241,0.1)', fg: '#93b4fd' }, FILE: { bg: 'rgba(251,146,60,0.1)', fg: '#fdba74' }, EMAIL: { bg: 'rgba(52,211,153,0.1)', fg: '#6ee7b7' }, HTTP: { bg: 'rgba(167,139,250,0.1)', fg: '#c4b5fd' } };

  return (
    <div style={{ maxWidth: 1320, margin: '0 auto' }}>
      {/* ── Back + Header ── */}
      <div className="animate-fade-up" style={{ marginBottom: 28 }}>
        <button onClick={() => navigate(-1)}
          style={{
            background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.8rem',
            cursor: 'pointer', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6,
            transition: 'color 0.15s ease',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
          Back to alerts
        </button>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontSize: '1.65rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
              Alert #{alert.id} — <span style={{ color: 'var(--accent-blue)' }}>{alert.user_id}</span>
            </h1>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4 }}>
              {alert.alert_type.replace(/_/g, ' ')} · {alert.created_at}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span className={`badge badge-${alert.severity.toLowerCase()}`}>{alert.severity}</span>
            <span className={`badge badge-status-${alert.status}`}>{alert.status}</span>
          </div>
        </div>
      </div>

      {/* ── Top Row: Gauge + Factors + Actions ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Risk Assessment */}
        <Section title="Risk Assessment" icon="🎯" delay={80}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, padding: '8px 0' }}>
            <RiskGauge score={alert.risk_score} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 20px', width: '100%' }}>
              {[
                { l: 'Type', v: alert.alert_type.replace(/_/g, ' ') },
                { l: 'Score', v: alert.risk_score.toFixed(1) },
                { l: 'Severity', v: alert.severity },
                { l: 'Status', v: alert.status },
              ].map(({ l, v }) => (
                <div key={l}>
                  <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 2 }}>{l}</p>
                  <p style={{ fontSize: '0.82rem', fontWeight: 600, textTransform: 'capitalize' }}>{v}</p>
                </div>
              ))}
            </div>
          </div>
        </Section>

        {/* Contributing Factors */}
        <Section title="Contributing Factors" icon="📊" delay={160}>
          {shapData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={shapData} layout="vertical" barSize={16} margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                <XAxis type="number" tick={{ fill: '#526077', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#1c2333', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, fontSize: 11, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {shapData.map((_, i) => <Cell key={i} fill={i < 3 ? '#f87171' : i < 5 ? '#fb923c' : '#6387f1'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', padding: '40px 0', textAlign: 'center' }}>No contributing factor data available.</p>
          )}
        </Section>

        {/* Actions */}
        <Section title="Actions" icon="⚡" delay={240}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <button onClick={handleInvestigate} disabled={investigating} className="btn btn-primary" style={{ width: '100%', padding: '12px 20px' }}>
              {investigating ? (
                <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} /> Running Agent...</>
              ) : '🤖 Investigate with AI'}
            </button>
            {investigateError && (
              <div style={{
                padding: '10px 14px', borderRadius: 8, fontSize: '0.72rem', lineHeight: 1.5,
                background: 'var(--critical-bg)', border: '1px solid var(--critical-border)',
                color: '#fca5a5', wordBreak: 'break-word',
              }}>
                ⚠️ {investigateError}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[
                { status: 'acknowledged', label: '✓ Acknowledge', color: 'var(--accent-purple)', bg: 'rgba(167,139,250,0.08)', border: 'rgba(167,139,250,0.18)' },
                { status: 'escalated', label: '⬆ Escalate', color: 'var(--critical)', bg: 'var(--critical-bg)', border: 'var(--critical-border)' },
                { status: 'dismissed', label: '✕ Dismiss', color: 'var(--text-muted)', bg: 'rgba(82,96,119,0.08)', border: 'rgba(82,96,119,0.18)' },
                { status: 'open', label: '↺ Re-open', color: 'var(--accent-blue)', bg: 'rgba(99,135,241,0.08)', border: 'rgba(99,135,241,0.18)' },
              ].map(b => (
                <button key={b.status} onClick={() => handleStatus(b.status)} disabled={statusUpdating}
                  style={{
                    padding: '10px 8px', borderRadius: 10, fontSize: '0.72rem', fontWeight: 600,
                    cursor: 'pointer', transition: 'all 0.2s ease',
                    background: b.bg, color: b.color, border: `1px solid ${b.border}`,
                  }}
                  onMouseEnter={e => { e.currentTarget.style.opacity = '0.8'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                  onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)'; }}
                >
                  {b.label}
                </button>
              ))}
            </div>
          </div>
        </Section>
      </div>

      {/* ── Investigation Report ── */}
      {report ? (
        <div className="card animate-fade-up" style={{ animationDelay: '320ms', marginBottom: 24 }}>
          <div className="card-inner">
            <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '1rem' }}>🤖</span>AI Investigation Report
            </p>

            {/* Summary */}
            <div style={{
              padding: '18px 22px', borderRadius: 12, marginBottom: 20,
              background: 'linear-gradient(135deg, rgba(99,135,241,0.06), rgba(139,92,246,0.04))',
              border: '1px solid rgba(99,135,241,0.12)',
            }}>
              <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--accent-blue)', marginBottom: 6 }}>Summary</p>
              <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--text-primary)' }}>{report.summary}</p>
            </div>

            {/* Key Findings Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 22 }}>
              {[
                { label: 'Threat Type', value: report.threat_scenario?.replace(/_/g, ' ') || 'Unknown' },
                { label: 'Confidence', value: `${((report.confidence || 0) * 100).toFixed(0)}%` },
                { label: 'Recommended', value: report.recommended_action?.replace(/_/g, ' ') || 'Monitor' },
                { label: 'LLM Model', value: report.llm_model || 'N/A' },
              ].map(item => (
                <div key={item.label} style={{ padding: '14px 16px', borderRadius: 10, background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
                  <p style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4 }}>{item.label}</p>
                  <p style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'capitalize' }}>{item.value}</p>
                </div>
              ))}
            </div>

            {/* Reasoning */}
            {report.reasoning && (
              <div style={{ marginBottom: 22 }}>
                <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>Reasoning</p>
                <div style={{
                  padding: '18px 20px', borderRadius: 12, background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                  fontSize: '0.82rem', lineHeight: 1.8, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap',
                  maxHeight: 300, overflowY: 'auto',
                }}>
                  {report.reasoning}
                </div>
              </div>
            )}

            {/* Evidence Chain */}
            {report.evidence_chain?.length > 0 && (
              <div style={{ marginBottom: 22 }}>
                <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>Evidence Chain</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {report.evidence_chain.map((e, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 12,
                      padding: '10px 16px', borderRadius: 10,
                      background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                      fontSize: '0.8rem', color: 'var(--text-secondary)',
                    }}>
                      <span style={{ fontFamily: 'monospace', color: 'var(--accent-cyan)', fontWeight: 700, flexShrink: 0, fontSize: '0.72rem' }}>#{i + 1}</span>
                      <span>{typeof e === 'string' ? e : JSON.stringify(e)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended Actions + Correlated Users */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {report.recommended_actions_detail?.length > 0 && (
                <div>
                  <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>Recommended Actions</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {report.recommended_actions_detail.map((a, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                        <span style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>→</span>
                        <span>{a}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {report.correlated_users?.length > 0 && (
                <div>
                  <p style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>Correlated Users</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {report.correlated_users.map((u, i) => (
                      <span key={i} style={{
                        padding: '5px 14px', borderRadius: 8, fontSize: '0.78rem', fontWeight: 600,
                        background: 'rgba(167,139,250,0.08)', color: 'var(--accent-purple)', border: '1px solid rgba(167,139,250,0.18)',
                      }}>
                        {u}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="card animate-fade-up" style={{ animationDelay: '320ms', marginBottom: 24 }}>
          <div style={{ padding: '48px 24px', textAlign: 'center' }}>
            <p style={{ fontSize: '2rem', marginBottom: 12 }}>🤖</p>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: 4 }}>No investigation report yet</p>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 20 }}>Click the button below to run the AI agent investigation</p>
            <button onClick={handleInvestigate} disabled={investigating} className="btn btn-primary" style={{ padding: '12px 32px' }}>
              {investigating ? <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} /> Running Agent...</> : '🤖 Run AI Investigation'}
            </button>
            {investigateError && (
              <div style={{
                padding: '12px 16px', borderRadius: 10, fontSize: '0.78rem', lineHeight: 1.6, marginTop: 12,
                background: 'var(--critical-bg)', border: '1px solid var(--critical-border)',
                color: '#fca5a5', wordBreak: 'break-word', textAlign: 'left',
              }}>
                ⚠️ {investigateError}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Raw Event Timeline ── */}
      <Section title={`Raw Event Timeline · ${timeline.length} events`} icon="📋" delay={400}>
        <div style={{ maxHeight: 420, overflowY: 'auto' }}>
          {timeline.length === 0 ? (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>No log events found.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {timeline.slice(0, 80).map((e, i) => {
                const tc = TYPE_COLORS[e.type] || TYPE_COLORS.LOGON;
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '8px 14px', borderRadius: 8,
                    transition: 'background 0.1s ease',
                  }}
                    onMouseEnter={ev => ev.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}
                  >
                    <span style={{
                      padding: '3px 10px', borderRadius: 6, fontSize: '0.62rem', fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: '0.04em',
                      background: tc.bg, color: tc.fg, flexShrink: 0, minWidth: 52, textAlign: 'center',
                    }}>
                      {e.type}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: 'var(--text-muted)', flexShrink: 0, width: 150 }}>
                      {e.timestamp}
                    </span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.activity || e.filename || e.url || e.to_addrs || '—'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Section>
    </div>
  );
}
