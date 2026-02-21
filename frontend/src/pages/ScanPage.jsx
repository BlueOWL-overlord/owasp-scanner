import { Shield, Info } from 'lucide-react'
import FileUpload from '../components/FileUpload'

export default function ScanPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">New Scan</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload a software artifact to scan for known vulnerabilities using OWASP Dependency Check
        </p>
      </div>

      <div className="card">
        <FileUpload />
      </div>

      {/* Info box */}
      <div className="bg-blue-950/30 border border-blue-900/40 rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Info size={16} className="text-blue-400" />
          <h3 className="text-sm font-semibold text-blue-400">How It Works</h3>
        </div>
        <ol className="space-y-2 text-sm text-gray-400 list-decimal list-inside">
          <li>Upload your artifact (JAR, WAR, ZIP, etc.)</li>
          <li>OWASP Dependency Check scans against the NVD CVE database</li>
          <li>Results are displayed with severity ratings and CVE details</li>
          <li>Use AI Analysis to identify false positives powered by Claude Opus</li>
          <li>Download the full report or integrate with your CI/CD pipeline</li>
        </ol>
      </div>

      {/* Supported formats */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">Supported Formats</h3>
        <div className="grid grid-cols-4 gap-2">
          {['JAR', 'WAR', 'EAR', 'ZIP', 'SAR', 'APK', 'NUPKG', 'EGG', 'WHEEL', 'TAR', 'GZ', 'TGZ'].map((ext) => (
            <div key={ext} className="bg-gray-800 rounded-lg p-2 text-center text-xs font-mono text-gray-300">
              .{ext.toLowerCase()}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
