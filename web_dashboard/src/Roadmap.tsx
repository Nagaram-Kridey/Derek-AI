import { useEffect, useState } from 'react';
import { Api, errorMessage } from './api';
import './roadmap.css';

type Block = { id: string; title: string; phase: string; origin: string; status: string; difficulty: string; description: string; evidence: string; next_step: string; owner_action: string; dependencies: string[]; enabled: boolean; test_mode: string; test_result: string; notes: string; priority: string };
type Board = { version: number; items: Block[] };
const states = ['implemented', 'in_progress', 'planned', 'idea', 'blocked', 'verified'];
const label = (s: string) => s.replaceAll('_', ' ');
function template(b: Block) {
  return `Derek feature request: ${b.title}\nBlock: ${b.id}\nStatus: ${b.status}; priority: ${b.priority}\nScope: ${b.description}\nDependencies: ${b.dependencies.join(', ') || 'none'}\nNext work / acceptance: ${b.next_step}\nOwner setup: ${b.owner_action}\nRequested test mode: ${b.test_mode}. This is a test plan, not authorization for live external effects.\nExisting evidence: ${b.evidence}\nNotes: ${b.notes}\nInspect current implementation before editing. Preserve unrelated work, verify the acceptance criteria, and update the checklist and roadmap with actual evidence. Never treat a planning toggle as runtime permission.`;
}
export function Roadmap({ api, portable = false }: { api: Api; portable?: boolean }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [selected, select] = useState('');
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [prompt, setPrompt] = useState('');
  async function load() {
    setBusy(true);
    try { const value = await api.request<Board>('/v1/roadmap/'); setBoard(value); setDirty(false); setError(''); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, [api]);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  // Keep component mounted when navigating between app pages so edits survive.
  const block = board?.items.find(b => b.id === selected);
  function update(values: Partial<Block>) {
    setBoard(b => b && ({ ...b, items: b.items.map(i => i.id === selected ? { ...i, ...values } : i) }));
    setDirty(true); setNotice('');
  }
  async function save() {
    setBusy(true);
    try { const result = await api.request<Board>('/v1/roadmap/', { method: 'PUT', body: JSON.stringify(board) }); setBoard(result); setDirty(false); setError(''); setNotice(portable ? 'Saved in this browser only. Export to transfer your edits.' : 'Saved to your roadmap. Runtime services are unchanged.'); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  function add(copy?: Block) {
    const id = crypto.randomUUID();
    const item: Block = copy ? { ...copy, id, title: `${copy.title} (copy)`, status: 'planned', test_result: 'not_run', evidence: '' } : { id, title: 'New feature', phase: '7 Extensions', origin: 'Owner request', status: 'idea', difficulty: 'medium', description: '', evidence: '', next_step: '', owner_action: '', dependencies: [], enabled: true, test_mode: 'isolated', test_result: 'not_run', notes: '', priority: 'next' };
    setBoard(b => b && ({ ...b, items: [...b.items, item] })); select(id); setDirty(true);
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(board, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'derek-roadmap.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function copyPrompt(value: string) {
    setPrompt(value);
    try { await navigator.clipboard.writeText(value); setNotice('Prompt copied. Paste it into Codex for review and implementation.'); }
    catch { setNotice('Select and copy the prompt below.'); }
  }
  if (!board) return <section className="roadmap"><h2>Roadmap</h2><p role="alert">{error || 'Loading roadmap…'}</p><button onClick={load} disabled={busy}>Retry</button></section>;
  const items = board.items.filter(b => (filter === 'all' || b.status === filter) && `${b.title} ${b.description} ${b.phase} ${b.origin}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="roadmap">
    <header><span className="eyebrow">PRODUCT CONTROL CENTER</span><h2>From idea to evidence.</h2><p>Plan Derek’s features, review dependencies and record what actually works.</p><p className="muted">Planning controls only. Test plans do not execute tests. Use Automations and Settings for existing runtime controls.</p></header>
    <div className="roadmap-toolbar">
      <button className="button primary" onClick={save} disabled={!dirty || busy}>{busy ? 'Working…' : 'Save changes'}</button>
      <button className="button" onClick={() => add()} disabled={busy}>Add feature</button>
      <button className="button" onClick={download}>Export JSON</button>
      <button className="button" onClick={() => window.print()}>Print / save PDF</button>
      <button className="button" onClick={() => copyPrompt(board.items.filter(b => b.enabled && b.priority === 'now').map(template).join('\n\n---\n\n'))}>Copy “now” plan</button>
      <button className="button" onClick={() => { if (!dirty || window.confirm('Discard unsaved roadmap edits and reload?')) void load(); }} disabled={busy}>Reload saved board</button>
      <strong>{dirty ? 'Unsaved changes' : `Saved · revision ${board.version}`}</strong>
    </div>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="roadmap-stats">{states.map(s => <button key={s} onClick={() => setFilter(s)}><b>{board.items.filter(b => b.status === s).length}</b>{label(s)}</button>)}</div>
    <div className="roadmap-toolbar"><input aria-label="Search roadmap" placeholder="Find a feature, phase or request…" value={query} onChange={e => setQuery(e.target.value)} /><select aria-label="Filter roadmap" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All statuses</option>{states.map(s => <option key={s}>{s}</option>)}</select></div>
    <div className="roadmap-layout"><div className="roadmap-phases">{[...new Set(items.map(b => b.phase))].map(phase => <section key={phase}><h3>{phase}</h3>{items.filter(b => b.phase === phase).map(b => <button className={`roadmap-card ${selected === b.id ? 'active' : ''}`} key={b.id} onClick={() => select(b.id)}><span>{label(b.status)} · {b.priority}</span><strong>{b.title}</strong><small>{b.origin} · {label(b.difficulty)} effort</small><small>{b.enabled ? 'Included in plans' : 'Excluded from plans'} · Test: {label(b.test_result)}</small>{b.dependencies.length > 0 && <small>Needs: {b.dependencies.map(id => board.items.find(x => x.id === id)?.title || id).join(', ')}</small>}</button>)}</section>)}{!items.length && <p>No matching features.</p>}</div>
    <aside className="roadmap-editor">{block ? <fieldset disabled={busy}><legend>Edit feature</legend><label>Title<input value={block.title} onChange={e => update({ title: e.target.value })} maxLength={240} /></label><label>Include in implementation plans<input type="checkbox" checked={block.enabled} onChange={e => update({ enabled: e.target.checked })} /></label>
      {(['phase','origin'] as const).map(k => <label key={k}>{label(k)}<input value={block[k]} onChange={e => update({ [k]: e.target.value })} maxLength={120} /></label>)}
      {([['status',states],['priority',['now','next','later']],['difficulty',['low','medium','high','very_high']],['test_mode',['isolated','live','none']],['test_result',['not_run','queued','passed','failed']]] as [keyof Block,string[]][]).map(([k,values]) => <label key={k}>{label(k)}<select value={String(block[k])} onChange={e => update({ [k]: e.target.value })}>{values.map(v => <option key={v} value={v}>{label(v)}</option>)}</select></label>)}
      {(['description','next_step','owner_action','evidence','notes'] as const).map(k => <label key={k}>{label(k)}<textarea rows={3} value={block[k]} maxLength={4000} onChange={e => update({ [k]: e.target.value })} /></label>)}
      <label>Dependencies (Ctrl to select several)<select multiple value={block.dependencies} onChange={e => update({ dependencies: Array.from(e.target.selectedOptions, o => o.value) })}>{board.items.filter(i => i.id !== block.id).map(i => <option key={i.id} value={i.id}>{i.title}</option>)}</select></label>
      <p>Passed / verified requires evidence. Test results are manually recorded, not automatically certified.</p>
      <div className="roadmap-toolbar"><button className="button" onClick={() => update({ test_result: 'queued' })}>Queue test plan</button><button className="button" onClick={() => copyPrompt(template(block))}>Copy prompt</button><button className="button" onClick={() => add(block)}>Duplicate</button></div>
    </fieldset> : <p>Select a feature to edit its scope, dependencies and acceptance evidence.</p>}</aside></div>
    {prompt && <label className="roadmap-prompt">Prompt preview — review before sending<textarea rows={12} readOnly value={prompt} /></label>}
  </section>;
}
