import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Loader, XCircle, Clock, CheckCircle, RefreshCw } from 'lucide-react'
import { scansAPI } from '../services/api'
import ScanResults from '../components/ScanResults'
import ScanLog from '../components/ScanLog'

const STATUS_MAP = {
  pending: { label: 'Queued', icon: <Clock size={16} className="text-yellow-400" />, color: 'text-yellow-400' },
  running: { label: 'Scanning...', icon: <Loader size={16} className="text-blue-400 animate-spin" />, color: 'text-blue-400' },
  completed: { label: 'Completed', icon: <CheckCircle size={16} className="text-green-400" />, color: 'text-green-400' },
  failed: { label: 'Failed', icon: <XCircle size={16} className="text-red-400" />, color: 'text-red-400' },
}

export default function ResultsPage() {
  const { scanId } = useParams()
  const [scan, setScan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchScan = useCallback(async () => {
    try {
      const { data } = await scansAPI.get(scanId)
      setScan(data)
      setError('')
    } catch (err) {
      setError('Scan not found or access denied')
    } finally {
      setLoading(false)
    }
  }, [scanId])

  useEffect(() => {
    fetchScan()
  }, [fetchScan])

  // Poll while scan is in progress
  useEffect(() => {
    if (!scan || scan.status === 'completed' || scan.status === 'failed') return
    const interval = setInterval(fetchScan, 4000)
    return () => clearInterval(interval)
  }, [scan, fetchScan])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader className="animate-spin text-blue-400" size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24">
        <XCircle size={40} className="mx-auto mb-3 text-red-400" />
        <p className="text-gray-400">{error}</p>
        <Link to="/" className="btn-secondary mt-4 inline-flex items-center gap-2">
          <ArrowLeft size={16} /> Back to Dashboard
        </Link>
      </div>
    )
  }

  const statusInfo = STATUS_MAP[scan.status] || STATUS_MAP.pending

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link to="/" className="text-gray-500 hover:text-gray-300 transition-colors mt-1">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-white truncate">{scan.original_filename}</h1>
            <div className={`flex items-center gap-1.5 text-sm ${statusInfo.color}`}>
              {statusInfo.icon}
              <span>{statusInfo.label}</span>
            </div>
            <button onClick={fetchScan} className="text-gray-500 hover:text-gray-300 transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Scan #{scan.id} · Started {new Date(scan.created_at).toLocaleString()} · Source: {scan.source}
            {scan.completed_at && ` · Completed ${new Date(scan.completed_at).toLocaleString()}`}
          </p>
        </div>
      </div>

      {/* Running state */}
      {(scan.status === 'pending' || scan.status === 'running') && (
        <div className="card text-center py-8">
          <div className="w-14 h-14 rounded-full border-4 border-blue-500 border-t-transparent animate-spin mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-200 mb-2">
            {scan.status === 'pending' ? 'Scan Queued' : 'Scanning Dependencies...'}
          </h2>
          <p className="text-gray-500 text-sm">
            OWASP Dependency Check is analyzing your artifact against the NVD database.
            <br />First-time scans download the NVD database (~500 MB) — this takes 10–20 min.
          </p>
        </div>
      )}

      {/* Failed state */}
      {scan.status === 'failed' && (
        <div className="card border-red-900/40 bg-red-950/10">
          <div className="flex items-start gap-3">
            <XCircle className="text-red-400 shrink-0 mt-0.5" size={20} />
            <div>
              <h3 className="font-semibold text-red-400">Scan Failed</h3>
              <p className="text-sm text-gray-400 mt-1 font-mono">
                {scan.error_message || 'An unknown error occurred'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Console log — visible for all non-pending states */}
      {scan.status !== 'pending' && (
        <ScanLog scanId={scan.id} scanStatus={scan.status} />
      )}

      {/* Completed results */}
      {scan.status === 'completed' && (
        scan.total_vulnerabilities === 0 ? (
          <div className="card text-center py-12">
            <CheckCircle size={48} className="mx-auto mb-4 text-green-400" />
            <h2 className="text-xl font-bold text-white mb-2">No Vulnerabilities Found!</h2>
            <p className="text-gray-500">
              OWASP Dependency Check found no known CVEs in the scanned artifact.
            </p>
          </div>
        ) : (
          <ScanResults scan={scan} onRefresh={fetchScan} />
        )
      )}
    </div>
  )
}
