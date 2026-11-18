import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  api,
  array,
  isAccount,
  isAnalysis,
  isCapabilities,
  isCase,
  isDashboard,
  isDetail,
  isEvent,
  isEvidence,
  isGraph,
  isReport,
  isReportSummary,
  isTransaction,
  type Account,
  type Case,
  type Dashboard,
  type Detail,
  type Evidence,
  type Graph,
  type Report,
  type ReportSummary,
  type TimelineEvent,
  type Transaction,
} from '../services/intelligence';

const stamp = (v: string) => new Date(v).toLocaleString('en-IN', { timeZone: 'UTC' }) + ' UTC';
const amount = (t: Transaction) => `${t.currency} ${t.amount}`;
const ids = (value: FormDataEntryValue | null) =>
  String(value ?? '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
const transitions: Record<string, string[]> = {
  open: ['under_investigation', 'closed'],
  under_investigation: ['pending_review'],
  pending_review: ['under_investigation', 'resolved'],
  resolved: ['under_investigation', 'closed'],
  closed: [],
};

function EvidenceTable({ rows }: { rows: Evidence[] }) {
  return rows.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Evidence / type</th>
            <th>Description & sources</th>
            <th>Associations</th>
            <th>Captured</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.evidence_id}>
              <td>
                {e.evidence_id}
                <small>
                  {e.kind} · {e.verification_status}
                </small>
              </td>
              <td>
                {e.description}
                <small>{e.provenance?.source_reference ?? 'Legacy provenance unavailable'}</small>
                <small>{e.provenance?.source_transaction_ids.join(', ')}</small>
              </td>
              <td>
                {e.transaction_id}
                <small>
                  Case: {e.case_id ?? 'Unassigned'} · Account: {e.account_id ?? 'Unavailable'}
                </small>
              </td>
              <td>{stamp(e.captured_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <p className="empty-state">No evidence records in this selection.</p>
  );
}

function Network({ graph, select }: { graph: Graph; select: (id: string) => void }) {
  const shown = graph.nodes.slice(0, 20);
  const points = new Map(
    shown.map((node, i) => [
      node.account_id,
      {
        x: 250 + 180 * Math.cos((2 * Math.PI * i) / shown.length),
        y: 200 + 150 * Math.sin((2 * Math.PI * i) / shown.length),
      },
    ]),
  );
  return (
    <>
      <svg
        viewBox="0 0 500 400"
        role="img"
        aria-label="Directed recorded transaction connections"
        className="account-graph"
      >
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="18" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8" fill="#64877b" />
          </marker>
        </defs>
        {graph.edges.map((e) => {
          const a = points.get(e.source),
            b = points.get(e.destination);
          return a && b ? (
            <line
              key={`${e.source}-${e.destination}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#64877b"
              markerEnd="url(#arrow)"
            />
          ) : null;
        })}
        {shown.map((n) => {
          const p = points.get(n.account_id)!;
          return (
            <g key={n.account_id}>
              <circle cx={p.x} cy={p.y} r="12" fill={n.is_root ? '#b87c36' : '#285c52'} />
              <text x={p.x} y={p.y + 28} textAnchor="middle" fontSize="10">
                {n.account_id.slice(-22)}
              </text>
            </g>
          );
        })}
      </svg>
      <p>
        Arrows follow recorded sender → receiver references. Up to 20 nodes drawn; all returned
        connections are listed below.
      </p>
      <div className="actions">
        {graph.nodes.map((n) => (
          <button key={n.account_id} onClick={() => select(n.account_id)}>
            {n.account_id}
          </button>
        ))}
      </div>
      {graph.truncated && (
        <p role="status">
          The graph reached its analysis bound. Narrow the window or choose another root.
        </p>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Sender → receiver</th>
              <th>Count</th>
              <th>Source transactions</th>
            </tr>
          </thead>
          <tbody>
            {graph.edges.map((e) => (
              <tr key={`${e.source}-${e.destination}`}>
                <td>
                  {e.source} → {e.destination}
                  <small>{e.explanation}</small>
                </td>
                <td>{e.transaction_count}</td>
                <td>{e.transaction_ids.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {graph.findings.map((f, i) => (
        <article className="finding" key={i}>
          <h3>{f.type.replaceAll('_', ' ')}</h3>
          <p>{f.description}</p>
          <small>Sources: {f.source_transaction_ids.join(', ')}</small>
        </article>
      ))}
      {graph.limitations.map((v) => (
        <p key={v} className="muted">
          {v}
        </p>
      ))}
    </>
  );
}

export default function InvestigationWorkspace() {
  const [cap, setCap] = useState<{ enabled: boolean; message: string }>();
  const [tab, setTab] = useState('Dashboard');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [detail, setDetail] = useState<Detail>();
  const [graph, setGraph] = useState<Graph>();
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState<Case>();
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [report, setReport] = useState<Report>();
  const [savedReports, setSavedReports] = useState<ReportSummary[]>([]);
  const [caseTransactions, setCaseTransactions] = useState<Transaction[]>([]);
  const [caseEvidence, setCaseEvidence] = useState<Evidence[]>([]);
  const [offset, setOffset] = useState(0);
  const [caseSource, setCaseSource] = useState('');
  const [caseAccount, setCaseAccount] = useState('');
  const pending = useRef(0);

  async function run(action: () => Promise<void>, message = '') {
    pending.current += 1;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
      setNotice(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed. Please retry.');
    } finally {
      pending.current -= 1;
      setBusy(pending.current > 0);
    }
  }
  async function load(name = tab, start = offset) {
    if (name === 'Dashboard') setDashboard(await api('/dashboard', isDashboard));
    if (name === 'Transactions') {
      const [t, a] = await Promise.all([
        api(`/transactions?limit=25&offset=${start}`, array(isTransaction)),
        api('/accounts?limit=100', array(isAccount)),
      ]);
      setTransactions(t);
      setAccounts(a);
    }
    if (name === 'Relationships') setAccounts(await api('/accounts?limit=100', array(isAccount)));
    if (name === 'Evidence')
      setEvidence(await api(`/evidence?limit=25&offset=${start}`, array(isEvidence)));
    if (name === 'Cases') setCases(await api(`/cases?limit=25&offset=${start}`, array(isCase)));
  }
  async function viewTransaction(id: string) {
    setDetail(undefined);
    setDetail(await api(`/transactions/${encodeURIComponent(id)}`, isDetail));
  }
  async function viewCase(id: string) {
    const [c, t, r, tx, ev] = await Promise.all([
      api(`/cases/${encodeURIComponent(id)}`, isCase),
      api(`/cases/${encodeURIComponent(id)}/timeline?limit=100`, array(isEvent)),
      api(`/cases/${encodeURIComponent(id)}/reports`, array(isReportSummary)),
      api(`/cases/${encodeURIComponent(id)}/transactions?limit=100`, array(isTransaction)),
      api(`/evidence?case_id=${encodeURIComponent(id)}&limit=100`, array(isEvidence)),
    ]);
    setSelected(c);
    setTimeline(t);
    setSavedReports(r);
    setCaseTransactions(tx);
    setCaseEvidence(ev);
    setReport(undefined);
  }
  async function viewGraph(id: string) {
    setGraph(undefined);
    setGraph(
      await api(`/accounts/${encodeURIComponent(id)}/relationships?depth=3&limit=100`, isGraph),
    );
  }
  useEffect(() => {
    const c = new AbortController();
    api('/capabilities', isCapabilities, 'GET', undefined, c.signal)
      .then(setCap)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, []);
  useEffect(() => {
    if (cap?.enabled) void run(() => load(tab, offset));
  }, [cap?.enabled, tab, offset]);
  const submit = (event: FormEvent<HTMLFormElement>, action: (data: FormData) => Promise<void>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void run(async () => {
      await action(data);
      form.reset();
    }, 'Saved successfully.');
  };
  return (
    <main className="investigation-workspace">
      <div className="heading-row">
        <div>
          <p className="eyebrow">FRAUD INTELLIGENCE / SYNTHETIC SANDBOX</p>
          <h1>Investigate the evidence.</h1>
          <p className="intro">
            Explainable signals, recorded connections, and traceable investigation history.
          </p>
        </div>
        <button disabled={busy || !cap?.enabled} onClick={() => void run(() => load())}>
          Refresh investigation data
        </button>
      </div>
      {!cap && !error && <p role="status">Checking investigation availability…</p>}
      {cap && <p className="notice">{cap.message} Scores guide review and never confirm fraud.</p>}
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {cap?.enabled && (
        <>
          <nav className="workspace-tabs" aria-label="Investigation sections">
            {['Dashboard', 'Transactions', 'Relationships', 'Evidence', 'Cases'].map((name) => (
              <button
                key={name}
                disabled={busy}
                aria-pressed={tab === name}
                onClick={() => {
                  setTab(name);
                  setOffset(0);
                  setDetail(undefined);
                }}
              >
                {name}
              </button>
            ))}
          </nav>
          <fieldset className="workspace-content" disabled={busy} aria-busy={busy}>
            {busy && <p role="status">Loading investigation data…</p>}
            {tab === 'Dashboard' && dashboard && (
              <>
                <section className="metrics">
                  <article>
                    <p>Total transactions</p>
                    <strong>{dashboard.transaction_count}</strong>
                    <span>Stored records in this dataset</span>
                  </article>
                  <article>
                    <p>Suspicious transactions</p>
                    <strong>{dashboard.suspicious_count}</strong>
                    <span>Latest high / critical assessment</span>
                  </article>
                  <article>
                    <p>Open investigations</p>
                    <strong>{dashboard.open_investigations}</strong>
                    <span>Cases not closed</span>
                  </article>
                </section>
                <section className="workspace-panel">
                  <h2>Risk distribution</h2>
                  <div className="risk-distribution">
                    {Object.entries(dashboard.risk_distribution).map(([key, value]) => (
                      <p key={key}>
                        <span className={`risk ${key}`}>{key}</span> {value}
                      </p>
                    ))}
                  </div>
                  <h2>Recent high-risk activity</h2>
                  {dashboard.recent_high_risk.length ? (
                    dashboard.recent_high_risk.map((t) => (
                      <button
                        key={t.transaction_id}
                        onClick={() => {
                          setTab('Transactions');
                          void run(() => viewTransaction(t.transaction_id));
                        }}
                      >
                        {t.transaction_id} · {amount(t)}
                      </button>
                    ))
                  ) : (
                    <p>No high-risk assessments recorded.</p>
                  )}
                  <h2>Recent investigation activity</h2>
                  {dashboard.recent_activity.length ? (
                    dashboard.recent_activity.map((e) => (
                      <p key={e.event_id}>
                        {stamp(e.created_at)} · {e.kind.replaceAll('_', ' ')} · {e.case_id}
                      </p>
                    ))
                  ) : (
                    <p>No investigation activity recorded.</p>
                  )}
                </section>
              </>
            )}
            {tab === 'Transactions' && (
              <>
                <section className="workspace-panel">
                  <h2>Stored transactions</h2>
                  {transactions.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Transaction</th>
                            <th>Accounts</th>
                            <th>Amount / time</th>
                            <th>State</th>
                          </tr>
                        </thead>
                        <tbody>
                          {transactions.map((t) => (
                            <tr key={t.transaction_id}>
                              <td>
                                <button
                                  onClick={() => void run(() => viewTransaction(t.transaction_id))}
                                >
                                  {t.transaction_id}
                                </button>
                                <small>
                                  {t.is_synthetic ? 'Synthetic' : 'Legacy / unknown provenance'}
                                </small>
                              </td>
                              <td>
                                {t.source_account_id ?? 'Source unavailable'} →{' '}
                                {t.destination_account_id ?? 'Receiver unavailable'}
                              </td>
                              <td>
                                {amount(t)}
                                <small>{stamp(t.occurred_at)}</small>
                              </td>
                              <td>
                                {t.status}
                                <small>{t.case_id ?? 'No case'}</small>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p>No transactions in this selection.</p>
                  )}
                </section>
                {detail && (
                  <section className="workspace-panel" aria-label="Transaction analysis">
                    <h2>Analysis: {detail.transaction.transaction_id}</h2>
                    <p>
                      {amount(detail.transaction)} · {stamp(detail.transaction.occurred_at)} ·
                      Device: {detail.transaction.device_id ?? 'Unavailable'}
                    </p>
                    <div className="actions">
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            await api(
                              `/transactions/${detail.transaction.transaction_id}/analyze`,
                              isAnalysis,
                              'POST',
                            );
                            await viewTransaction(detail.transaction.transaction_id);
                          }, 'Assessment saved; identical inputs reuse the existing result.')
                        }
                      >
                        Analyze transaction
                      </button>
                      <button
                        onClick={() => {
                          setCaseSource(detail.transaction.transaction_id);
                          setTab('Cases');
                        }}
                      >
                        Create investigation from transaction
                      </button>
                    </div>
                    {detail.assessments.length === 0 && (
                      <p>Not assessed. No risk score has been invented.</p>
                    )}
                    {detail.assessments.map((a) => (
                      <article key={a.assessment_id} className="finding">
                        <h3>
                          <span className={`risk ${a.risk_category}`}>
                            {a.risk_category ?? 'Unknown'}
                          </span>{' '}
                          {a.score} / 100
                        </h3>
                        <p>
                          {a.ruleset_version} · {a.status} · {stamp(a.created_at)}
                        </p>
                        {a.factors.map((f) => (
                          <div key={f.code}>
                            <h4>
                              {f.code} · +{f.contribution}
                            </h4>
                            <p>{f.description}</p>
                            <small>Sources: {f.source_transaction_ids.join(', ')}</small>
                            <p>{f.review_guidance}</p>
                          </div>
                        ))}
                        {a.missing_information.map((m) => (
                          <p key={m}>{m}</p>
                        ))}
                        <button
                          disabled={busy}
                          onClick={() =>
                            void run(async () => {
                              await api(
                                `/assessments/${a.assessment_id}/evidence`,
                                array(isEvidence),
                                'POST',
                              );
                              await viewTransaction(detail.transaction.transaction_id);
                            }, 'Evidence collected from recorded factors.')
                          }
                        >
                          Collect evidence
                        </button>
                      </article>
                    ))}
                    <h3>Supporting evidence</h3>
                    <EvidenceTable rows={detail.evidence} />
                  </section>
                )}
                <details className="workspace-panel">
                  <summary>Ingest a synthetic transaction</summary>
                  <form
                    onSubmit={(e) =>
                      submit(e, async (d) => {
                        await api('/transactions', isTransaction, 'POST', {
                          transaction_id: d.get('transaction_id'),
                          source_account_id: d.get('source'),
                          destination_account_id: d.get('destination'),
                          amount: d.get('amount'),
                          currency: d.get('currency'),
                          occurred_at: new Date(String(d.get('time')) + 'Z').toISOString(),
                          transaction_type: 'transfer',
                          status: 'completed',
                          data_source: 'manual_synthetic_sandbox',
                          is_synthetic: true,
                          device_id: d.get('device') || null,
                        });
                        await load();
                      })
                    }
                  >
                    <label>
                      Transaction ID
                      <input
                        name="transaction_id"
                        required
                        pattern="[A-Za-z0-9][A-Za-z0-9_.:-]*"
                        maxLength={64}
                      />
                    </label>
                    <label>
                      Sender
                      <select name="source" required>
                        <option value="">Select account</option>
                        {accounts.map((a) => (
                          <option key={a.account_id}>{a.account_id}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Receiver
                      <select name="destination" required>
                        <option value="">Select account</option>
                        {accounts.map((a) => (
                          <option key={a.account_id}>{a.account_id}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Amount
                      <input
                        name="amount"
                        required
                        pattern="[0-9]+(\.[0-9]{1,2})?"
                        inputMode="decimal"
                      />
                    </label>
                    <label>
                      Currency
                      <input
                        name="currency"
                        required
                        pattern="[A-Z]{3}"
                        maxLength={3}
                        defaultValue="INR"
                      />
                    </label>
                    <label>
                      Occurred at (UTC)
                      <input name="time" type="datetime-local" required />
                    </label>
                    <label>
                      Device ID (optional)
                      <input name="device" maxLength={64} />
                    </label>
                    <button disabled={busy}>Ingest synthetic transaction</button>
                  </form>
                </details>
              </>
            )}
            {tab === 'Relationships' && (
              <section className="workspace-panel">
                <h2>Account relationships</h2>
                <label>
                  Root account
                  <select
                    aria-label="Root account"
                    value={graph?.root_account_id ?? ''}
                    onChange={(e) => void run(() => viewGraph(e.target.value))}
                  >
                    <option value="">Choose an account</option>
                    {accounts.map((a) => (
                      <option key={a.account_id}>{a.account_id}</option>
                    ))}
                  </select>
                </label>
                {graph ? (
                  <>
                    <Network graph={graph} select={(id) => void run(() => viewGraph(id))} />
                    <button
                      onClick={() => {
                        setCaseAccount(graph.root_account_id);
                        setCaseSource(
                          [...new Set(graph.edges.flatMap((edge) => edge.transaction_ids))].join(
                            ', ',
                          ),
                        );
                        setTab('Cases');
                      }}
                    >
                      Open investigation for this account
                    </button>
                  </>
                ) : (
                  <p>Choose a stored account to inspect recorded connections.</p>
                )}
                <details>
                  <summary>Add a synthetic account reference</summary>
                  <form
                    onSubmit={(e) =>
                      submit(e, async (d) => {
                        await api('/accounts', isAccount, 'POST', {
                          account_id: d.get('account_id'),
                          status: 'active',
                          data_source: 'manual_synthetic_sandbox',
                          is_synthetic: true,
                        });
                        await load();
                      })
                    }
                  >
                    <label>
                      Account ID
                      <input name="account_id" required maxLength={64} />
                    </label>
                    <button disabled={busy}>Add synthetic account</button>
                  </form>
                </details>
              </section>
            )}
            {tab === 'Evidence' && (
              <section className="workspace-panel">
                <h2>Evidence register</h2>
                <form
                  className="inline-form"
                  onSubmit={(e) =>
                    submit(e, async (d) => {
                      const q = new URLSearchParams();
                      if (d.get('case')) q.set('case_id', String(d.get('case')));
                      if (d.get('transaction'))
                        q.set('transaction_id', String(d.get('transaction')));
                      setEvidence(await api(`/evidence?${q}`, array(isEvidence)));
                    })
                  }
                >
                  <label>
                    Case filter
                    <input name="case" />
                  </label>
                  <label>
                    Transaction filter
                    <input name="transaction" />
                  </label>
                  <button disabled={busy}>Filter evidence</button>
                </form>
                <EvidenceTable rows={evidence} />
              </section>
            )}
            {tab === 'Cases' && (
              <>
                <section className="workspace-panel">
                  <h2>Investigations</h2>
                  {cases.length ? (
                    cases.map((c) => (
                      <button
                        className="case-row"
                        key={c.case_id}
                        onClick={() => void run(() => viewCase(c.case_id))}
                      >
                        {c.title}{' '}
                        <span>
                          {c.status.replaceAll('_', ' ')} · {c.priority}
                        </span>
                      </button>
                    ))
                  ) : (
                    <p>No cases in this selection.</p>
                  )}
                  <details open={!!caseSource || !!caseAccount}>
                    <summary>Create investigation</summary>
                    <form
                      onSubmit={(e) =>
                        submit(e, async (d) => {
                          const c = await api('/cases', isCase, 'POST', {
                            case_id: `case_${crypto.randomUUID().replaceAll('-', '')}`,
                            title: d.get('title'),
                            description: d.get('description'),
                            priority: d.get('priority'),
                            transaction_ids: ids(d.get('transactions')),
                            account_ids: ids(d.get('accounts')),
                          });
                          setCaseSource('');
                          setCaseAccount('');
                          await load();
                          await viewCase(c.case_id);
                        })
                      }
                    >
                      <label>
                        Case title
                        <input name="title" required maxLength={200} />
                      </label>
                      <label>
                        Description
                        <textarea name="description" maxLength={5000} />
                      </label>
                      <label>
                        Priority
                        <select name="priority">
                          <option>medium</option>
                          <option>low</option>
                          <option>high</option>
                          <option>urgent</option>
                        </select>
                      </label>
                      <label>
                        Transaction IDs (comma separated)
                        <input name="transactions" key={caseSource} defaultValue={caseSource} />
                      </label>
                      <label>
                        Account IDs (comma separated)
                        <input name="accounts" key={caseAccount} defaultValue={caseAccount} />
                      </label>
                      <button disabled={busy}>Create case</button>
                    </form>
                  </details>
                </section>
                {selected && (
                  <section className="workspace-panel" aria-label="Case details">
                    <h2>{selected.title}</h2>
                    <p>
                      {selected.case_id} · {selected.status.replaceAll('_', ' ')} · Version{' '}
                      {selected.version}
                    </p>
                    <p>{selected.description || 'No description recorded.'}</p>
                    {selected.status !== 'closed' && (
                      <>
                        <form
                          key={`${selected.case_id}-${selected.version}`}
                          onSubmit={(e) =>
                            submit(e, async (d) => {
                              await api(`/cases/${selected.case_id}`, isCase, 'PATCH', {
                                expected_version: selected.version,
                                title: d.get('title'),
                                description: d.get('description'),
                                status: d.get('status'),
                                priority: d.get('priority'),
                                assigned_to:
                                  d.get('assign') === 'self' ? 'user_demo_analyst' : null,
                              });
                              await viewCase(selected.case_id);
                              await load();
                            })
                          }
                        >
                          <label>
                            Update title
                            <input
                              name="title"
                              required
                              maxLength={200}
                              defaultValue={selected.title}
                            />
                          </label>
                          <label>
                            Update description
                            <textarea
                              name="description"
                              maxLength={5000}
                              defaultValue={selected.description}
                            />
                          </label>
                          <label>
                            Case status
                            <select
                              aria-label="Case status"
                              name="status"
                              defaultValue={selected.status}
                            >
                              <option value={selected.status}>
                                {selected.status.replaceAll('_', ' ')}
                              </option>
                              {(transitions[selected.status] ?? []).map((s) => (
                                <option key={s} value={s}>
                                  {s.replaceAll('_', ' ')}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Update priority
                            <select name="priority" defaultValue={selected.priority}>
                              {['low', 'medium', 'high', 'urgent'].map((p) => (
                                <option key={p}>{p}</option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Assigned investigator
                            <select name="assign" defaultValue={selected.assigned_to ? 'self' : ''}>
                              <option value="">Unassigned</option>
                              <option value="self">Current demo investigator</option>
                            </select>
                          </label>
                          <button disabled={busy}>Save case changes</button>
                        </form>
                        <form
                          onSubmit={(e) =>
                            submit(e, async (d) => {
                              await api(`/cases/${selected.case_id}/notes`, isEvent, 'POST', {
                                text: d.get('note'),
                              });
                              await viewCase(selected.case_id);
                            })
                          }
                        >
                          <label>
                            Investigation note
                            <textarea name="note" required maxLength={5000} />
                          </label>
                          <button disabled={busy}>Add analyst note</button>
                        </form>
                        <form
                          onSubmit={(e) =>
                            submit(e, async (d) => {
                              await api(`/cases/${selected.case_id}/links`, isCase, 'POST', {
                                transaction_ids: ids(d.get('transactions')),
                                assessment_ids: ids(d.get('assessments')),
                                evidence_ids: ids(d.get('evidence')),
                                account_ids: ids(d.get('accounts')),
                              });
                              await viewCase(selected.case_id);
                            })
                          }
                        >
                          <label>
                            Link transaction IDs
                            <input name="transactions" />
                          </label>
                          <label>
                            Link assessment IDs
                            <input name="assessments" />
                          </label>
                          <label>
                            Link evidence IDs
                            <input name="evidence" />
                          </label>
                          <label>
                            Link account IDs
                            <input name="accounts" />
                          </label>
                          <button disabled={busy}>Link records</button>
                        </form>
                      </>
                    )}
                    <h3>Investigation timeline</h3>
                    {timeline.length ? (
                      <ol className="timeline">
                        {timeline.map((t) => (
                          <li key={t.event_id}>
                            <strong>{t.kind.replaceAll('_', ' ')}</strong> · {stamp(t.created_at)}
                            <p>{t.description}</p>
                            <small>{JSON.stringify(t.references)}</small>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p>No detailed events recorded; this case may predate workflow activation.</p>
                    )}
                    <h3>Linked transactions (up to 100)</h3>
                    {caseTransactions.map((tx) => (
                      <p key={tx.transaction_id}>
                        {tx.transaction_id} · {amount(tx)}
                      </p>
                    ))}
                    <h3>Case evidence (up to 100)</h3>
                    <EvidenceTable rows={caseEvidence} />
                    <h3>Saved reports (latest 25)</h3>
                    {savedReports.length ? (
                      savedReports.map((saved) => (
                        <button
                          key={saved.report_id}
                          onClick={() =>
                            void run(async () => {
                              setReport(
                                await api(
                                  `/cases/${selected.case_id}/reports/${saved.report_id}`,
                                  isReport,
                                ),
                              );
                            })
                          }
                        >
                          View saved report · {stamp(saved.created_at)}
                        </button>
                      ))
                    ) : (
                      <p>No reports generated yet.</p>
                    )}
                    <button
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          setReport(
                            await api(`/cases/${selected.case_id}/reports`, isReport, 'POST'),
                          );
                          setTimeline(
                            await api(
                              `/cases/${selected.case_id}/timeline?limit=100`,
                              array(isEvent),
                            ),
                          );
                          setSavedReports(
                            await api(`/cases/${selected.case_id}/reports`, array(isReportSummary)),
                          );
                        })
                      }
                    >
                      Generate investigation report
                    </button>
                    {report && (
                      <article className="report" aria-label="Investigation report">
                        <h2>Investigation report</h2>
                        <p>
                          {report.report_id}
                          <small>Source snapshot SHA-256: {report.fingerprint}</small>
                        </p>
                        {(
                          [
                            'case',
                            'recorded_facts',
                            'verified_facts',
                            'system_findings',
                            'evidence',
                            'supporting_source_transactions',
                            'analyst_notes',
                            'timeline',
                            'observations',
                            'recommendations',
                            'limitations',
                          ] as const
                        ).map((key) => (
                          <section key={key}>
                            <h3>{key.replaceAll('_', ' ')}</h3>
                            {key === 'verified_facts' &&
                            Array.isArray(report.content[key]) &&
                            (report.content[key] as unknown[]).length === 0 ? (
                              <p>No independently verified facts recorded.</p>
                            ) : (
                              <pre>{JSON.stringify(report.content[key], null, 2)}</pre>
                            )}
                          </section>
                        ))}
                        <button
                          onClick={() => {
                            const url = URL.createObjectURL(
                              new Blob([JSON.stringify(report, null, 2)], {
                                type: 'application/json',
                              }),
                            );
                            const link = document.createElement('a');
                            link.href = url;
                            link.download = `${report.report_id}.json`;
                            link.click();
                            setTimeout(() => URL.revokeObjectURL(url), 1000);
                          }}
                        >
                          Download JSON report
                        </button>
                      </article>
                    )}
                  </section>
                )}
              </>
            )}
            {['Transactions', 'Evidence', 'Cases'].includes(tab) && (
              <div className="actions pagination">
                <button
                  disabled={busy || offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 25))}
                >
                  Previous page
                </button>
                <span>
                  Records {offset + 1}–{offset + 25}
                </span>
                <button
                  disabled={
                    busy ||
                    offset >= 10000 ||
                    (tab === 'Transactions'
                      ? transactions.length
                      : tab === 'Cases'
                        ? cases.length
                        : evidence.length) < 25
                  }
                  onClick={() => setOffset(offset + 25)}
                >
                  Next page
                </button>
              </div>
            )}
          </fieldset>
        </>
      )}
    </main>
  );
}
