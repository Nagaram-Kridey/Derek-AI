import { useState } from 'react';
import { Api } from './api';
import { ErrorNotice, Icon, Loading, useResource } from './ui';
import './analytics.css';

type Timing = { count: number; mean: number | null; p50: number | null; p95: number | null; max: number | null };
type Metrics = { requests: number; succeeded: number; failed: number; cancelled: number; slow: number; latency_ms: Timing };
export type AnalyticsData = {
  window: { days: number; since: string; generated_at: string };
  users: { total: number; active: number };
  provider: Metrics & { slow_threshold_ms: number; collection_started_at: string | null };
  models: (Metrics & { provider: string; model: string })[];
  commands: { requests: number; by_status: Record<string, number>; end_to_end_ms: Timing; queue_ms: Timing; in_progress: number; stale: number };
  recent_issues: { id: string; at: string; provider: string; model: string; operation: string; status: string; error_code: string; latency_ms: number }[];
  images?: { requests: number; by_status: Record<string, number>; queue_ms: Timing; generation_ms: Timing; in_progress: number; failures: number };
  notes: string[]; sampled: boolean;
};

function duration(ms: number | null | undefined) {
  if (ms == null || !Number.isFinite(ms)) return 'No samples';
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}
function timestamp(value: string) { return new Date(value).toLocaleString(); }

export function Analytics({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const [days, setDays] = useState(7);
  const resource = useResource<AnalyticsData>(api, `/v1/admin/analytics/?days=${days}`, refresh);
  const data = resource.error ? null : resource.data;
  return <div className="stack analytics-page">
    <div className="analytics-toolbar">
      <label>Time period <select value={days} onChange={event => setDays(Number(event.target.value))}>
        <option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option>
      </select></label>
      <button className="button" onClick={changed}><Icon name="refresh" size={16} /> Refresh</button>
    </div>
    <ErrorNotice message={resource.error} />
    {!data && !resource.error && <Loading />}
    {data && <>
      <p className="muted analytics-updated">Updated {timestamp(data.window.generated_at)} · Admin only</p>
      <section className="analytics-stats" aria-label="Model request overview">
        {[
          ['Model calls', data.provider.requests.toLocaleString(), `${data.provider.succeeded} succeeded · ${data.provider.cancelled} cancelled`],
          ['Failures', data.provider.failed.toLocaleString(), data.provider.requests ? `${(data.provider.failed / data.provider.requests * 100).toFixed(1)}% of model calls` : 'No calls recorded'],
          ['Typical response', duration(data.provider.latency_ms.p50), 'Median model call duration'],
          ['Slow-end response', duration(data.provider.latency_ms.p95), '95th percentile model call duration'],
          ['Slow calls', data.provider.slow.toLocaleString(), `At least ${duration(data.provider.slow_threshold_ms)}`],
          ['Accounts', data.users.total.toLocaleString(), `${data.users.active} active in this period`],
        ].map(([label, value, help]) => <article className="panel analytics-stat" key={label}><span>{label}</span><strong>{value}</strong><small>{help}</small></article>)}
      </section>
      {data.images && <section className="panel"><h2>Image generation</h2><p className="muted">Local image jobs are measured separately from text-model calls.</p><dl className="analytics-delays"><div><dt>Accepted jobs</dt><dd>{data.images.requests}</dd></div><div><dt>Failures</dt><dd>{data.images.failures}</dd></div><div><dt>In progress</dt><dd>{data.images.in_progress}</dd></div><div><dt>Median queue wait</dt><dd>{duration(data.images.queue_ms.p50)}</dd></div><div><dt>Median generation</dt><dd>{duration(data.images.generation_ms.p50)}</dd></div><div><dt>95th percentile generation</dt><dd>{duration(data.images.generation_ms.p95)}</dd></div></dl><p className="muted">{Object.entries(data.images.by_status).map(([status, count]) => `${status}: ${count}`).join(' � ') || 'No image jobs recorded.'}</p></section>}
      <section className="panel">
        <h2>Request delays</h2>
        <p className="muted">A request may include several model calls and tool steps. These timings cover the whole request.</p>
        <dl className="analytics-delays">
          <div><dt>Total requests</dt><dd>{data.commands.requests}</dd></div>
          <div><dt>Median total time</dt><dd>{duration(data.commands.end_to_end_ms.p50)}</dd></div>
          <div><dt>95th percentile total</dt><dd>{duration(data.commands.end_to_end_ms.p95)}</dd></div>
          <div><dt>Median queue wait</dt><dd>{duration(data.commands.queue_ms.p50)}</dd></div>
          <div><dt>95th percentile queue</dt><dd>{duration(data.commands.queue_ms.p95)}</dd></div>
          <div><dt>In progress</dt><dd>{data.commands.in_progress}</dd></div>
          <div><dt>Stale requests</dt><dd>{data.commands.stale}</dd></div>
        </dl>
        <p className="muted">Request states: {Object.entries(data.commands.by_status).map(([status, count]) => `${status}: ${count}`).join(' · ') || 'No requests in this period'}</p>
      </section>
      <section className="panel">
        <h2>Requested models & routes</h2>
        <p className="muted">Router profiles such as auto:fast may use different underlying models. These measurements are grouped by the requested model or route.</p>
        {!data.models.length ? <p className="muted">New model measurements will appear after a request is processed.</p> : <div className="analytics-table-scroll" tabIndex={0} role="region" aria-label="Model performance table"><table>
          <thead><tr><th scope="col">Requested model / route</th><th scope="col">Calls</th><th scope="col">Failed</th><th scope="col">Slow</th><th scope="col">Median</th><th scope="col">95th percentile</th></tr></thead>
          <tbody>{data.models.map(model => <tr key={`${model.provider}:${model.model}`}><th scope="row">{model.model}<small>{model.provider}</small></th><td>{model.requests}</td><td>{model.failed}</td><td>{model.slow}</td><td>{duration(model.latency_ms.p50)}</td><td>{duration(model.latency_ms.p95)}</td></tr>)}</tbody>
        </table></div>}
      </section>
      <section className="panel">
        <h2>Recent issues & slow calls</h2>
        {!data.recent_issues.length ? <p className="muted">No recorded issues in this period.</p> : <ul className="analytics-issues">{data.recent_issues.map(issue => <li key={issue.id}>
          <div><strong>{issue.error_code || issue.status}</strong><span>{issue.provider} · {issue.model} · {issue.operation}</span></div>
          <div><span>{duration(issue.latency_ms)}</span><time dateTime={issue.at}>{timestamp(issue.at)}</time></div>
        </li>)}</ul>}
      </section>
      <aside className="panel analytics-notes" aria-label="Measurement details">
        <h2>Measurement details</h2>
        <p>{data.provider.collection_started_at ? `Model timing collection began ${timestamp(data.provider.collection_started_at)}.` : 'Model timing collection has no samples yet. Historical request timings are shown separately.'}</p>
        {data.sampled && <p>Timing statistics use a bounded sample; counts cover the selected period.</p>}
        {data.notes.map((note, index) => <p key={index}>{note}</p>)}
      </aside>
    </>}
  </div>;
}
