export type Row = Record<string, unknown>;
export type Transaction = {
  transaction_id: string;
  case_id: string | null;
  source_account_id: string | null;
  destination_account_id: string | null;
  amount: string;
  currency: string;
  occurred_at: string;
  status: string;
  device_id: string | null;
  is_synthetic: boolean | null;
};
export type Factor = {
  code: string;
  description: string;
  contribution: string;
  source_transaction_ids: string[];
  review_guidance: string;
};
export type Assessment = {
  assessment_id: string;
  transaction_id: string;
  score: string;
  risk_category: string | null;
  factors: Factor[];
  missing_information: string[];
  ruleset_version: string;
  status: string;
  created_at: string;
};
export type Evidence = {
  evidence_id: string;
  transaction_id: string;
  case_id: string | null;
  assessment_id: string | null;
  account_id: string | null;
  description: string;
  kind: string;
  verification_status: string;
  captured_at: string;
  provenance: { source_reference: string; source_transaction_ids: string[] } | null;
};
export type Case = {
  case_id: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  version: number;
  assigned_to: string | null;
};
export type TimelineEvent = {
  event_id: string;
  case_id: string;
  kind: string;
  description: string;
  references: Row;
  created_at: string;
};
export type Account = { account_id: string; status: string; is_synthetic: boolean };
export type Graph = {
  root_account_id: string;
  nodes: { account_id: string; is_root: boolean }[];
  edges: {
    source: string;
    destination: string;
    transaction_count: number;
    transaction_ids: string[];
    relationship_type: string;
    explanation: string;
  }[];
  findings: {
    type: string;
    description: string;
    source_transaction_ids: string[];
    account_ids: string[];
  }[];
  truncated: boolean;
  limitations: string[];
};
export type Dashboard = {
  transaction_count: number;
  suspicious_count: number;
  open_investigations: number;
  risk_distribution: Record<string, number>;
  recent_high_risk: Transaction[];
  recent_activity: TimelineEvent[];
};
export type Report = {
  report_id: string;
  case_id: string;
  fingerprint: string;
  created_at: string;
  content: Row;
};
export type Detail = { transaction: Transaction; assessments: Assessment[]; evidence: Evidence[] };

const obj = (v: unknown): v is Row => typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown): v is string => typeof v === 'string';
const nullable = (v: unknown) => v === null || str(v);
const num = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;
const date = (v: unknown) => str(v) && Number.isFinite(Date.parse(v));
const money = (v: unknown) => str(v) && /^\d+(\.\d+)?$/.test(v) && Number.isFinite(Number(v));
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(str);
export const array =
  <T>(guard: (v: unknown) => v is T) =>
  (v: unknown): v is T[] =>
    Array.isArray(v) && v.length <= 100 && v.every(guard);
export const isTransaction = (v: unknown): v is Transaction =>
  obj(v) &&
  str(v.transaction_id) &&
  nullable(v.case_id) &&
  nullable(v.source_account_id) &&
  nullable(v.destination_account_id) &&
  money(v.amount) &&
  str(v.currency) &&
  /^[A-Z]{3}$/.test(v.currency) &&
  date(v.occurred_at) &&
  str(v.status) &&
  nullable(v.device_id) &&
  (v.is_synthetic === null || typeof v.is_synthetic === 'boolean');
const isFactor = (v: unknown): v is Factor =>
  obj(v) &&
  str(v.code) &&
  str(v.description) &&
  money(v.contribution) &&
  strings(v.source_transaction_ids) &&
  str(v.review_guidance);
export const isAssessment = (v: unknown): v is Assessment =>
  obj(v) &&
  str(v.assessment_id) &&
  str(v.transaction_id) &&
  money(v.score) &&
  Number(v.score) <= 100 &&
  nullable(v.risk_category) &&
  array(isFactor)(v.factors) &&
  strings(v.missing_information) &&
  str(v.ruleset_version) &&
  str(v.status) &&
  date(v.created_at);
export const isEvidence = (v: unknown): v is Evidence =>
  obj(v) &&
  str(v.evidence_id) &&
  str(v.transaction_id) &&
  nullable(v.case_id) &&
  nullable(v.assessment_id) &&
  nullable(v.account_id) &&
  str(v.description) &&
  str(v.kind) &&
  str(v.verification_status) &&
  date(v.captured_at) &&
  (v.provenance === null ||
    (obj(v.provenance) &&
      str(v.provenance.source_reference) &&
      strings(v.provenance.source_transaction_ids)));
export const isCase = (v: unknown): v is Case =>
  obj(v) &&
  str(v.case_id) &&
  str(v.title) &&
  str(v.description) &&
  str(v.priority) &&
  str(v.status) &&
  num(v.version) &&
  nullable(v.assigned_to);
export const isEvent = (v: unknown): v is TimelineEvent =>
  obj(v) &&
  str(v.event_id) &&
  str(v.case_id) &&
  str(v.kind) &&
  str(v.description) &&
  obj(v.references) &&
  date(v.created_at);
export const isAccount = (v: unknown): v is Account =>
  obj(v) && str(v.account_id) && str(v.status) && typeof v.is_synthetic === 'boolean';
export const isGraph = (v: unknown): v is Graph =>
  obj(v) &&
  str(v.root_account_id) &&
  Array.isArray(v.nodes) &&
  v.nodes.length <= 201 &&
  v.nodes.every((n) => obj(n) && str(n.account_id) && typeof n.is_root === 'boolean') &&
  Array.isArray(v.edges) &&
  v.edges.every(
    (e) =>
      obj(e) &&
      str(e.source) &&
      str(e.destination) &&
      num(e.transaction_count) &&
      strings(e.transaction_ids) &&
      str(e.relationship_type) &&
      str(e.explanation),
  ) &&
  Array.isArray(v.findings) &&
  v.findings.every(
    (f) =>
      obj(f) &&
      str(f.type) &&
      str(f.description) &&
      strings(f.source_transaction_ids) &&
      strings(f.account_ids),
  ) &&
  typeof v.truncated === 'boolean' &&
  strings(v.limitations);
export const isDashboard = (v: unknown): v is Dashboard =>
  obj(v) &&
  num(v.transaction_count) &&
  num(v.suspicious_count) &&
  num(v.open_investigations) &&
  obj(v.risk_distribution) &&
  ['low', 'medium', 'high', 'critical'].every((k) => num((v.risk_distribution as Row)[k])) &&
  array(isTransaction)(v.recent_high_risk) &&
  array(isEvent)(v.recent_activity);
export const isDetail = (v: unknown): v is Detail =>
  obj(v) &&
  isTransaction(v.transaction) &&
  array(isAssessment)(v.assessments) &&
  array(isEvidence)(v.evidence);
export const isReport = (v: unknown): v is Report =>
  obj(v) &&
  str(v.report_id) &&
  str(v.case_id) &&
  str(v.fingerprint) &&
  date(v.created_at) &&
  obj(v.content) &&
  obj(v.content.recorded_facts) &&
  obj(v.content.system_findings) &&
  Array.isArray(v.content.evidence) &&
  Array.isArray(v.content.timeline) &&
  Array.isArray(v.content.analyst_notes) &&
  strings(v.content.observations) &&
  strings(v.content.recommendations) &&
  strings(v.content.limitations);
export type ReportSummary = Pick<Report, 'report_id' | 'created_at' | 'fingerprint'>;
export const isReportSummary = (v: unknown): v is ReportSummary =>
  obj(v) && str(v.report_id) && date(v.created_at) && str(v.fingerprint);
export const isAnalysis = (v: unknown): v is { assessment: Assessment } =>
  obj(v) && isAssessment(v.assessment);
export const isCapabilities = (v: unknown): v is { enabled: boolean; message: string } =>
  obj(v) && typeof v.enabled === 'boolean' && str(v.message);

export async function api<T>(
  path: string,
  guard: (v: unknown) => v is T,
  method = 'GET',
  data?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const timeout = AbortSignal.timeout(15000);
  const response = await fetch(`/api/v1/intelligence${path}`, {
    method,
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: {
      Accept: 'application/json',
      ...(method === 'GET'
        ? {}
        : { 'Content-Type': 'application/json', 'X-FraudSentinel-Sandbox': 'synthetic-only' }),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    if (response.status === 403)
      throw new Error('Access refused. Use the explicitly enabled local synthetic sandbox.');
    if (response.status === 409)
      throw new Error(
        'Record conflict or invalid workflow transition. Refresh and check the case links or status.',
      );
    if (response.status === 422)
      throw new Error(
        'Invalid form values. Check identifiers, amounts, timestamps and required fields.',
      );
    throw new Error(`Request failed (HTTP ${response.status}). Refresh to retry.`);
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new Error('The investigation API returned an invalid response.');
  }
  if (!guard(value)) throw new Error('The investigation API returned an invalid response.');
  return value;
}
