import { useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage } from './api';
import type { Approval, ScheduledTask, Workflow, WorkflowDefinition, Run } from './types';
import { Badge, Empty, ErrorNotice, Icon, JsonDetails, Loading, Modal, dateLabel, useResource } from './ui';

const initial: WorkflowDefinition = { name: 'Morning check-in', description: 'A personal notification', steps: [{ tool: 'notify', args: { message: 'Time to review your day.' } }], allowed_tools: ['notify'], allowed_domains: [], allowed_paths: [], trigger: { kind: 'manual' } };

export function Automations({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const tasks = useResource<ScheduledTask[]>(api, '/v1/tasks/', refresh);
  const workflows = useResource<Workflow[]>(api, '/v1/workflows/', refresh);
  const approvals = useResource<Approval[]>(api, '/v1/approvals/', refresh);
  const runs = useResource<Run[]>(api, '/v1/runs/', refresh);
  const [modal, setModal] = useState<'task' | 'workflow' | null>(null);
  const [definition, setDefinition] = useState(JSON.stringify(initial, null, 2));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function act(path: string, method = 'POST') {
    setBusy(true); setError(null);
    try { if (method === 'DELETE') await api.delete(path); else await api.post(path); changed(); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  async function saveWorkflow(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try { await api.post('/v1/workflows/', JSON.parse(definition)); setModal(null); changed(); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  async function saveTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError(null);
    const kind = String(form.get('kind')); const recurrence = String(form.get('recurrence'));
    const schedule = recurrence === 'once' ? { kind: 'once', at: String(form.get('at')), timezone: 'Asia/Kolkata' } : { kind: recurrence, time: String(form.get('time')), weekdays: [Number(form.get('weekday'))], timezone: 'Asia/Kolkata' };
    try { await api.post('/v1/tasks/', { name: form.get('name'), kind, payload: kind === 'reminder' ? { message: form.get('content') } : { topic: form.get('content') }, schedule }); setModal(null); changed(); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  const [recurrence, setRecurrence] = useState('once');
  return <div className="stack"><div className="section-heading"><div><h2>Your routines</h2><p className="muted">Review permissions once, then let approved workflows take care of the routine.</p></div><div className="actions"><button className="button secondary" onClick={() => {setModal('workflow'); setError(null);}}><Icon name="plus"/>Draft workflow</button><button className="button primary" onClick={() => {setModal('task'); setError(null);}}><Icon name="plus"/>New reminder</button></div></div><ErrorNotice message={error || tasks.error || workflows.error || approvals.error || runs.error}/>
    {!!approvals.data?.length && <section className="panel"><h2>Your approval is needed</h2>{approvals.data.map(item => <article className="card" key={item.id}><Badge status="needs approval"/><h3>{item.reason || item.action}</h3><JsonDetails value={item.payload || item.details} label="Review the exact action"/><div className="actions"><button className="button primary" disabled={busy} onClick={() => { if (window.confirm('Approve this exact sensitive action? Review its details before continuing.')) void act(`/v1/approvals/${item.id}/approve/`); }}>Approve once</button><button className="button secondary" disabled={busy} onClick={() => act(`/v1/approvals/${item.id}/reject/`)}>Reject</button></div></article>)}</section>}
    <section><h2>Scheduled tasks</h2>{tasks.loading && !tasks.data ? <Loading/> : tasks.data?.length ? <div className="card-grid">{tasks.data.map(item => <article className="card" key={item.id}><div className="section-heading"><Badge status={item.enabled ? 'scheduled' : 'paused'}/><span className="eyebrow">{item.kind}</span></div><h3>{item.name}</h3><p>{item.payload.message || (item.payload as {topic?:string}).topic}</p><p className="muted">Next: {dateLabel(item.next_run_at)}</p><JsonDetails value={item.schedule} label="Schedule details"/><div className="actions"><button className="button secondary small" disabled={busy} onClick={() => act(`/v1/tasks/${item.id}/${item.enabled ? 'pause' : 'resume'}/`)}>{item.enabled ? 'Pause' : 'Resume'}</button><button className="text-button" disabled={busy} onClick={() => { if (window.confirm('Delete this scheduled task?')) void act(`/v1/tasks/${item.id}/`, 'DELETE'); }}>Delete</button></div></article>)}</div> : <Empty icon="clock" title="Room for a routine">Add a reminder or schedule regular research.</Empty>}</section>
    <section><h2>Workflows</h2>{workflows.data?.length ? <div className="card-grid">{workflows.data.map(item => <article className="card" key={item.id}><Badge status={item.enabled ? 'enabled' : 'draft / paused'}/><h3>{item.name}</h3><p>{item.description}</p><div className="scope"><strong>Permissions</strong><p>{item.allowed_tools.join(', ')}</p><p>Sites: {item.allowed_domains.join(', ') || 'None'}</p><p>Folders: {item.allowed_paths.join(', ') || 'None'}</p></div><JsonDetails value={{steps: item.steps, trigger: item.trigger}} label="Review steps and trigger"/><div className="actions"><button className="button secondary small" disabled={busy} onClick={() => { if (item.enabled || window.confirm(`Enable ${item.name} with the displayed tools, sites, folders and trigger?`)) void act(`/v1/workflows/${item.id}/${item.enabled ? 'pause' : 'enable'}/`); }}>{item.enabled ? 'Pause' : 'Review & enable'}</button><button className="button primary small" disabled={busy || !item.enabled} onClick={() => act(`/v1/workflows/${item.id}/run/`)}><Icon name="play" size={14}/>Run now</button><button className="text-button" disabled={busy} onClick={() => {if(window.confirm('Delete this workflow and cancel pending runs?')) void act(`/v1/workflows/${item.id}/`, 'DELETE');}}>Delete</button></div></article>)}</div> : <Empty title="Give a routine a home">Describe an automation in chat or create a workflow draft here.</Empty>}</section>
    <section className="panel"><h2>Recent runs</h2>{runs.data?.length ? runs.data.map(item => <div className="list-row" key={item.id}><div><strong>{item.workflow_name || item.id}</strong><p className="muted">{dateLabel(item.created_at)}</p>{item.error && <p className="error-text">{item.error}</p>}</div><div className="actions"><Badge status={item.status}/>{!['completed','failed','cancelled'].includes(item.status) && <button className="text-button" disabled={busy} onClick={() => act(`/v1/runs/${item.id}/cancel/`)}>Cancel</button>}</div></div>) : <p className="muted">Workflow runs will appear here.</p>}</section>
    {modal === 'workflow' && <Modal title="Draft a workflow" close={() => setModal(null)}><p className="muted">You can also ask Lily-Leo to draft this in chat. Review the exact steps and permissions before enabling it.</p><form onSubmit={saveWorkflow}><label>Workflow definition<textarea className="code-editor" value={definition} onChange={e => setDefinition(e.target.value)} rows={18} required/></label><ErrorNotice message={error}/><button className="button primary" disabled={busy}>Save draft</button></form></Modal>}
    {modal === 'task' && <Modal title="Schedule a task" close={() => setModal(null)}><form onSubmit={saveTask} className="stack"><label>Name<input name="name" required maxLength={160}/></label><label>Task type<select name="kind"><option value="reminder">Reminder</option><option value="research">Research report</option></select></label><label>Reminder message or research topic<textarea name="content" required rows={3}/></label><label>Repeat<select name="recurrence" value={recurrence} onChange={e => setRecurrence(e.target.value)}><option value="once">Once</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select></label>{recurrence === 'once' ? <label>When (Asia/Kolkata)<input type="datetime-local" name="at" required/></label> : <label>Time (Asia/Kolkata)<input name="time" type="time" defaultValue="09:00" required/></label>}{recurrence === 'weekly' && <label>Day<select name="weekday">{['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((day,i) => <option key={i} value={i}>{day}</option>)}</select></label>}<ErrorNotice message={error}/><button className="button primary" disabled={busy}>Schedule</button></form></Modal>}
  </div>;
}
