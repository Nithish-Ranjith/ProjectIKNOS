// 
// TerraTrace — Canonical Type Definitions
// Every type matches exactly the PRD Section 7 case/parcel/evidence schemas
// and the Architecture Section 6 backend endpoint contract.
// When the real FastAPI backend replaces stubs, these types must NOT change.
// 

export type CaseStatus = 'open' | 'field_verification' | 'closed'
export type DecisionAction = 'approve' | 'reject' | 'escalate'
export type MutationStatus = 'pending' | 'approved' | 'none'
export type SpatialSource = 'cadastral' | 'drone_derived'
export type QualityFlag = 'PASS' | 'BLUR'

//  Core Data Objects 

export interface GeoJSONGeometry {
  type: 'Polygon' | 'MultiPolygon' | 'Point'
  coordinates: number[][][] | number[][]
}

export interface GeoJSONFeature {
  type: 'Feature'
  geometry: GeoJSONGeometry
  properties?: Record<string, unknown>
}

export interface TemporalSignal {
  instability_score: number   // 0–1
  onset_year: number | null
}

export interface AuditEntry {
  actor: string
  action: string
  timestamp: string
  reason?: string
}

export interface OfficerDecision {
  decision: DecisionAction
  decided_by: string
  decided_at: string
  reason: string
}

// PRD Section 7 — Case Object (exact shape)
export interface Case {
  case_id: string
  parcel_id: string
  spatial_mismatch_pct: number
  boundary_shift_m: number
  registration_conflict: boolean
  mutation_status: MutationStatus
  temporal_signal: TemporalSignal
  confidence_score: number          // 0–100
  action: string
  status: CaseStatus
  audit_trail: AuditEntry[]
  evidence_refs: string[]
  officer_decision?: OfficerDecision
  // Extra fields that come from joined DB query
  village?: string
  district?: string
  owner_name?: string
  assigned_surveyor_id?: string
  created_at?: string
}

// PRD Section 7 — Parcel Object
export interface Parcel {
  parcel_id: string
  source: SpatialSource
  area_sqm: number
  last_updated: string
  geom?: GeoJSONGeometry
  // Joined fields from ror table
  owner_name?: string
  khasra_no?: string
  village?: string
  district?: string
}

export interface RoR {
  parcel_id: string
  owner_name: string
  khasra_no: string
  area_recorded: number
  record_date: string
}

export interface Mutation {
  parcel_id: string
  mutation_status: MutationStatus
  mutation_date: string
}

//  Geometry Layers (Architecture 4.3 — EvidenceMap) 
// Returned by GET /cases/:id/geometry-layers
// U-Net output is slotted here when the ML model is integrated.
export interface GeometryLayers {
  cadastral: GeoJSONFeature | null
  ai_boundary: GeoJSONFeature | null       // STUB: null until U-Net endpoint live
  drone_coverage: GeoJSONFeature | null    // STUB: null until mission images processed
  discrepancy: {
    area_diff_pct: number
    boundary_shift_m: number
  } | null
}

//  Evidence Bundle (Architecture 4.3 — EvidenceTabs) 
// Returned by GET /cases/:id/evidence
export interface EvidenceBundle {
  spatial: {
    cadastral_area_sqm: number
    drone_area_sqm: number | null
    area_diff_pct: number
    boundary_shift_m: number
    registration_conflict: boolean
  }
  temporal: {
    instability_score: number
    onset_year: number | null
    ndvi_series_uri: string | null   // link to Sentinel-2 derived NDVI chart
  }
  records: {
    ror: RoR | null
    mutation: Mutation | null
    registration_deed_present: boolean
  }
}

//  Reasoning Trace (Architecture 4.3 — ReasoningTrace) 
// Returned by GET /cases/:id/reasoning
export interface ReasoningRule {
  rule_id: string
  description: string
  weight: number
  input_value: number | boolean
  score_contribution: number
  passed: boolean
}

export interface ReasoningTrace {
  total_score: number
  rules: ReasoningRule[]
}

//  API Response Wrappers 
export interface PaginatedCases {
  cases: Case[]
  total: number
  page: number
  per_page: number
}

export interface DashboardStats {
  open_cases: number
  sla_breaches: number
  avg_resolution_days: number
  cases_this_week: number
}

//  Decision Payload 
export interface DecisionPayload {
  decision: DecisionAction
  reason: string
  decided_by: string   // user email or ID, from Supabase session
}

//  Surveyor Assignment 
export interface Surveyor {
  id: string
  name: string
  email: string
  dgca_credential?: string
  assigned_case_count: number
}

//  Grievance 
export interface GrievancePayload {
  parcel_id: string
  submitted_by: string
  text: string
  photo_uris?: string[]
}
