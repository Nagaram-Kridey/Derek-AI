import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage, safeHttpUrl } from './api';
import { Markdown } from './Markdown';
import type { Report } from './types';
import { Badge, Empty, ErrorNotice, Icon, Loading, Modal, dateLabel, useResource } from './ui';

function text(value: unknown) {
  return typeof value === 'string' ? value : '';
}
function stringList(value: unknown) {
  return Array.isArray(value) ? (value.filter((item) => typeof item === 'string') as string[]) : [];
}
function objects(value: unknown) {
  return Array.isArray(value)
    ? (value.filter((item) => item && typeof item === 'object') as Record<string, unknown>[])
    : [];
}

function ReportReader({
  api,
  id,
  refresh,
  close,
}: {
  api: Api;
  id: string;
  refresh: number;
  close: () => void;
}) {
  const report = useResource<Report>(api, `/v1/reports/${id}/detail/`, refresh);
  const data = report.data;
  const content = data?.content || {};
  const ideas = objects(content.project_ideas);
  const shortlisted = Array.isArray(content.shortlisted_projects) ? content.shortlisted_projects : [];
  return (
    <Modal title={data?.title || 'Your report'} close={close}>
      <ErrorNotice message={report.error} />
      {report.loading && !data ? (
        <Loading />
      ) : (
        data && (
          <div className="report-reader">
            <div className="actions">
              <Badge status={data.status} />
              <small>{dateLabel(data.created_at)}</small>
            </div>
            {data.error && <div className="notice error">{data.error}</div>}
            <Markdown text={text(content.executive_summary)} />
            {ideas.length > 0 && (
              <section>
                <h3>Project proposals</h3>
                <p className="notice">
                  These proposals and scores are engineering estimates. Validate the problem, data access and
                  MVP scope before choosing a project.
                </p>
                {text(content.ranking_method) && <p className="muted">{text(content.ranking_method)}</p>}
                {text(content.shortlist_reason) && <p className="muted">{text(content.shortlist_reason)}</p>}
                {ideas.map((idea) => (
                  <article
                    className={`idea-card ${shortlisted.includes(idea.number) ? 'shortlisted' : ''}`}
                    key={String(idea.number)}
                  >
                    <div className="section-heading">
                      <span className="eyebrow">PROJECT {String(idea.number)}</span>
                      {shortlisted.includes(idea.number) && <Badge status="shortlisted" />}
                    </div>
                    <h3>{text(idea.title)}</h3>
                    <p>{text(idea.problem)}</p>
                    <p className="idea-evidence">
                      {text(idea.evidence_status)} <span>Heuristic score: {String(idea.score)}/50</span>
                    </p>
                    <div className="sources">
                      {stringList(idea.source_urls).map((url, index) =>
                        safeHttpUrl(url) ? (
                          <a key={index} href={safeHttpUrl(url)} target="_blank" rel="noopener noreferrer">
                            {new URL(url).hostname}
                            <Icon name="link" size={12} />
                          </a>
                        ) : null,
                      )}
                    </div>
                    <dl>
                      <dt>For</dt>
                      <dd>{text(idea.target_users)}</dd>
                      <dt>MVP</dt>
                      <dd>{text(idea.mvp)}</dd>
                      <dt>Architecture</dt>
                      <dd>{text(idea.architecture)}</dd>
                    </dl>
                    {shortlisted.includes(idea.number) && (
                      <>
                        <h4>Production features to consider</h4>
                        <ul>
                          {stringList(idea.production_features).map((feature, i) => (
                            <li key={i}>{feature}</li>
                          ))}
                        </ul>
                        <h4>Implementation steps</h4>
                        <ol>
                          {stringList(idea.implementation_plan).map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                        <h4>Risks to validate</h4>
                        <p>{text(idea.risks_and_validation)}</p>
                      </>
                    )}
                  </article>
                ))}
              </section>
            )}
            {objects(content.key_findings).length > 0 && (
              <section>
                <h3>Findings and evidence</h3>
                {objects(content.key_findings).map((finding, index) => (
                  <div className="finding" key={index}>
                    <Badge status={finding.verified === true ? 'verified evidence' : 'unverified'} />
                    <Markdown text={text(finding.claim) || text(finding.text)} />
                    {text(finding.verification_reason) && (
                      <p className="muted">{text(finding.verification_reason)}</p>
                    )}
                    <details className="evidence-details">
                      <summary>Inspect this finding's sources and excerpts</summary>
                      <ul>
                        {stringList(finding.source_urls).map((url, i) =>
                          safeHttpUrl(url) ? (
                            <li key={i}>
                              <a href={safeHttpUrl(url)} target="_blank" rel="noopener noreferrer">
                                {url}
                              </a>
                            </li>
                          ) : null,
                        )}
                      </ul>
                      {objects(finding.evidence).map((evidence, i) => (
                        <blockquote key={i}>
                          <p>{text(evidence.quote)}</p>
                          {safeHttpUrl(text(evidence.url)) && (
                            <a
                              href={safeHttpUrl(text(evidence.url))}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Source excerpt
                            </a>
                          )}
                        </blockquote>
                      ))}
                      {!objects(finding.evidence).length && (
                        <p className="muted">
                          No supporting excerpt was retained for this finding. A listed source alone does not
                          verify the claim.
                        </p>
                      )}
                    </details>
                  </div>
                ))}
              </section>
            )}
            {stringList(content.next_steps).length > 0 && (
              <section>
                <h3>Suggested next steps</h3>
                <ol>
                  {stringList(content.next_steps).map((step, index) => (
                    <li key={index}>{step}</li>
                  ))}
                </ol>
              </section>
            )}
            {stringList(content.errors).length > 0 && (
              <section className="notice warning">
                <h3>Research limitations</h3>
                <ul>
                  {stringList(content.errors).map((error, i) => (
                    <li key={i}>{error}</li>
                  ))}
                </ul>
              </section>
            )}
            {data.citations?.length ? (
              <section>
                <h3>Sources</h3>
                <ol className="report-sources">
                  {data.citations.map((source, index) =>
                    safeHttpUrl(source.url) ? (
                      <li key={index}>
                        <a href={safeHttpUrl(source.url)} target="_blank" rel="noopener noreferrer">
                          {source.title || source.url}
                          <Icon name="link" size={12} />
                        </a>
                      </li>
                    ) : null,
                  )}
                </ol>
              </section>
            ) : null}
          </div>
        )
      )}
    </Modal>
  );
}

export function ReportLibrary({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const createId = useRef(crypto.randomUUID());
  const reports = useResource<Report[]>(api, '/v1/reports/', refresh);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [reader, setReader] = useState<string | null>(null);
  const [create, setCreate] = useState(false);
  const visible =
    reports.data?.filter(
      (report) =>
        (filter === 'all' || report.status === filter) &&
        `${report.title} ${report.summary}`.toLowerCase().includes(search.toLowerCase()),
    ) || [];
  async function download(report: Report, format: string) {
    setBusy(String(report.id));
    setError(null);
    try {
      await api.download(`/v1/reports/${report.id}/download/?format=${format}`, `${report.title}.${format}`);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }
  async function remove(report: Report) {
    if (!window.confirm('Permanently delete this report and both exported files?')) return;
    setBusy(String(report.id));
    setError(null);
    try {
      await api.delete(`/v1/reports/${report.id}/`);
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }
  async function stop(report: Report) {
    setBusy(String(report.id));
    setError(null);
    try {
      await api.post(`/v1/reports/${report.id}/cancel/`);
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }
  async function sendCopy(report: Report) {
    if (
      !window.confirm(
        'Send a PDF copy to your approved Telegram chat? If an earlier send was uncertain, check Telegram first to avoid an unwanted duplicate.',
      )
    )
      return;
    setBusy(String(report.id));
    setError(null);
    try {
      await api.post(`/v1/reports/${report.id}/deliver/`, { confirm_copy: true });
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }
  async function research(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy('new');
    setError(null);
    try {
      await api.post('/v1/reports/', {
        topic: form.get('topic'),
        report_kind: form.get('kind'),
        include_academic: form.get('academic') === 'on',
        request_id: createId.current,
      });
      setCreate(false);
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="stack">
      <div className="section-heading">
        <div>
          <h2>Your research library</h2>
          <p className="muted">A place to read, compare, and carry your ideas forward.</p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            createId.current = crypto.randomUUID();
            setCreate(true);
            setError(null);
          }}
        >
          <Icon name="plus" size={16} />
          New research
        </button>
      </div>
      <ErrorNotice message={error || reports.error} />
      <div className="filter-bar">
        <input
          type="search"
          aria-label="Search reports"
          placeholder="Search your reports…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select aria-label="Filter reports" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All reports</option>
          <option value="completed">Ready to read</option>
          <option value="running">In progress</option>
          <option value="queued">Queued</option>
          <option value="failed">Needs attention</option>
          <option value="cancelled">Stopped</option>
        </select>
      </div>
      {reports.loading && !reports.data ? (
        <Loading />
      ) : visible.length ? (
        <div className="card-grid">
          {visible.map((report) => (
            <article className="card report-card" key={report.id}>
              <div className="section-heading">
                <Badge status={report.status} />
                <span className="eyebrow">
                  {report.report_kind === 'project_ideas' ? '5 IDEAS · TOP 2' : 'RESEARCH'}
                </span>
              </div>
              <h3>{report.title}</h3>
              <small>{dateLabel(report.created_at)}</small>
              <p className="report-summary">
                {report.summary ||
                  (report.status === 'running'
                    ? 'Researching sources and checking the findings. You can leave this page.'
                    : report.status === 'queued'
                      ? 'Saved and waiting for the research worker.'
                      : 'Open this report to read its findings.')}
              </p>
              {report.progress && ['queued', 'running'].includes(report.status || '') && (
                <div className="research-progress" role="status">
                  <span className="loader" />
                  <div>
                    <strong>{report.progress.label}</strong>
                    {report.progress.current && report.progress.total ? (
                      <small>
                        {report.progress.current} of {report.progress.total}
                      </small>
                    ) : null}
                    <small>CPU-only local models can take several minutes.</small>
                  </div>
                </div>
              )}
              {report.progress?.telegram_delivery && (
                <small className="delivery-status">
                  Telegram PDF: {report.progress.telegram_delivery.status.replaceAll('_', ' ')}
                  {report.progress.telegram_delivery.error && (
                    <span className="error-text">{report.progress.telegram_delivery.error}</span>
                  )}
                </small>
              )}
              {report.error && <div className="notice error">{report.error}</div>}
              <div className="actions">
                {report.status === 'completed' && (
                  <button className="button primary small" onClick={() => setReader(String(report.id))}>
                    Read report
                    <Icon name="arrow" size={14} />
                  </button>
                )}
                {['pdf', 'docx'].map((format) => (
                  <button
                    className="button secondary small"
                    key={format}
                    disabled={!!busy || report.status !== 'completed'}
                    onClick={() => download(report, format)}
                    aria-label={`Download ${report.title} as ${format}`}
                  >
                    <Icon name="download" size={13} />
                    {format.toUpperCase()}
                  </button>
                ))}
                {report.status === 'completed' && (
                  <button
                    className="text-button"
                    disabled={
                      !!busy ||
                      ['pending', 'sending'].includes(report.progress?.telegram_delivery?.status || '')
                    }
                    onClick={() => sendCopy(report)}
                  >
                    Send PDF to Telegram
                  </button>
                )}
                {['queued', 'running'].includes(report.status || '') && (
                  <button className="text-button" disabled={!!busy} onClick={() => stop(report)}>
                    Stop research
                  </button>
                )}
                <button
                  className="text-button"
                  disabled={!!busy || report.status === 'running'}
                  onClick={() => remove(report)}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          icon="file"
          title={search || filter !== 'all' ? 'No reports match this view' : 'A place for your discoveries'}
        >
          Research a topic or ask for five enterprise software and AI project ideas.
        </Empty>
      )}
      {reader && <ReportReader api={api} id={reader} refresh={refresh} close={() => setReader(null)} />}{' '}
      {create && (
        <Modal title="Explore a topic" close={() => setCreate(false)}>
          <p className="muted">
            Research uses your configured installation model and counts toward your daily limits. Results
            retain evidence labels.
          </p>
          <form className="stack" onSubmit={research}>
            <label>
              What would you like to research?
              <textarea
                name="topic"
                rows={4}
                required
                minLength={3}
                maxLength={2000}
                placeholder="For example, enterprise AI projects for operations teams"
              />
            </label>
            <label>
              Report format
              <select name="kind">
                <option value="standard">Research report</option>
                <option value="project_ideas">Five project ideas with a top-two shortlist</option>
              </select>
            </label>
            <label className="checkbox-label">
              <input type="checkbox" name="academic" />
              Include academic sources
            </label>
            <ErrorNotice message={error} />
            <button className="button primary" disabled={!!busy}>
              {busy ? 'Saving…' : 'Start research'}
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
