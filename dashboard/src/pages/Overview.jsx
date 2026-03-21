import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { fetchOverview } from '../api';

const SEV_COLORS = { CRITICAL: '#f87171', HIGH: '#fb923c', MEDIUM: '#facc15', LOW: '#4ade80' };
const SEV_ICONS = { CRITICAL: '🔴', HIGH: '🟠', MEDIUM: '🟡', LOW: '🟢' };

export default function Overview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchOverview().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ height: '60vh' }}>
        <div className="spinner" />
      </div>
    );
  }
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>Failed to load data.</p>;

  const sevData = Object.entries(data.severity_counts).map(([name, value]) => ({ name, value }));

  return (
    <div style={{ maxWidth: 1320, margin: '0 auto' }}>
      {/* Header */}
      <div className="animate-fade-up" style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
          Dashboard Overview
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: 4 }}>
          Real-time insider threat monitoring · {data.total_users.toLocaleString()} users tracked
        </p>
      </div>

      {/* ── Severity Cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {Object.entries(data.severity_counts).map(([sev, count], i) => (
          <div
            key={sev}
            className="card animate-fade-up"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div className="card-inner" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <p style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 8 }}>
                  {sev}
                </p>
                <p style={{ fontSize: '2.2rem', fontWeight: 800, color: SEV_COLORS[sev], lineHeight: 1 }}>
                  {count}
                </p>
              </div>
              <div
                style={{
                  width: 40, height: 40, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '1.1rem',
                  background: `${SEV_COLORS[sev]}10`,
                  border: `1px solid ${SEV_COLORS[sev]}20`,
                }}
              >
                {SEV_ICONS[sev]}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Stats Row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {[
          { label: 'Total Alerts', value: data.total_alerts, color: 'var(--accent-blue)' },
          { label: 'Open Alerts', value: data.open_alerts, color: 'var(--accent-cyan)' },
          { label: 'Investigated', value: data.total_investigated, color: 'var(--accent-purple)' },
          { label: 'Total Users', value: data.total_users, color: 'var(--accent-emerald)' },
        ].map((stat, i) => (
          <div key={stat.label} className="card animate-fade-up" style={{ animationDelay: `${280 + i * 60}ms` }}>
            <div className="card-inner">
              <p style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 8 }}>
                {stat.label}
              </p>
              <p style={{ fontSize: '1.75rem', fontWeight: 800, color: stat.color, lineHeight: 1 }}>
                {stat.value.toLocaleString()}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* ── Two-Column: Chart + Top Users ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Chart */}
        <div className="card animate-fade-up" style={{ animationDelay: '520ms' }}>
          <div className="card-inner">
            <p className="section-label">Alerts by Severity</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sevData} barSize={40}>
                <XAxis dataKey="name" tick={{ fill: '#526077', fontSize: 11, fontWeight: 600 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#526077', fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                <Tooltip
                  contentStyle={{ background: '#1c2333', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  labelStyle={{ color: '#94a3b8', fontWeight: 600 }}
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {sevData.map(entry => <Cell key={entry.name} fill={SEV_COLORS[entry.name]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Users */}
        <div className="card animate-fade-up" style={{ animationDelay: '580ms' }}>
          <div className="card-inner">
            <p className="section-label">Top 10 Risky Users</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 240, overflowY: 'auto' }}>
              {data.top_risky_users.map((u, i) => (
                <div
                  key={u.user_id}
                  onClick={() => {
                    const a = data.recent_alerts.find(a => a.user_id === u.user_id);
                    navigate(a ? `/alerts/${a.id}` : '/alerts');
                  }}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', borderRadius: 10, cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', width: 24, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {i + 1}.
                    </span>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, fontFamily: "'Inter', monospace" }}>{u.user_id}</span>
                    {u.is_insider && (
                      <span style={{
                        fontSize: '0.6rem', fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                        background: 'var(--critical-bg)', color: 'var(--critical)', border: '1px solid var(--critical-border)',
                        letterSpacing: '0.05em',
                      }}>
                        INSIDER
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div className="risk-bar-track">
                      <div
                        className="risk-bar-fill"
                        style={{
                          width: `${u.risk_score}%`,
                          background: u.risk_score >= 90 ? 'var(--critical)' : u.risk_score >= 70 ? 'var(--high)' : u.risk_score >= 40 ? 'var(--medium)' : 'var(--low)',
                        }}
                      />
                    </div>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text-secondary)', width: 30, textAlign: 'right' }}>
                      {u.risk_score.toFixed(0)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Recent Alerts ── */}
      <div className="card animate-fade-up" style={{ animationDelay: '660ms', overflow: 'hidden' }}>
        <div style={{ padding: '24px 24px 0 24px' }}>
          <p className="section-label">Recent Alerts</p>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>User</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_alerts.slice(0, 10).map((a, i) => (
                <tr
                  key={a.id}
                  className="animate-slide-right"
                  style={{ animationDelay: `${720 + i * 35}ms` }}
                  onClick={() => navigate(`/alerts/${a.id}`)}
                >
                  <td>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>#{a.id}</span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{a.user_id}</td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{a.alert_type.replace(/_/g, ' ')}</td>
                  <td><span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span></td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="risk-bar-track">
                        <div className="risk-bar-fill" style={{
                          width: `${a.risk_score}%`,
                          background: a.risk_score >= 90 ? 'var(--critical)' : a.risk_score >= 70 ? 'var(--high)' : 'var(--medium)',
                        }} />
                      </div>
                      <span style={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 600 }}>{a.risk_score.toFixed(1)}</span>
                    </div>
                  </td>
                  <td><span className={`badge badge-status-${a.status}`}>{a.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
