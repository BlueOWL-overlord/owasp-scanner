import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal, ChevronDown, ChevronUp, Download } from 'lucide-react'
import { scansAPI } from '../services/api'

/** Colour-code a single log line based on its content */
function LogLine({ line, index }) {
  let cls = 'text-gray-400'
  if (/\b(ERROR|EXCEPTION|FATAL|SEVERE)\b/i.test(line)) cls = 'text-red-400'
  else if (/\b(WARN|WARNING)\b/i.test(line))             cls = 'text-yellow-400'
  else if (/\b(INFO)\b/i.test(line))                     cls = 'text-blue-300'
  else if (/\b(DEBUG)\b/i.test(line))                    cls = 'text-gray-500'
  else if (/CVE-\d{4}-\d+/i.test(line))                  cls = 'text-orange-400'
  else if (/\b(Done|Complete|Success|Finished)\b/i.test(line)) cls = 'text-green-400'

  return (
    <div className="flex gap-2 hover:bg-gray-800/40 px-2 py-0.5 rounded group">
      <span className="text-gray-600 select-none w-8 shrink-0 text-right tabular-nums">
        {index + 1}
      </span>
      <span className={`${cls} font-mono text-xs whitespace-pre-wrap break-all`}>
        {line || '\u00A0'}
      </span>
    </div>
  )
}

export default function ScanLog({ scanId, scanStatus }) {
  const [log, setLog]           = useState('')
  const [open, setOpen]         = useState(true)
  const [autoScroll, setAutoScroll] = useState(true)
  const bottomRef               = useRef(null)
  const containerRef            = useRef(null)
  const isActive = scanStatus === 'pending' || scanStatus === 'running'

  const fetchLog = useCallback(async () => {
    try {
      const { data } = await scansAPI.getLog(scanId)
      setLog(data || '')
    } catch {
      // silently ignore — log may not exist yet
    }
  }, [scanId])

  // Initial fetch
  useEffect(() => { fetchLog() }, [fetchLog])

  // Poll every 2 s while scan is active
  useEffect(() => {
    if (!isActive) return
    const id = setInterval(fetchLog, 2000)
    return () => clearInterval(id)
  }, [isActive, fetchLog])

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [log, autoScroll])

  // Detect manual scroll-up → disable auto-scroll
  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40)
  }

  const lines = log.split('\n')

  const downloadLog = () => {
    const blob = new Blob([log], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `scan-${scanId}.log`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card overflow-hidden">
      {/* Header bar */}
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center gap-2">
          <Terminal size={16} className="text-green-400" />
          <span className="text-sm font-semibold text-gray-200">Scan Console Output</span>
          {isActive && (
            <span className="flex items-center gap-1 text-xs text-blue-400">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              Live
            </span>
          )}
          <span className="text-xs text-gray-600">{lines.length} lines</span>
        </div>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {log && (
            <button
              onClick={downloadLog}
              className="text-gray-500 hover:text-gray-300 transition-colors p-1"
              title="Download log"
            >
              <Download size={14} />
            </button>
          )}
          <button className="text-gray-500 hover:text-gray-300 transition-colors p-1">
            {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {open && (
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="mt-3 bg-gray-950 rounded-lg border border-gray-800 overflow-y-auto"
          style={{ maxHeight: '420px', minHeight: '120px' }}
        >
          {lines.length === 0 || (lines.length === 1 && !lines[0]) ? (
            <p className="text-gray-600 text-xs font-mono px-4 py-6 text-center">
              {isActive ? 'Waiting for output...' : 'No log available.'}
            </p>
          ) : (
            <div className="py-2">
              {lines.map((line, i) => (
                <LogLine key={i} line={line} index={i} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}

          {/* Auto-scroll indicator */}
          {!autoScroll && isActive && (
            <button
              onClick={() => {
                setAutoScroll(true)
                bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
              }}
              className="sticky bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded-full shadow-lg transition-colors"
            >
              <ChevronDown size={12} /> Resume auto-scroll
            </button>
          )}
        </div>
      )}
    </div>
  )
}
