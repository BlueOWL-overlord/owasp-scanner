import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, Clock, CheckCircle, XCircle, Loader, AlertTriangle, Upload, Trash2,
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { scansAPI } from '../services/api'

const STATUS_ICON = {
  pending: <Clock size={14} className="text-yellow-400" />,
  running: <Loader size={14} className="text-blue-400 animate-spin" />,
  completed: <CheckCircle size={14} className="text-green-400" />,
  failed: <XCircle size={14} className="text-red-400" />,
}

const SEVERITY_COLORS = {
  Critical: '#ef4444',
  High: '#f97316',
  Medium: '#eab308',
  Low: '#3b82f6',
}

export default function DashboardPage() {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  const fetchScans = async () => {
    try {
      const { data } = await scansAPI.list()
      setScans(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchScans()
    const interval = setInterval(() => {
      const hasActive = scans.some((s) => s.status === 'pending' || s.status === 'running')
      if (hasActive) fetchScans()
    }, 5000)
    return () => clearInterval(interval)
  }, [scans.length])

  const handleDelete = async (id, e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Delete this scan?')) return
    await scansAPI.delete(id)
    setScans((prev) => prev.filter((s) => s.id !== id))
  }

  // Chart data
  const chartData = scans
    .filter((s) => s.status === 'completed')
    .slice(0, 10)
    .map((s) => ({
      name: s.original_filename.slice(0, 12),
      Critical: s.critical_count,
      High: s.high_count,
      Medium: s.medium_count,
      Low: s.low_count,
    }))
    .reverse()

  const totalVulns = scans.reduce((sum, s) => sum + (s.total_vulnerabilities || 0), 0)
  const completedScans = scans.filter((s) => s.status === 'completed').length
  const failedScans = scans.filter((s) => s.status === 'failed').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Welcome back, {user.username}</p>
        </div>
        <Link to="/scan" className="btn-primary flex items-center gap-2">
          <Upload size={16} />
          New Scan
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Scans', value: scans.length, icon: <Shield size={20} className="text-blue-400" /> },
          { label: 'Completed', value: completedScans, icon: <CheckCircle size={20} className="text-green-400" /> },
          { label: 'Failed', value: failedScans, icon: <XCircle size={20} className="text-red-400" /> },
          { label: 'Total CVEs Found', value: totalVulns, icon: <AlertTriangle size={20} className="text-orange-400" /> },
        ].map(({ label, value, icon }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center">
              {icon}
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-xs text-gray-500">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wide">
            Vulnerability Trend (Last {chartData.length} Scans)
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#6b7280' }} />
              <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#f9fafb' }}
              />
              {Object.entries(SEVERITY_COLORS).map(([key, color]) => (
                <Bar key={key} dataKey={key} stackId="a" fill={color} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Scans table */}
      <div className="card p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-800">
          <h2 className="font-semibold text-gray-200">Recent Scans</h2>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader className="animate-spin text-blue-400" />
          </div>
        ) : scans.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Shield size={40} className="mx-auto mb-3 opacity-30" />
            <p>No scans yet. <Link to="/scan" className="text-blue-400 hover:underline">Start your first scan</Link></p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {scans.map((scan) => (
              <Link
                key={scan.id}
                to={`/results/${scan.id}`}
                className="flex items-center gap-4 px-6 py-4 hover:bg-gray-800/50 transition-colors group"
              >
                <div className="flex items-center gap-2 shrink-0">
                  {STATUS_ICON[scan.status]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-200 truncate">{scan.original_filename}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(scan.created_at).toLocaleString()} · {scan.source}
                  </p>
                </div>
                {scan.status === 'completed' && (
                  <div className="flex items-center gap-3 text-xs shrink-0">
                    {scan.critical_count > 0 && (
                      <span className="badge-critical">{scan.critical_count} Critical</span>
                    )}
                    {scan.high_count > 0 && (
                      <span className="badge-high">{scan.high_count} High</span>
                    )}
                    {scan.medium_count > 0 && (
                      <span className="badge-medium">{scan.medium_count} Med</span>
                    )}
                  </div>
                )}
                {scan.status === 'failed' && (
                  <span className="text-xs text-red-400 shrink-0">Failed</span>
                )}
                {(scan.status === 'pending' || scan.status === 'running') && (
                  <span className="text-xs text-yellow-400 shrink-0 animate-pulse">Scanning...</span>
                )}
                <button
                  onClick={(e) => handleDelete(scan.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all ml-2"
                >
                  <Trash2 size={15} />
                </button>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
