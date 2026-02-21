import { useState } from 'react'
import { Brain, Download, Filter, AlertTriangle, CheckCircle, Loader } from 'lucide-react'
import VulnerabilityCard from './VulnerabilityCard'
import { scansAPI } from '../services/api'

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN', 'INFO']

export default function ScanResults({ scan, onRefresh }) {
  const [selectedIds, setSelectedIds] = useState([])
  const [filterSeverity, setFilterSeverity] = useState('ALL')
  const [filterFP, setFilterFP] = useState('ALL')
  const [showSuppressed, setShowSuppressed] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')

  const vulns = scan.vulnerabilities || []

  const filtered = vulns.filter((v) => {
    if (!showSuppressed && v.is_suppressed) return false
    if (filterSeverity !== 'ALL' && v.severity !== filterSeverity) return false
    if (filterFP === 'FP' && !v.ai_is_false_positive) return false
    if (filterFP === 'REAL' && v.ai_is_false_positive !== false) return false
    return true
  })

  const sorted = [...filtered].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  )

  const handleSelect = (id, checked) => {
    setSelectedIds((prev) => checked ? [...prev, id] : prev.filter((x) => x !== id))
  }

  const handleSelectAll = () => {
    const ids = sorted.map((v) => v.id)
    setSelectedIds(selectedIds.length === ids.length ? [] : ids)
  }

  const handleAnalyze = async () => {
    const ids = selectedIds.length > 0 ? selectedIds : sorted.map((v) => v.id)
    if (ids.length === 0) return
    setAnalyzing(true)
    setAnalysisError('')
    try {
      await scansAPI.analyze(scan.id, ids)
      onRefresh()
      setSelectedIds([])
    } catch (err) {
      setAnalysisError(err.response?.data?.detail || 'AI analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleSuppress = async (vulnId) => {
    await scansAPI.suppress(scan.id, vulnId)
    onRefresh()
  }

  const handleDownload = async () => {
    const { data } = await scansAPI.downloadReport(scan.id)
    const url = URL.createObjectURL(new Blob([data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `scan-${scan.id}-report.json`
    a.click()
  }

  const fpCount = vulns.filter((v) => v.ai_is_false_positive).length
  const analyzedCount = vulns.filter((v) => v.ai_is_false_positive !== null && v.ai_is_false_positive !== undefined).length

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Total', value: vulns.length, color: 'text-gray-300' },
          { label: 'Critical', value: scan.critical_count, color: 'text-red-400' },
          { label: 'High', value: scan.high_count, color: 'text-orange-400' },
          { label: 'Medium', value: scan.medium_count, color: 'text-yellow-400' },
          { label: 'Low', value: scan.low_count, color: 'text-blue-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card text-center py-3">
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* AI summary */}
      {analyzedCount > 0 && (
        <div className="flex items-center gap-3 bg-blue-950/30 border border-blue-900/40 rounded-xl p-4">
          <Brain className="w-5 h-5 text-blue-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-300">
              AI Analysis Complete — {analyzedCount} of {vulns.length} vulnerabilities analyzed
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {fpCount} identified as likely false positives, {analyzedCount - fpCount} confirmed risks
            </p>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Severity filter */}
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
        >
          <option value="ALL">All Severities</option>
          {SEVERITY_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* FP filter */}
        <select
          value={filterFP}
          onChange={(e) => setFilterFP(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
        >
          <option value="ALL">All Results</option>
          <option value="FP">False Positives Only</option>
          <option value="REAL">Confirmed Risks Only</option>
        </select>

        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showSuppressed}
            onChange={(e) => setShowSuppressed(e.target.checked)}
            className="accent-blue-500"
          />
          Show suppressed
        </label>

        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-gray-500">
            {selectedIds.length > 0 ? `${selectedIds.length} selected` : `${sorted.length} shown`}
          </span>
          <button
            onClick={handleAnalyze}
            disabled={analyzing || sorted.length === 0}
            className="btn-primary flex items-center gap-1.5 text-sm py-2"
          >
            {analyzing ? (
              <><Loader size={14} className="animate-spin" /> Analyzing...</>
            ) : (
              <><Brain size={14} /> AI Analyze {selectedIds.length > 0 ? `(${selectedIds.length})` : 'All'}</>
            )}
          </button>
          <button onClick={handleDownload} className="btn-secondary flex items-center gap-1.5 text-sm py-2">
            <Download size={14} /> Report
          </button>
        </div>
      </div>

      {analysisError && (
        <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg p-3">
          {analysisError}
        </div>
      )}

      {/* Select all */}
      {sorted.length > 0 && (
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={selectedIds.length === sorted.length && sorted.length > 0}
            onChange={handleSelectAll}
            className="accent-blue-500"
          />
          <span className="text-sm text-gray-400">Select all visible</span>
        </div>
      )}

      {/* Vulnerability list */}
      {sorted.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <CheckCircle size={40} className="mx-auto mb-3 text-green-500" />
          <p className="font-medium">No vulnerabilities match your filters</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((v) => (
            <VulnerabilityCard
              key={v.id}
              vuln={v}
              selected={selectedIds.includes(v.id)}
              onSelect={handleSelect}
              onSuppress={handleSuppress}
            />
          ))}
        </div>
      )}
    </div>
  )
}
