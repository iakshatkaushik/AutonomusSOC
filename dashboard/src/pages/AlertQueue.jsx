import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchAlerts } from '../api';

const SEVERITIES = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const STATUSES = ['ALL', 'open', 'acknowledged', 'dismissed', 'escalated'];

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

  return (
    <div style={{ maxWidth: 1320, margin: '0 auto' }}>
      {/* Header */}
      <div className="animate-fade-up" style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Alert Queue</h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: 4 }}>
          {total.toLocaleString()} alerts detected across all severity levels
        </p>
      </div>

      {/* Filters */}
      <div className="animate-fade-up" style={{ display: 'flex', flexWrap: 'wrap', gap: 24, marginBottom: 24, animationDelay: '80ms' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Severity</span>
          <div style={{ display: 'flex', gap: 6 }}>
            {SEVERITIES.map(s => (
              <button key={s} onClick={() => { setSevFilter(s); setPage(0); }}
                className={`pill ${sevFilter === s ? 'pill-active' : ''}`}>
                {s}
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Status</span>
          <div style={{ display: 'flex', gap: 6 }}>
            {STATUSES.map(s => (
              <button key={s} onClick={() => { setStatusFilter(s); setPage(0); }}
                className={`pill ${statusFilter === s ? 'pill-active' : ''}`}
                style={{ textTransform: 'capitalize' }}>
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card animate-fade-up" style={{ animationDelay: '160ms', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0' }}>
            <div className="spinner" />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>User</th>
                  <th>Alert Type</th>
                  <th>Severity</th>
                  <th>Risk Score</th>
                  <th>Status</th>
                  <th>Investigation</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a, i) => (
                  <tr
                    key={a.id}
                    className="animate-slide-right"
                    style={{ animationDelay: `${i * 20}ms` }}
                    onClick={() => navigate(`/alerts/${a.id}`)}
                  >
                    <td>
                      <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>#{a.id}</span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{a.user_id}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{a.alert_type.replace(/_/g, ' ')}</td>
                    <td><span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div className="risk-bar-track">
                          <div className="risk-bar-fill" style={{
                            width: `${a.risk_score}%`,
                            background: a.risk_score >= 90 ? 'var(--critical)' : a.risk_score >= 70 ? 'var(--high)' : a.risk_score >= 40 ? 'var(--medium)' : 'var(--low)',
                          }} />
                        </div>
                        <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', fontWeight: 600, width: 36, textAlign: 'right' }}>
                          {a.risk_score.toFixed(1)}
                        </span>
                      </div>
                    </td>
                    <td><span className={`badge badge-status-${a.status}`}>{a.status}</span></td>
                    <td>
                      {a.has_investigation ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M20 6L9 17l-5-5"/></svg>
                          Done
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Pending</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="animate-fade-up" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: 20 }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="btn btn-outline" style={{ padding: '8px 18px', fontSize: '0.75rem' }}>
            ← Previous
          </button>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            Page {page + 1} of {totalPages}
          </span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="btn btn-outline" style={{ padding: '8px 18px', fontSize: '0.75rem' }}>
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
