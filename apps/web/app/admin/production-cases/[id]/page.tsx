'use client'

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import {
  adminApiClient,
  ProductionCase,
  ReleaseGate,
} from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'

function gateTone(gate: ReleaseGate) {
  if (gate.status === 'passed' || gate.status === 'overridden') return 'border-green-700 bg-green-950/30'
  if (gate.status === 'failed') return 'border-red-700 bg-red-950/30'
  if (gate.status === 'warning' || gate.status === 'unchecked') return 'border-yellow-700 bg-yellow-950/30'
  return 'border-gray-700 bg-gray-800'
}

const DETECTOR_GATES = new Set(['plagiarism_proxy', 'ai_detection_proxy'])

type DetectorForm = {
  detector_name: string
  result_percent: string
  decision: '' | 'passed' | 'failed'
  artifact_format: '' | 'docx' | 'pdf'
  checked_at: string
  report_ref: string
  reason: string
}

export default function ProductionCaseDetailPage() {
  const params = useParams()
  const caseId = Number(params.id)
  const [productionCase, setProductionCase] = useState<ProductionCase | null>(null)
  const [gates, setGates] = useState<ReleaseGate[]>([])
  const [loading, setLoading] = useState(true)
  const [isReleasing, setIsReleasing] = useState(false)
  const [savingDetector, setSavingDetector] = useState<string | null>(null)
  const [detectorForms, setDetectorForms] = useState<Record<string, DetectorForm>>({})

  const blockers = useMemo(
    () =>
      gates.filter(
        (gate) =>
          gate.blocking &&
          ['failed', 'no_data', 'unchecked', 'warning'].includes(gate.status) &&
          !gate.override_reason
      ),
    [gates]
  )

  const load = async () => {
    try {
      setLoading(true)
      const [caseData, gateData] = await Promise.all([
        adminApiClient.getProductionCase(caseId),
        adminApiClient.getReleaseGates(caseId),
      ])
      setProductionCase(caseData)
      setGates(gateData)
    } catch (error) {
      console.error('Failed to load production case:', error)
      toast.error('Failed to load production case')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (Number.isFinite(caseId)) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId])

  const handleRelease = async () => {
    try {
      setIsReleasing(true)
      await adminApiClient.releaseProductionCase(caseId, 'Approved from manager console')
      toast.success('Production case released')
      await load()
    } catch (error: any) {
      toast.error(error?.message || 'Release blocked')
    } finally {
      setIsReleasing(false)
    }
  }

  const handleOverride = async (gate: ReleaseGate) => {
    const reason = window.prompt(`Override ${gate.gate_key}. Enter reason:`)
    if (!reason) return
    try {
      await adminApiClient.overrideReleaseGate(caseId, gate.gate_key, reason)
      toast.success('Gate overridden')
      await load()
    } catch (error: any) {
      toast.error(error?.message || 'Failed to override gate')
    }
  }

  const detectorFormFor = (gateKey: string): DetectorForm => {
    const artifactBindings = productionCase?.document?.artifact_bindings
    const defaultArtifactFormat: DetectorForm['artifact_format'] = artifactBindings?.docx
      ? 'docx'
      : artifactBindings?.pdf
        ? 'pdf'
        : ''
    return detectorForms[gateKey] || {
      detector_name: 'Compilatio',
      result_percent: '',
      decision: '',
      artifact_format: defaultArtifactFormat,
      checked_at: new Date().toISOString().slice(0, 16),
      report_ref: 'docs/phase1-runs/RUN-001.md',
      reason: '',
    }
  }

  const updateDetectorForm = (
    gateKey: string,
    patch: Partial<ReturnType<typeof detectorFormFor>>
  ) => {
    setDetectorForms((current) => ({
      ...current,
      [gateKey]: { ...detectorFormFor(gateKey), ...patch },
    }))
  }

  const handleDetectorSubmit = async (
    event: FormEvent<HTMLFormElement>,
    gate: ReleaseGate
  ) => {
    event.preventDefault()
    const form = detectorFormFor(gate.gate_key)
    if (!form.decision || !form.artifact_format) {
      toast.error('Choose a release decision and the exact artifact that was checked')
      return
    }
    try {
      setSavingDetector(gate.gate_key)
      await adminApiClient.recordDetectorResult(caseId, gate.gate_key, {
        detector_name: form.detector_name,
        result_percent: Number(form.result_percent),
        decision: form.decision,
        artifact_format: form.artifact_format,
        checked_at: new Date(form.checked_at).toISOString(),
        report_ref: form.report_ref,
        reason: form.reason,
      })
      toast.success('Detector result recorded')
      await load()
    } catch (error: any) {
      toast.error(error?.message || 'Failed to record release decision')
    } finally {
      setSavingDetector(null)
    }
  }

  if (loading || !productionCase) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Production Case #{productionCase.id}
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            {productionCase.document?.title || `Document ${productionCase.document_id}`}
          </p>
        </div>
        <Button onClick={handleRelease} disabled={isReleasing || blockers.length > 0}>
          {isReleasing ? 'Releasing...' : 'Approve release'}
        </Button>
      </div>

      {blockers.length > 0 && (
        <div className="rounded-lg border border-red-700 bg-red-950/30 p-4 text-sm text-red-100">
          Release blocked by {blockers.map((gate) => gate.gate_key).join(', ')}.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[
          ['Generation', productionCase.generation_status],
          ['QA', productionCase.qa_status],
          ['Editorial', productionCase.editorial_status],
          ['Delivery', productionCase.delivery_status],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <p className="text-xs uppercase text-gray-400">{label}</p>
            <p className="mt-2 text-lg font-semibold text-white">{value}</p>
          </div>
        ))}
      </div>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-white">QA Evidence</h2>
          <p className="mt-1 text-sm text-gray-400">
            Consolidated manager view for release blockers, provenance, detector proxies,
            human minutes, and delivery package readiness.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {gates.map((gate) => {
            const form = detectorFormFor(gate.gate_key)
            const isDetectorGate = DETECTOR_GATES.has(gate.gate_key)
            const selectedArtifactBinding = form.artifact_format
              ? productionCase.document?.artifact_bindings?.[form.artifact_format]
              : undefined
            return (
              <div key={gate.gate_key} className={`rounded-lg border p-4 ${gateTone(gate)}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-white">{gate.gate_key}</h3>
                    <p className="mt-1 text-sm text-gray-300">{gate.summary}</p>
                  </div>
                  <span className="rounded bg-gray-900 px-2 py-1 text-xs text-gray-200">
                    {gate.status}
                  </span>
                </div>
                <p className="mt-3 text-xs text-gray-400">
                  {gate.blocking ? 'Blocking' : 'Advisory'} · {gate.source}
                </p>
                {gate.evidence && Object.keys(gate.evidence).length > 0 && (
                  <dl className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-300 sm:grid-cols-2">
                    {Object.entries(gate.evidence)
                      .filter(([key]) =>
                        [
                          'detector_name',
                          'result_percent',
                          'decision',
                          'checked_at',
                          'report_ref',
                          'artifact_format',
                          'artifact_identifier',
                          'binding_status',
                        ].includes(key)
                      )
                      .map(([key, value]) => (
                        <div key={key}>
                          <dt className="text-gray-500">{key}</dt>
                          <dd className="break-words text-gray-200">{String(value)}</dd>
                        </div>
                      ))}
                  </dl>
                )}
                {gate.override_reason && (
                  <p className="mt-2 text-xs text-green-200">
                    Override: {gate.override_reason}
                  </p>
                )}
                {isDetectorGate && (
                  <form
                    onSubmit={(event) => handleDetectorSubmit(event, gate)}
                    className="mt-4 space-y-3 border-t border-gray-700 pt-4"
                  >
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <label className="text-xs text-gray-300">
                        Release detector
                        <input
                          value={form.detector_name}
                          readOnly
                          className="mt-1 w-full rounded border border-gray-600 bg-gray-900 px-2 py-1.5 text-sm text-gray-300"
                          required
                        />
                        <span className="mt-1 block text-gray-500">
                          GPTZero is diagnostic only and cannot authorize release.
                        </span>
                      </label>
                      <label className="text-xs text-gray-300">
                        Checked at
                        <input
                          type="datetime-local"
                          value={form.checked_at}
                          onChange={(event) =>
                            updateDetectorForm(gate.gate_key, {
                              checked_at: event.target.value,
                            })
                          }
                          className="mt-1 w-full rounded border border-gray-600 bg-gray-950 px-2 py-1.5 text-sm text-white"
                          required
                        />
                      </label>
                      <label className="text-xs text-gray-300">
                        Result %
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step="0.01"
                          value={form.result_percent}
                          onChange={(event) =>
                            updateDetectorForm(gate.gate_key, {
                              result_percent: event.target.value,
                            })
                          }
                          className="mt-1 w-full rounded border border-gray-600 bg-gray-950 px-2 py-1.5 text-sm text-white"
                          required
                        />
                      </label>
                      <label className="text-xs text-gray-300">
                        Release decision
                        <select
                          value={form.decision}
                          onChange={(event) =>
                            updateDetectorForm(gate.gate_key, {
                              decision: event.target.value as DetectorForm['decision'],
                            })
                          }
                          className="mt-1 w-full rounded border border-gray-600 bg-gray-950 px-2 py-1.5 text-sm text-white"
                          required
                        >
                          <option value="">Choose passed or failed</option>
                          <option value="passed">Passed</option>
                          <option value="failed">Failed</option>
                        </select>
                      </label>
                    </div>
                    <label className="block text-xs text-gray-300">
                      Checked artifact
                      <select
                        value={form.artifact_format}
                        onChange={(event) =>
                          updateDetectorForm(gate.gate_key, {
                            artifact_format: event.target.value as DetectorForm['artifact_format'],
                          })
                        }
                        className="mt-1 w-full rounded border border-gray-600 bg-gray-950 px-2 py-1.5 text-sm text-white"
                        required
                      >
                        <option value="">Choose the generated file you checked</option>
                        {(['docx', 'pdf'] as const).map((artifactFormat) => {
                          const binding = productionCase.document?.artifact_bindings?.[artifactFormat]
                          return binding ? (
                            <option key={artifactFormat} value={artifactFormat}>
                              {artifactFormat.toUpperCase()} · {binding.identifier}
                            </option>
                          ) : null
                        })}
                      </select>
                      <span className="mt-1 block text-gray-500">
                        Plagiarism and AI decisions must both use this same final file.
                      </span>
                    </label>
                    {selectedArtifactBinding && (
                      <p className="rounded border border-gray-700 bg-gray-950 p-2 text-xs text-gray-300">
                        Server artifact ID: {selectedArtifactBinding.identifier}. This ID is attached
                        automatically and cannot be supplied by the browser.
                      </p>
                    )}
                    <label className="block text-xs text-gray-300">
                      Run report reference
                      <input
                        value={form.report_ref}
                        onChange={(event) =>
                          updateDetectorForm(gate.gate_key, {
                            report_ref: event.target.value,
                          })
                        }
                        className="mt-1 w-full rounded border border-gray-600 bg-gray-950 px-2 py-1.5 text-sm text-white"
                        required
                      />
                    </label>
                    <label className="block text-xs text-gray-300">
                      Release-manager rationale
                      <textarea
                        value={form.reason}
                        onChange={(event) =>
                          updateDetectorForm(gate.gate_key, {
                            reason: event.target.value,
                          })
                        }
                        className="mt-1 h-20 w-full rounded border border-gray-600 bg-gray-950 px-2 py-1.5 text-sm text-white"
                        required
                      />
                    </label>
                    <button
                      type="submit"
                      disabled={savingDetector === gate.gate_key}
                      className="rounded bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
                    >
                      {savingDetector === gate.gate_key ? 'Saving...' : 'Record release decision'}
                    </button>
                  </form>
                )}
                {gate.override_allowed && gate.status !== 'overridden' && (
                  <button
                    type="button"
                    onClick={() => handleOverride(gate)}
                    className="mt-3 text-sm text-primary-300 hover:text-primary-200"
                  >
                    Override with reason
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h2 className="text-lg font-semibold text-white">Production Economics</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase text-gray-400">Human minutes</p>
            <p className="mt-1 text-white">{productionCase.human_minutes_used}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-gray-400">Cost</p>
            <p className="mt-1 text-white">€{(productionCase.cost_cents / 100).toFixed(2)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-gray-400">AI cost</p>
            <p className="mt-1 text-white">
              €{((productionCase.ai_cost_eur_cents ?? 0) / 100).toFixed(2)}
            </p>
            <p className="text-xs text-gray-400">
              {(productionCase.ai_total_tokens ?? 0).toLocaleString()} tokens
            </p>
          </div>
          <div>
            <p className="text-xs uppercase text-gray-400">Client</p>
            <p className="mt-1 text-white">{productionCase.client_email || 'Unknown'}</p>
          </div>
        </div>
      </section>
    </div>
  )
}
