import type { Health, Overview, Readiness } from '../types/api';
import { isHealth, isOverview, isReadiness } from './validation';

async function readJson<T>(
  path: string,
  validate: (value: unknown, status: number) => value is T,
  signal: AbortSignal,
  allowUnavailable = false,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(8000)]),
    headers: { Accept: 'application/json' },
  });
  if (!response.ok && !(allowUnavailable && response.status === 503)) {
    if (response.status === 403) throw new Error('Demo access is disabled or not permitted for this analyst.');
    if (response.status === 409) throw new Error('Demo data has not been seeded yet.');
    throw new Error(`The API returned HTTP ${response.status}.`);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error('The API returned an invalid response. Refresh to try again.');
  }
  if (!validate(body, response.status)) {
    throw new Error('The API returned an invalid response. Refresh to try again.');
  }
  return body;
}

export const getHealth = (signal: AbortSignal) => readJson<Health>('/health', isHealth, signal);
export const getReadiness = (signal: AbortSignal) => readJson<Readiness>('/health/ready', isReadiness, signal, true);
export const getOverview = (signal: AbortSignal) => readJson<Overview>('/demo/overview', isOverview, signal);
