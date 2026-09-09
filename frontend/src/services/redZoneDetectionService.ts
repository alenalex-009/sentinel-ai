// Sentinel AI — Automated Red Zone Detection and Alerting Service
//
// Polls the backend risk engine (/api/v1/risk/priorities) for real
// per-habitation risk scores and derives Red Zone statuses from them.
// The backend is the single source of truth for risk numbers; this service
// only classifies (thresholds + trend), and raises/clears alerts.
//
// Escalation semantics: an alert is raised when a habitation's status becomes
// MORE severe than its previous assessment, and cleared when it becomes less
// severe. Statuses are never compared against the assessment being processed
// (that comparison is always "equal").

import {
  RedZoneStatus
} from '../types/index'
import { api } from '../api/client'

interface BackendHabitation {
  id: string
  name: string
  ward?: string
  taluk?: string
  population: number
  risk_score: number
  risk_change: number
  priority: string
  primary_hazard: string
  data_status?: string
  rpi_score?: number
}

interface PrioritiesResponse {
  data_status: string
  district_id: string
  habitations: BackendHabitation[]
}

interface RedZoneAlert {
  id: string
  habitationId: string
  habitationName: string
  redZoneStatus: RedZoneStatus
  riskScore: number
  confidence: number
  triggers: string[]
  detectedAt: string
  expiresAt: string | null
  recommendedActions: string[]
}

interface RedZoneAssessment {
  habitationId: string
  habitationName: string
  currentStatus: RedZoneStatus
  recommendedStatus: RedZoneStatus
  riskTrend: 'increasing' | 'stable' | 'decreasing'
  riskScoreHistory: Array<{ score: number; timestamp: string }>
  source: {
    riskScore: number        // current operational risk from the API
    baselineRisk: number     // risk_score - risk_change
    riskChange: number       // event-driven movement reported by the engine
    priority: string         // engine RPI classification
    dataStatus: string       // DEMO | LIVE | ... — provenance of the numbers
  }
  confidence: number
  recommendedActions: string[]
  validUntil: string
}

const SEVERITY_ORDER: Record<RedZoneStatus, number> = {
  NOT_RECOMMENDED: 0,
  DATA_INSUFFICIENT: 1,
  UNDER_ASSESSMENT: 2,
  RED_ZONE_CANDIDATE: 3,
}

export class RedZoneDetectionService {
  private static instance: RedZoneDetectionService
  private monitoringInterval: ReturnType<typeof setInterval> | null = null
  private redZoneHistory: Map<string, RedZoneAssessment[]> = new Map()
  private activeAlerts: Map<string, RedZoneAlert> = new Map()
  private lastPriorityById: Map<string, string> = new Map()
  private districtId = 'idukki'
  private lastError: string | null = null

  // Classification thresholds over the API's 0-100 operational risk score.
  private readonly RED_ZONE_THRESHOLDS = {
    risk_score: 80,           // immediate Red Zone consideration
    under_assessment: 60,     // elevated — monitoring + verification
    confidence_threshold: 0.6 // minimum confidence to escalate to candidate
  }

  private constructor() {}

  public static getInstance(): RedZoneDetectionService {
    if (!RedZoneDetectionService.instance) {
      RedZoneDetectionService.instance = new RedZoneDetectionService()
    }
    return RedZoneDetectionService.instance
  }

  // Start continuous monitoring
  startMonitoring(districtId: string = 'idukki', intervalMinutes: number = 5): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval)
    }
    this.districtId = districtId

    // Initial assessment
    this.assessRedZoneStatus(districtId)

    // Set up periodic monitoring
    this.monitoringInterval = setInterval(
      () => this.assessRedZoneStatus(districtId),
      intervalMinutes * 60 * 1000
    )

    console.log(`Red Zone monitoring started for ${districtId} every ${intervalMinutes} minutes`)
  }

  // Stop monitoring
  stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval)
      this.monitoringInterval = null
      console.log('Red Zone monitoring stopped')
    }
  }

  /** True when the last assessment cycle failed (API unreachable). */
  isDegraded(): boolean {
    return this.lastError !== null
  }

  getLastError(): string | null {
    return this.lastError
  }

  // Assess Red Zone status for all habitations in a district
  async assessRedZoneStatus(districtId: string = this.districtId): Promise<RedZoneAssessment[]> {
    try {
      // Real per-habitation risk scores from the backend risk engine.
      const response = await api.getRiskPriorities(districtId) as unknown as PrioritiesResponse
      if (!response?.habitations?.length) {
        throw new Error('Risk priorities response contained no habitations')
      }

      this.lastError = null
      const assessments = response.habitations.map(h => this.assessSingleHabitation(h))

      // Alerts are processed BEFORE the reading is pushed to history, so the
      // comparison baseline is the previous assessment's status — the correct
      // escalation semantics.
      assessments.forEach(assessment => {
        this.processRedZoneAlerts(assessment)
        this.updateRedZoneHistory(assessment)
      })

      return assessments
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      this.lastError = msg
      console.warn(`[Sentinel AI] Red Zone assessment failed, retaining last known state: ${msg}`)
      return []
    }
  }

  // Classify one habitation from backend-derived values
  private assessSingleHabitation(h: BackendHabitation): RedZoneAssessment {
    const riskScore = Number(h.risk_score) || 0
    const riskChange = Number(h.risk_change) || 0
    const baseline = riskScore - riskChange

    // Trend: prefer the engine's reported risk_change; corroborate with local
    // history once several readings exist.
    const historyTrend = this.calculateRiskTrend(h.id, riskScore)
    const apiTrend: 'increasing' | 'stable' | 'decreasing' =
      riskChange > 5 ? 'increasing' : riskChange < -5 ? 'decreasing' : 'stable'
    const riskTrend = historyTrend === 'stable' ? apiTrend : historyTrend

    const confidence = this.assessmentConfidence(h, riskScore, baseline)
    const status = this.determineRedZoneStatus(h.id, riskScore, riskTrend, confidence)
    const actions = this.generateRecommendedActions(status, h)
    const riskScoreHistory = this.getRiskScoreHistory(h.id)

    return {
      habitationId: h.id,
      habitationName: h.name,
      currentStatus: this.getCurrentRedZoneStatusFromHistory(h.id),
      recommendedStatus: status,
      riskTrend,
      riskScoreHistory: [...riskScoreHistory, { score: riskScore, timestamp: new Date().toISOString() }],
      source: {
        riskScore,
        baselineRisk: baseline,
        riskChange,
        priority: h.priority,
        dataStatus: h.data_status ?? 'DEMO',
      },
      confidence,
      recommendedActions: actions,
      validUntil: this.calculateValidityPeriod(status, riskTrend),
    }
  }

  // Determine Red Zone status from backend risk score + trend + confidence
  private determineRedZoneStatus(
    habitationId: string,
    riskScore: number,
    riskTrend: 'increasing' | 'stable' | 'decreasing',
    confidence: number
  ): RedZoneStatus {
    if (riskScore >= this.RED_ZONE_THRESHOLDS.risk_score &&
        confidence >= this.RED_ZONE_THRESHOLDS.confidence_threshold) {
      // Escalate to candidate when corroborated by a rising trend, persistent
      // high readings, or an engine IMMEDIATE classification.
      const engineImmediate = this.lastPriorityById.get(habitationId) === 'IMMEDIATE'
      if (riskTrend === 'increasing' || engineImmediate ||
          this.isPersistentHighRisk(habitationId, riskScore)) {
        return 'RED_ZONE_CANDIDATE'
      }
      return 'UNDER_ASSESSMENT'
    }

    if (riskScore >= this.RED_ZONE_THRESHOLDS.under_assessment) {
      return 'UNDER_ASSESSMENT'
    }

    return 'NOT_RECOMMENDED'
  }

  /**
   * Confidence in the classification, derived from provenance and the
   * separation of the score from the decision boundary — NOT from the score
   * being "close to 50" (the previous formula ironically trusted extreme
   * danger least).
   */
  private assessmentConfidence(h: BackendHabitation, riskScore: number, baseline: number): number {
    // Provenance: live data > validated demo seed > unknown.
    const provenance = h.data_status === 'LIVE' ? 1.0 : h.data_status === 'DEMO' ? 0.85 : 0.7

    // Distance from the nearest decision boundary (60 / 80): a score sitting
    // exactly on a threshold is inherently ambiguous.
    const boundaryDistance = Math.min(
      Math.abs(riskScore - this.RED_ZONE_THRESHOLDS.risk_score),
      Math.abs(riskScore - this.RED_ZONE_THRESHOLDS.under_assessment),
    )
    const decisiveness = Math.min(1, boundaryDistance / 20)

    // Movement the engine reports vs its own baseline: large movement is a
    // stronger, more explainable signal than a flat line.
    const movement = Math.min(1, Math.abs(riskScore - baseline) / 15)

    return Math.min(1, Math.max(0, 0.5 * decisiveness + 0.3 * movement + 0.2 * provenance))
  }

  // Check if risk has been persistently high
  private isPersistentHighRisk(habitationId: string, _currentScore: number): boolean {
    const history = this.redZoneHistory.get(habitationId) || []
    if (history.length < 3) return false // Need at least 3 readings

    const recent = history.slice(-3)
    const highRiskCount = recent.filter(a =>
      a.source.riskScore >= this.RED_ZONE_THRESHOLDS.risk_score
    ).length

    return highRiskCount >= 2 // At least 2 of last 3 readings high risk
  }

  // Calculate risk trend from historical data
  private calculateRiskTrend(habitationId: string, _currentScore: number):
    | 'increasing' | 'stable' | 'decreasing' {
    const history = this.redZoneHistory.get(habitationId) || []
    if (history.length < 2) return 'stable'

    const recent = history.slice(-Math.min(5, history.length))
    const first = recent[0].source.riskScore
    const last = recent[recent.length - 1].source.riskScore
    const change = last - first

    if (change > 5) return 'increasing'
    if (change < -5) return 'decreasing'
    return 'stable'
  }

  // Get risk score history for habitation
  private getRiskScoreHistory(habitationId: string): Array<{ score: number; timestamp: string }> {
    const history = this.redZoneHistory.get(habitationId) || []
    return history.map(a => ({
      score: a.source.riskScore,
      timestamp: a.validUntil
    })).slice(-10) // Last 10 readings
  }

  // Get current Red Zone status from history
  private getCurrentRedZoneStatusFromHistory(habitationId: string): RedZoneStatus {
    const history = this.redZoneHistory.get(habitationId) || []
    if (history.length === 0) return 'NOT_RECOMMENDED'
    return history[history.length - 1].recommendedStatus
  }

  // Update Red Zone history
  private updateRedZoneHistory(assessment: RedZoneAssessment): void {
    const history = this.redZoneHistory.get(assessment.habitationId) || []
    history.push(assessment)

    // Keep only last 50 assessments (about 4 hours at 5-min intervals)
    if (history.length > 50) {
      history.splice(0, history.length - 50)
    }

    this.redZoneHistory.set(assessment.habitationId, history)
    if (assessment.source.priority) {
      this.lastPriorityById.set(assessment.habitationId, assessment.source.priority)
    }
  }

  // Process and generate Red Zone alerts.
  // NOTE: called BEFORE updateRedZoneHistory, so "previous status" is the
  // last stored assessment's status — the correct escalation baseline.
  private processRedZoneAlerts(assessment: RedZoneAssessment): void {
    const { habitationId, habitationName, recommendedStatus, source, confidence, recommendedActions } = assessment
    const previousStatus = this.getCurrentRedZoneStatusFromHistory(habitationId)

    if (this.isStatusEscalated(previousStatus, recommendedStatus)) {
      const alert: RedZoneAlert = {
        id: `rz-${habitationId}-${Date.now()}`,
        habitationId,
        habitationName,
        redZoneStatus: recommendedStatus,
        riskScore: source.riskScore,
        confidence,
        triggers: this.identifyTriggers(assessment),
        detectedAt: new Date().toISOString(),
        expiresAt: this.calculateAlertExpiry(recommendedStatus),
        recommendedActions
      }

      this.activeAlerts.set(habitationId, alert)
      console.log(`🚨 RED ZONE ALERT: ${habitationName} (${habitationId}) - ${recommendedStatus} (Risk: ${source.riskScore})`)
    } else if (this.isStatusImproved(previousStatus, recommendedStatus) && this.activeAlerts.has(habitationId)) {
      this.activeAlerts.delete(habitationId)
      console.log(`✅ RED ZONE ALERT CLEARED: ${habitationName} (${habitationId})`)
    }
  }

  // Check if status has escalated (become more severe)
  private isStatusEscalated(oldStatus: RedZoneStatus, newStatus: RedZoneStatus): boolean {
    return (SEVERITY_ORDER[newStatus] || 0) > (SEVERITY_ORDER[oldStatus] || 0)
  }

  // Check if status has improved (become less severe)
  private isStatusImproved(oldStatus: RedZoneStatus, newStatus: RedZoneStatus): boolean {
    return this.isStatusEscalated(newStatus, oldStatus)
  }

  // Identify what triggered the Red Zone alert — backend-derived facts only
  private identifyTriggers(assessment: RedZoneAssessment): string[] {
    const triggers: string[] = []
    const { source, riskTrend, confidence } = assessment

    if (source.riskScore >= this.RED_ZONE_THRESHOLDS.risk_score)
      triggers.push(`Operational risk ${source.riskScore}/100 exceeds Red Zone threshold (${this.RED_ZONE_THRESHOLDS.risk_score})`)
    if (source.riskChange > 0)
      triggers.push(`Risk up ${source.riskChange} points from baseline ${source.baselineRisk} (engine-reported)`)
    if (source.priority === 'IMMEDIATE')
      triggers.push('Engine classifies relocation priority as IMMEDIATE (RPI)')
    if (riskTrend === 'increasing')
      triggers.push('Rising risk trend across recent readings')
    if (confidence >= 0.8)
      triggers.push(`High classification confidence (${Math.round(confidence * 100)}%)`)

    return triggers.length > 0 ? triggers : ['Threshold-based classification of engine risk score']
  }

  // Generate recommended actions based on status
  private generateRecommendedActions(status: RedZoneStatus, h: BackendHabitation): string[] {
    const actions: string[] = []

    switch (status) {
      case 'RED_ZONE_CANDIDATE':
        actions.push('Immediate field verification recommended')
        actions.push('Consider evacuation preparedness')
        actions.push('Deploy rapid assessment team')
        break
      case 'UNDER_ASSESSMENT':
        actions.push('Increase monitoring frequency to hourly')
        actions.push('Collect additional field data')
        actions.push('Prepare evacuation plans')
        break
      case 'NOT_RECOMMENDED':
        actions.push('Continue routine monitoring')
        break
      case 'DATA_INSUFFICIENT':
        actions.push('Deploy data collection teams')
        actions.push('Seek alternative data sources')
        break
    }

    // Hazard-specific follow-ups from the engine's primary hazard
    if (h.primary_hazard === 'LANDSLIDE') {
      actions.push('Monitor slope stability indicators and drainage')
    } else if (h.primary_hazard === 'FLOOD') {
      actions.push('Monitor river levels and flood defences')
    } else if (h.primary_hazard === 'CLOUDBURST') {
      actions.push('Issue weather alerts to the community')
    }

    return actions.slice(0, 5)
  }

  // Calculate how long the assessment is valid
  private calculateValidityPeriod(
    status: RedZoneStatus,
    riskTrend: 'increasing' | 'stable' | 'decreasing'
  ): string {
    let baseMinutes = 30 // Default 30 minutes

    switch (status) {
      case 'RED_ZONE_CANDIDATE':
        baseMinutes = riskTrend === 'increasing' ? 15 : 30
        break
      case 'UNDER_ASSESSMENT':
        baseMinutes = 60
        break
      case 'NOT_RECOMMENDED':
        baseMinutes = 240 // 4 hours
        break
      case 'DATA_INSUFFICIENT':
        baseMinutes = 15
        break
    }

    const validityDate = new Date(Date.now() + (baseMinutes * 60 * 1000))
    return validityDate.toISOString()
  }

  // Calculate when alert should expire
  private calculateAlertExpiry(status: RedZoneStatus): string {
    let hours = 1 // Default 1 hour

    switch (status) {
      case 'RED_ZONE_CANDIDATE':
        hours = 2
        break
      case 'UNDER_ASSESSMENT':
        hours = 4
        break
      case 'NOT_RECOMMENDED':
        hours = 12
        break
      case 'DATA_INSUFFICIENT':
        hours = 0.5 // 30 minutes
        break
    }

    const expiryDate = new Date(Date.now() + (hours * 60 * 60 * 1000))
    return expiryDate.toISOString()
  }

  // Get active Red Zone alerts
  getActiveAlerts(): RedZoneAlert[] {
    return Array.from(this.activeAlerts.values())
  }

  // Get Red Zone assessment history for a habitation
  getHabitationRedZoneHistory(habitationId: string): RedZoneAssessment[] {
    return this.redZoneHistory.get(habitationId) || []
  }
}

export default RedZoneDetectionService.getInstance()