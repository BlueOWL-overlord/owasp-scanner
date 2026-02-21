import { useState, useCallback } from 'react'
import { Upload, File, X, CheckCircle, Loader } from 'lucide-react'
import { scansAPI } from '../services/api'
import { useNavigate } from 'react-router-dom'

const SUPPORTED = ['.jar', '.war', '.ear', '.zip', '.sar', '.apk', '.nupkg', '.egg', '.wheel', '.tar', '.gz', '.tgz']

export default function FileUpload() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) validateAndSet(dropped)
  }, [])

  const validateAndSet = (f) => {
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!SUPPORTED.includes(ext)) {
      setError(`Unsupported file type. Supported: ${SUPPORTED.join(', ')}`)
      return
    }
    setError('')
    setFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const { data } = await scansAPI.upload(file)
      navigate(`/results/${data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input').click()}
        className={`relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
          dragging
            ? 'border-blue-500 bg-blue-500/10'
            : 'border-gray-700 hover:border-gray-500 hover:bg-gray-800/50'
        }`}
      >
        <input
          id="file-input"
          type="file"
          className="hidden"
          accept={SUPPORTED.join(',')}
          onChange={(e) => e.target.files[0] && validateAndSet(e.target.files[0])}
        />

        <div className="flex flex-col items-center gap-3">
          <div className="w-16 h-16 rounded-full bg-blue-600/20 flex items-center justify-center">
            <Upload className="w-8 h-8 text-blue-400" />
          </div>
          <div>
            <p className="text-lg font-medium text-gray-200">
              Drop your artifact here or <span className="text-blue-400">browse</span>
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Supported formats: JAR, WAR, EAR, ZIP, SAR, APK, NUPKG, EGG, WHEEL, TAR, GZ
            </p>
          </div>
        </div>
      </div>

      {/* Selected file */}
      {file && (
        <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-4">
          <File className="w-5 h-5 text-blue-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-200 truncate">{file.name}</p>
            <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
          <button
            onClick={() => setFile(null)}
            className="text-gray-500 hover:text-red-400 transition-colors"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 bg-red-900/20 border border-red-800 rounded-lg p-3 text-sm">
          <X size={16} />
          {error}
        </div>
      )}

      {/* Upload button */}
      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        className="w-full btn-primary flex items-center justify-center gap-2 py-3"
      >
        {uploading ? (
          <>
            <Loader className="w-4 h-4 animate-spin" />
            Uploading & Starting Scan...
          </>
        ) : (
          <>
            <Upload size={16} />
            Start OWASP Scan
          </>
        )}
      </button>

      {/* Info */}
      <div className="grid grid-cols-3 gap-3 text-center text-xs text-gray-500">
        {['Detects 180k+ CVEs', 'NVD Database', 'AI False Positive Analysis'].map((t) => (
          <div key={t} className="bg-gray-800/50 rounded-lg p-2">{t}</div>
        ))}
      </div>
    </div>
  )
}
