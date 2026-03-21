import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 2 min (investigation can take time)
});

export const fetchOverview = () => api.get('/dashboard/overview').then(r => r.data);

export const fetchAlerts = (params = {}) => api.get('/alerts', { params }).then(r => r.data);
export const fetchAlert = (id) => api.get(`/alerts/${id}`).then(r => r.data);
export const updateAlertStatus = (id, status) => api.patch(`/alerts/${id}/status`, { status }).then(r => r.data);

export const fetchUsers = (params = {}) => api.get('/users', { params }).then(r => r.data);
export const fetchUser = (id) => api.get(`/users/${id}`).then(r => r.data);
export const fetchUserLogs = (id, logType = 'all') => api.get(`/users/${id}/logs`, { params: { log_type: logType } }).then(r => r.data);

export const triggerInvestigation = (alertId) => api.post(`/investigate/${alertId}`).then(r => r.data);
export const fetchReport = (alertId) => api.get(`/reports/${alertId}`).then(r => r.data);

export default api;
