export interface Health {
  status: 'ok';
  service: string;
  version: string;
  timestamp: string;
}

export interface Readiness {
  status: 'ready' | 'not_ready';
  database: 'connected' | 'unavailable';
  schema_ready: boolean;
}

export interface Transaction {
  transaction_id: string;
  case_id: string;
  customer_id: string;
  amount: string;
  currency: string;
  occurred_at: string;
  device_id: string;
  beneficiary_id: string;
}

export interface Overview {
  mode: 'synthetic_demo';
  analyst_name: string;
  transaction_count: number;
  case_count: number;
  assessment_count: number;
  recent_transactions: Transaction[];
}
