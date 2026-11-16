import type { Health, Overview, Readiness } from '../types/api';

async function readJson<T>(path: string, signal: AbortSignal, allowUnavailable = false): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(8000)]),
    headers: { Accept: 'application/json' },
  });
  if (!response.ok && !(allowUnavailable && response.status === 503)) {
    if (response.status === 403) throw new Error('Demo access is disabled on this server.');
    if (response.status === 409) throw new Error('Demo data has not been seeded yet.');
    throw new Error(`The API returned HTTP ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export const getHealth = (signal: AbortSignal) => readJson<Health>('/health', signal);
export const getReadiness = (signal: AbortSignal) => readJson<Readiness>('/health/ready', signal, true);
export const getOverview = (signal: AbortSignal) => readJson<Overview>('/demo/overview', signal);
