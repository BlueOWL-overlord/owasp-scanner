import { useState, useEffect } from 'react'
import { GitBranch, Loader } from 'lucide-react'
import CicdIntegration from '../components/CicdIntegration'
import { integrationsAPI } from '../services/api'

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchIntegrations = async () => {
    try {
      const { data } = await integrationsAPI.list()
      setIntegrations(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIntegrations()
  }, [])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <GitBranch className="text-blue-400" size={24} />
          CI/CD Integrations
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Connect Azure DevOps, Jenkins, or AWS CodePipeline to trigger and receive OWASP scans automatically
        </p>
      </div>

      {/* How-to */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            icon: '🔵',
            title: 'Azure DevOps',
            desc: 'Trigger pipelines via REST API using Personal Access Tokens. Add a webhook step in your YAML pipeline.',
          },
          {
            icon: '🔶',
            title: 'Jenkins',
            desc: 'Use Jenkins Remote Access API to trigger jobs. Add a build step to POST results to the webhook endpoint.',
          },
          {
            icon: '🟠',
            title: 'AWS CodePipeline',
            desc: 'Start pipeline executions via AWS API. Use Lambda or CodeBuild to POST results back via webhook.',
          },
        ].map((item) => (
          <div key={item.title} className="card text-sm">
            <div className="text-2xl mb-2">{item.icon}</div>
            <h3 className="font-semibold text-gray-200 mb-1">{item.title}</h3>
            <p className="text-gray-500 text-xs leading-relaxed">{item.desc}</p>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <Loader className="animate-spin text-blue-400" />
        </div>
      ) : (
        <CicdIntegration integrations={integrations} onRefresh={fetchIntegrations} />
      )}

      {/* Webhook docs */}
      <div className="card">
        <h3 className="font-semibold text-gray-200 mb-3">Webhook Integration Guide</h3>
        <p className="text-sm text-gray-400 mb-3">
          After configuring an integration, use the webhook URL in your pipeline to submit scan results:
        </p>
        <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-green-400 overflow-x-auto">{`POST /api/integrations/webhook/<your-token>
Content-Type: application/json

{
  "source": "jenkins",          // azure | jenkins | aws
  "project_name": "my-app",
  "artifact_url": "https://...", // Optional: URL to download artifact
  "metadata": {}                  // Optional: custom data
}`}</pre>

        <div className="mt-4">
          <h4 className="text-sm font-semibold text-gray-400 mb-2">Jenkins Pipeline Example</h4>
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-green-400 overflow-x-auto">{`pipeline {
  stages {
    stage('OWASP Scan') {
      steps {
        sh '''
          curl -X POST \\
            -H "Content-Type: application/json" \\
            -d '{"source":"jenkins","project_name":"'"\${JOB_NAME}"'",
                 "artifact_url":"'"\${ARTIFACT_URL}"'"}' \\
            \${OWASP_SCANNER_WEBHOOK_URL}
        '''
      }
    }
  }
}`}</pre>
        </div>

        <div className="mt-4">
          <h4 className="text-sm font-semibold text-gray-400 mb-2">Azure DevOps Pipeline Example</h4>
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-green-400 overflow-x-auto">{`- task: PowerShell@2
  displayName: 'Trigger OWASP Scan'
  inputs:
    script: |
      $body = @{
        source = "azure"
        project_name = "$(Build.Repository.Name)"
        artifact_url = "$(artifact_url)"
      } | ConvertTo-Json
      Invoke-RestMethod -Uri "$(OWASP_WEBHOOK_URL)" \\
        -Method POST -Body $body \\
        -ContentType "application/json"`}</pre>
        </div>
      </div>
    </div>
  )
}
