import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,  // send httpOnly cookie on every request
  headers: { 'Content-Type': 'application/json' },
})

// Handle 401 globally — token expired or invalid
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// Auth
export const authAPI = {
  login: (credentials) => api.post('/auth/login', credentials),
  register: (data) => api.post('/auth/register', data),
  profile: () => api.get('/auth/profile'),
  logout: () => api.post('/auth/logout'),
}

// Scans
export const scansAPI = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/scans/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () => api.get('/scans/'),
  get: (id) => api.get(`/scans/${id}`),
  delete: (id) => api.delete(`/scans/${id}`),
  analyze: (scanId, vulnerabilityIds) =>
    api.post(`/scans/${scanId}/analyze`, { vulnerability_ids: vulnerabilityIds }),
  suppress: (scanId, vulnId) =>
    api.patch(`/scans/${scanId}/vulnerabilities/${vulnId}/suppress`),
  downloadReport: (scanId) =>
    api.get(`/scans/${scanId}/report`, { responseType: 'blob' }),
  exportCSV: (scanId) =>
    api.get(`/scans/${scanId}/export/csv`, { responseType: 'blob' }),
  getLog: (scanId) =>
    api.get(`/scans/${scanId}/log`, { responseType: 'text', transformResponse: [(d) => d] }),
}

// Integrations
export const integrationsAPI = {
  list: () => api.get('/integrations/'),
  create: (data) => api.post('/integrations/', data),
  delete: (id) => api.delete(`/integrations/${id}`),
  trigger: (id, data) => api.post(`/integrations/${id}/trigger`, data),
  listResources: (id) => api.post(`/integrations/${id}/list-resources`),
}

export default api
