export type Hook = "order-sign" | "order-select" | "appointment-book";
export type ScenarioKey = "pa-required" | "pa-not-required" | "auth-pending";
export type Disposition = "Granted" | "Denied" | "Pended";

export type SessionStatus =
  | "created"
  | "crd_complete"
  | "dtr_in_progress"
  | "dtr_complete"
  | "pas_reviewing"
  | "pas_submitted"
  | "granted"
  | "denied"
  | "pended";

export interface Session {
  id: string;
  hook: Hook;
  scenario_key: ScenarioKey;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
}

export interface SessionListItem extends Session {
  disposition: Disposition | null;
}

export interface Link {
  label: string;
  url: string;
  type: "absolute" | "smart";
  appContext?: string | null;
}

export interface CoverageInformation {
  coverage: { reference: string };
  covered: "covered" | "not-covered" | "conditional";
  "pa-needed": boolean;
  "doc-needed": "clinical" | "admin" | "patient" | "no";
  "doc-purpose"?: string[];
  "coverage-assertion-ids"?: string[];
  date: string;
}

export interface Card {
  summary: string;
  indicator: "info" | "warning" | "critical";
  source: { label: string; url?: string };
  detail?: string | null;
  links?: Link[];
  extension?: { "davinci-crd.coverage-information"?: CoverageInformation[] } | null;
}

export interface CRDResult {
  id: string;
  cards: Card[];
  pa_needed: boolean;
  smart_url: string | null;
  hook_request?: Record<string, unknown>;
  raw_response?: Record<string, unknown>;
}

export interface CreateSessionResponse {
  session: Session;
  crd_result: CRDResult;
}

export interface QuestionItem {
  linkId: string;
  text: string;
  type: "boolean" | "string" | "integer";
  required?: boolean;
}

export interface AnsweredItem {
  linkId: string;
  answer: Record<string, unknown>[];
}

export type QuestionnaireMode = "static" | "adaptive";

export interface QuestionnaireSession {
  id: string;
  questionnaire_url: string;
  questionnaire_json: { item: QuestionItem[]; [key: string]: unknown };
  mode: QuestionnaireMode;
  answered_items: AnsweredItem[];
  qr_reference: string | null;
  submitted_at: string | null;
}

export interface DTRStartResponse {
  mode: QuestionnaireMode;
  questions?: QuestionItem[];
  current_question?: QuestionItem | null;
  answered_count?: number;
}

export interface DTRState {
  mode: QuestionnaireMode;
  questions?: QuestionItem[];
  current_question?: QuestionItem | null;
  done?: boolean;
  answered_items: AnsweredItem[];
}

export interface DTRNextResponse {
  done: boolean;
  current_question: QuestionItem | null;
  answered_count: number;
}

export interface DTRSubmitResponse {
  qr_reference: string;
}

export interface PASBundle {
  resourceType: "Bundle";
  entry: { resource: Record<string, unknown> }[];
  [key: string]: unknown;
}

export interface PASBundleEdits {
  diagnosis_code?: string;
  service_code?: string;
  service_system?: string;
  quantity?: number;
  priority?: "normal" | "stat" | "deferred";
}

export interface PASSubmission {
  id: string;
  bundle_json: PASBundle;
  claim_response: Record<string, unknown> | null;
  disposition: Disposition | null;
  auth_number: string | null;
  submitted_at: string | null;
}

export interface PASResult {
  disposition: Disposition;
  auth_number: string | null;
  claim_response: Record<string, unknown>;
}

export interface SessionDetailResponse {
  session: Session;
  crd_result: CRDResult | null;
  questionnaire_session: QuestionnaireSession | null;
  pas_submission: PASSubmission | null;
}

export interface Scenario {
  key: ScenarioKey;
  code: string;
  system: string;
  display: string;
  expected_outcome: string;
}

export interface HookInfo {
  id: Hook;
  title: string;
  description: string;
}

export interface HealthStatus {
  fhir_reachable: boolean;
  sqlite_connected: boolean;
}
