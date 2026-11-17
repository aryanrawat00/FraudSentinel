import type { Health, Overview, Readiness, Transaction } from '../types/api';

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isTimestamp(value: unknown): value is string {
  return typeof value === 'string'
    && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

export function isHealth(value: unknown): value is Health {
  return isObject(value) && value.status === 'ok' && value.service === 'fraudsentinel-api'
    && isText(value.version) && isTimestamp(value.timestamp);
}

export function isReadiness(value: unknown, status: number): value is Readiness {
  if (!isObject(value)) return false;
  if (status === 200) {
    return value.status === 'ready' && value.database === 'connected' && value.schema_ready === true;
  }
  return status === 503 && value.status === 'not_ready' && value.schema_ready === false
    && (value.database === 'connected' || value.database === 'unavailable');
}

function isTransaction(value: unknown): value is Transaction {
  return isObject(value)
    && isText(value.transaction_id) && isText(value.case_id) && isText(value.customer_id)
    && typeof value.amount === 'string' && /^\d+(?:\.\d{1,2})?$/.test(value.amount)
    && Number.isFinite(Number(value.amount)) && Number(value.amount) > 0
    && typeof value.currency === 'string' && /^[A-Z]{3}$/.test(value.currency)
    && isTimestamp(value.occurred_at) && isText(value.device_id) && isText(value.beneficiary_id);
}

export function isOverview(value: unknown): value is Overview {
  return isObject(value) && value.mode === 'synthetic_demo' && isText(value.analyst_name)
    && isCount(value.transaction_count) && isCount(value.case_count) && isCount(value.assessment_count)
    && Array.isArray(value.recent_transactions) && value.recent_transactions.every(isTransaction);
}
