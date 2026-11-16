import { useEffect, useState } from 'react';
import { getHealth, getOverview, getReadiness } from '../services/api';
import type { Health, Overview, Readiness } from '../types/api';

interface State {
  loading: boolean;
  health?: Health;
  readiness?: Readiness;
  overview?: Overview;
  error?: string;
}

const money = new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 2,
});
const time = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  hour12: false,
});

export default function App() {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<State>({ loading: true });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState({ loading: true });
      let health: Health | undefined;
      let readiness: Readiness | undefined;
      try {
        health = await getHealth(controller.signal);
        readiness = await getReadiness(controller.signal);
        if (readiness.status !== 'ready') {
          throw new Error(readiness.database === 'unavailable'
            ? 'Database unavailable. Start PostgreSQL, then refresh the connection.'
            : 'Database connected. Run the database migrations to prepare the workspace.');
        }
        const overview = await getOverview(controller.signal);
        if (!controller.signal.aborted) setState({ loading: false, health, readiness, overview });
      } catch (error) {
        if (!controller.signal.aborted) setState({
          loading: false, health, readiness,
          error: health && error instanceof Error
            ? error.message : 'API unavailable. Start the backend, then try again.',
        });
      }
    }
    void load();
    return () => controller.abort();
  }, [revision]);

  const { health, readiness, overview, loading, error } = state;
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="FraudSentinel home">
          <span className="brand-mark" aria-hidden="true">F<span> / </span>S</span>
          <span>Fraud<span className="brand-light">Sentinel</span></span>
        </a>
        <span className="environment"><span className="status-dot" />Development workspace</span>
      </header>

      <main>
        <div className="heading-row">
          <div>
            <p className="eyebrow">INVESTIGATION WORKSPACE <span>/</span> PHASE 01</p>
            <h1>A clear starting point.</h1>
            <p className="intro">Review the connection and explore your synthetic transaction data.</p>
          </div>
          <button type="button" disabled={loading} onClick={() => setRevision((value) => value + 1)}>
            <span aria-hidden="true">↻</span> {loading ? 'Checking connection…' : 'Refresh connection'}
          </button>
        </div>

        <section className="connection-panel" aria-labelledby="connection-title" aria-busy={loading}>
          <div className="panel-label">
            <h2 id="connection-title">System connection</h2>
            <span className="muted">Live service checks</span>
          </div>
          <div className="connection-grid" aria-live="polite">
            <div className="service">
              <span className={`service-indicator ${health ? 'online' : loading ? 'pending' : 'offline'}`} />
              <div><h3>Backend API</h3><p>{health ? 'Connected' : loading ? 'Checking…' : 'Unavailable'}</p></div>
              <span className="service-detail">{health ? `v${health.version}` : 'FastAPI'}</span>
            </div>
            <div className="service">
              <span className={`service-indicator ${readiness?.status === 'ready' ? 'online' : loading ? 'pending' : 'offline'}`} />
              <div><h3>Database</h3><p>{readiness?.status === 'ready' ? 'Connected · schema ready'
                : loading ? 'Checking…' : readiness?.database === 'connected' ? 'Migration required' : 'Unavailable'}</p></div>
              <span className="service-detail">PostgreSQL</span>
            </div>
          </div>
        </section>

        {error && <div className="notice error" role="alert"><strong>Workspace needs attention</strong><p>{error}</p></div>}

        <section className="metrics" aria-label="Workspace counts" aria-busy={loading}>
          <article><p>Transactions</p><strong data-testid="transaction-count">{overview?.transaction_count ?? '—'}</strong><span>Synthetic records in your cases</span></article>
          <article><p>Investigation cases</p><strong>{overview?.case_count ?? '—'}</strong><span>Assigned to the demo analyst</span></article>
          <article><p>Risk assessments</p><strong>{overview?.assessment_count ?? '—'}</strong><span>Detection begins in the next phase</span></article>
        </section>

        <section className="transactions-panel" aria-labelledby="transactions-title">
          <div className="section-heading"><div><p className="eyebrow">YOUR DATA</p><h2 id="transactions-title">Recent transactions</h2></div><span className="tag">Synthetic demo</span></div>
          {overview?.recent_transactions.length ? (
            <div className="table-scroll">
              <table>
                <caption className="sr-only">Recent synthetic transactions. All timestamps are in India Standard Time.</caption>
                <thead><tr><th>Transaction / customer</th><th>Time (IST)</th><th>Device</th><th className="amount">Amount</th><th>Review status</th></tr></thead>
                <tbody>{overview.recent_transactions.map((transaction) => (
                  <tr key={transaction.transaction_id}>
                    <td><strong className="mono">{transaction.transaction_id}</strong><span className="table-secondary">{transaction.customer_id}</span></td>
                    <td>{time.format(new Date(transaction.occurred_at))}</td>
                    <td className="mono device">{transaction.device_id.replace('device_demo_', '')}</td>
                    <td className="amount money">{money.format(Number(transaction.amount))}</td>
                    <td><span className="review-status">Not assessed</span></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : <div className="empty-state"><span aria-hidden="true">▤</span><h3>{loading ? 'Loading workspace…' : 'No transactions to display'}</h3><p>{error ? 'Resolve the connection above to load data from the backend.' : 'Run the synthetic seed to populate your development workspace.'}</p></div>}
          <div className="table-footer"><span>{overview ? `${overview.recent_transactions.length} of ${overview.transaction_count} records` : 'Waiting for data'}</span><span>All amounts in INR · All times in IST</span></div>
        </section>

        <aside className="foundation-note"><span className="note-icon" aria-hidden="true">i</span><div><h2>Built for investigation, with human judgment.</h2><p>This foundation uses synthetic records only. Detection, agent authorization, and evidence-linked reports are upcoming modules. A suspicious transaction is a review signal, never a confirmed fraud finding.</p></div></aside>
      </main>
      <footer><span>FraudSentinel <span className="footer-divider">/</span> Foundation 0.1.0</span><span>{overview?.analyst_name ?? 'Local development'} · Synthetic data only</span></footer>
    </div>
  );
}
