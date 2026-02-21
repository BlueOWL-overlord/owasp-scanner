import { useState } from 'react'
import { Plus, Trash2, Play, ChevronDown, GitBranch, Loader, CheckCircle, X } from 'lucide-react'
import { integrationsAPI } from '../services/api'

const INTEGRATION_TYPES = [
  { value: 'azure', label: 'Azure DevOps', icon: '🔵', fields: ['org_url', 'project', 'pat', 'pipeline_id'] },
  { value: 'jenkins', label: 'Jenkins', icon: '🔶', fields: ['url', 'username', 'token', 'default_job'] },
  { value: 'aws', label: 'AWS CodePipeline', icon: '🟠', fields: ['access_key_id', 'secret_access_key', 'region', 'pipeline_name'] },
]

const FIELD_LABELS = {
  org_url: 'Organization URL',
  project: 'Project Name',
  pat: 'Personal Access Token',
  pipeline_id: 'Pipeline ID',
  url: 'Jenkins URL',
  username: 'Username',
  token: 'API Token',
  default_job: 'Default Job Name',
  access_key_id: 'AWS Access Key ID',
  secret_access_key: 'AWS Secret Access Key',
  region: 'AWS Region',
  pipeline_name: 'Pipeline Name',
}

const SENSITIVE = new Set(['pat', 'token', 'secret_access_key'])

export default function CicdIntegration({ integrations, onRefresh }) {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', type: 'azure', config: {} })
  const [saving, setSaving] = useState(false)
  const [triggering, setTriggering] = useState(null)
  const [status, setStatus] = useState({})
  const [error, setError] = useState('')

  const selectedType = INTEGRATION_TYPES.find((t) => t.value === form.type)

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await integrationsAPI.create(form)
      setShowForm(false)
      setForm({ name: '', type: 'azure', config: {} })
      onRefresh()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save integration')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this integration?')) return
    await integrationsAPI.delete(id)
    onRefresh()
  }

  const handleTrigger = async (id) => {
    setTriggering(id)
    setStatus((s) => ({ ...s, [id]: null }))
    try {
      const { data } = await integrationsAPI.trigger(id, {})
      setStatus((s) => ({ ...s, [id]: { ok: true, msg: 'Pipeline triggered successfully!' } }))
    } catch (err) {
      setStatus((s) => ({
        ...s,
        [id]: { ok: false, msg: err.response?.data?.detail || 'Trigger failed' },
      }))
    } finally {
      setTriggering(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* Integrations list */}
      {integrations.length === 0 && !showForm && (
        <div className="text-center py-12 text-gray-500 card">
          <GitBranch size={40} className="mx-auto mb-3 opacity-50" />
          <p className="font-medium">No CI/CD integrations configured</p>
          <p className="text-sm mt-1">Connect Azure, Jenkins, or AWS to trigger scans from pipelines</p>
        </div>
      )}

      {integrations.map((integ) => {
        const typeInfo = INTEGRATION_TYPES.find((t) => t.value === integ.type)
        const st = status[integ.id]
        return (
          <div key={integ.id} className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{typeInfo?.icon || '🔌'}</span>
                <div>
                  <p className="font-medium text-gray-200">{integ.name}</p>
                  <p className="text-xs text-gray-500">{typeInfo?.label} · {integ.type}</p>
                  {integ.last_used_at && (
                    <p className="text-xs text-gray-600">
                      Last used: {new Date(integ.last_used_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleTrigger(integ.id)}
                  disabled={triggering === integ.id}
                  className="btn-primary flex items-center gap-1.5 text-sm py-2"
                >
                  {triggering === integ.id ? (
                    <Loader size={13} className="animate-spin" />
                  ) : (
                    <Play size={13} />
                  )}
                  Trigger
                </button>
                <button
                  onClick={() => handleDelete(integ.id)}
                  className="text-gray-500 hover:text-red-400 transition-colors p-2"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>

            {st && (
              <div className={`mt-3 flex items-center gap-2 text-sm rounded-lg p-2 ${
                st.ok ? 'bg-green-900/20 text-green-400' : 'bg-red-900/20 text-red-400'
              }`}>
                {st.ok ? <CheckCircle size={14} /> : <X size={14} />}
                {st.msg}
              </div>
            )}

            {/* Webhook info */}
            <div className="mt-3 bg-gray-800/50 rounded-lg p-3">
              <p className="text-xs text-gray-500 font-medium mb-1">Webhook URL (for CI/CD pipeline callbacks):</p>
              <code className="text-xs text-blue-300 break-all">
                {window.location.origin}/api/integrations/webhook/your-token
              </code>
            </div>
          </div>
        )
      })}

      {/* Add form */}
      {showForm ? (
        <div className="card space-y-4">
          <h3 className="font-semibold text-gray-200">Add CI/CD Integration</h3>

          <div>
            <label className="label">Integration Name</label>
            <input
              className="input"
              placeholder="e.g. My Jenkins"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>

          <div>
            <label className="label">Type</label>
            <select
              className="input"
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value, config: {} })}
            >
              {INTEGRATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
              ))}
            </select>
          </div>

          {selectedType?.fields.map((field) => (
            <div key={field}>
              <label className="label">{FIELD_LABELS[field] || field}</label>
              <input
                className="input"
                type={SENSITIVE.has(field) ? 'password' : 'text'}
                placeholder={FIELD_LABELS[field]}
                value={form.config[field] || ''}
                onChange={(e) =>
                  setForm({ ...form, config: { ...form.config, [field]: e.target.value } })
                }
              />
            </div>
          ))}

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          <div className="flex gap-2">
            <button onClick={handleSave} disabled={saving || !form.name} className="btn-primary flex items-center gap-2">
              {saving && <Loader size={14} className="animate-spin" />}
              Save Integration
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="w-full border-2 border-dashed border-gray-700 hover:border-gray-500 rounded-xl p-4 text-gray-500 hover:text-gray-300 transition-colors flex items-center justify-center gap-2"
        >
          <Plus size={18} />
          Add Integration
        </button>
      )}
    </div>
  )
}
