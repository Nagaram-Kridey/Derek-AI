import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage } from './api';
import { ErrorNotice, Loading, useResource } from './ui';
import './images.css';

export type ImageJob = { id: string; prompt: string; negative_prompt: string; seed: number; status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'; created_at: string; error_code?: string; conversation_id?: string | null; provider?: string; model?: string; width?: number; height?: number };
const ROUTER_MODELS = [
  { value: '@cf/bytedance/stable-diffusion-xl-lightning', label: 'SDXL Lightning' },
  { value: '@cf/stabilityai/stable-diffusion-xl-base-1.0', label: 'SDXL Base' },
];
type ImageConfig = { enabled: boolean; disabled_reason?: string; jobs: ImageJob[]; provider?: string; default_model?: string; width?: number; height?: number };

function PrivatePreview({ api, job }: { api: Api; job: ImageJob }) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = '';
    void api.fetch(`/v1/images/${job.id}/download/`, { signal: controller.signal }).then(response => response.blob()).then(blob => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
    }).catch(failure => { if (!controller.signal.aborted) setError(errorMessage(failure)); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [api, job.id]);
  return <><ErrorNotice message={error} />{url ? <img className="generated-image" src={url} alt={job.prompt} width={job.width || 1024} height={job.height || 1024} /> : !error && <Loading />}</>;
}

export function ImageForm({ api, config, conversationId, created, createConversation = false }: { api: Api; config: ImageConfig; conversationId?: string | null; created: (job: ImageJob) => void; createConversation?: boolean }) {
  const router = config.provider === 'freellmapi';
  const [model, setModel] = useState(config.default_model || ROUTER_MODELS[0].value);
  const [prompt, setPrompt] = useState('');
  const [negative, setNegative] = useState('');
  const [seed, setSeed] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(crypto.randomUUID());
  const dirty = () => { requestId.current = crypto.randomUUID(); };
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy || !config.enabled) return;
    setBusy(true); setError('');
    try {
      const job = await api.post<ImageJob>('/v1/images/', { prompt, ...(router ? { model } : { negative_prompt: negative, seed: seed === '' ? -1 : Number(seed) }), request_id: requestId.current, ...(conversationId ? { conversation_id: conversationId } : createConversation ? { create_conversation: true } : {}) });
      requestId.current = crypto.randomUUID(); setPrompt(''); setNegative(''); setSeed(''); created(job);
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }
  return <form className="image-form" onSubmit={submit}>
    {!config.enabled && <p role="status" className="muted">{config.disabled_reason || 'Image generation is not available yet. Check the configured image service.'}</p>}
    <label>Image prompt<textarea required maxLength={2000} rows={3} value={prompt} disabled={busy || !config.enabled} onChange={event => { dirty(); setPrompt(event.target.value); }} placeholder="Describe the image you want to create…" /></label>
    {router && <label>Image model<select value={model} disabled={busy || !config.enabled} onChange={event => { dirty(); setModel(event.target.value); }}>{ROUTER_MODELS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>}
    {!router && <label>Negative prompt <span className="muted">(optional)</span><input maxLength={1000} value={negative} disabled={busy || !config.enabled} onChange={event => { dirty(); setNegative(event.target.value); }} /></label>}
    <div className="image-form-bottom">{!router && <label>Seed <span className="muted">(optional)</span><input type="number" min="0" max="4294967295" step="1" value={seed} disabled={busy || !config.enabled} onChange={event => { dirty(); setSeed(event.target.value); }} placeholder="Random" /></label>}<button className="button primary" disabled={busy || !config.enabled || !prompt.trim()}>{busy ? 'Saving…' : 'Generate image'}</button></div>
    <small className="muted">512 × 512 · 15 steps · One image · Up to 5 accepted jobs per day</small>
    <ErrorNotice message={error} />
  </form>;
}

function ImageCard({ api, job, changed }: { api: Api; job: ImageJob; changed: () => void }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function act(action: 'cancel' | 'delete' | 'download') {
    if (action === 'delete' && !window.confirm('Delete this generated image and its saved output?')) return;
    setBusy(true); setError('');
    try {
      if (action === 'download') await api.download(`/v1/images/${job.id}/download/`, `Derek-image-${job.id}.png`);
      else if (action === 'delete') await api.delete(`/v1/images/${job.id}/`);
      else await api.post(`/v1/images/${job.id}/cancel/`);
      if (action !== 'download') changed();
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }
  return <article className="panel image-card">
    <div className="image-card-heading"><strong>{job.prompt}</strong><span role="status" className="muted">{job.status}</span></div>
    {job.model && <small className="muted">{ROUTER_MODELS.find(option => option.value === job.model)?.label || job.model}</small>}
    {job.status === 'completed' && <PrivatePreview api={api} job={job} />}
    {job.status === 'queued' && <p className="muted">Waiting for the image worker.</p>}
    {job.status === 'running' && <p className="muted">Generating your image. You can keep chatting while this runs.</p>}
    {job.status === 'failed' && <p role="status">Generation could not finish{job.error_code ? ` (${job.error_code.replaceAll('_', ' ')})` : ''}. It will not be retried automatically.</p>}
    <div className="actions">
      {job.status === 'completed' && <button className="button secondary" disabled={busy} onClick={() => void act('download')}>Download PNG</button>}
      {job.status === 'queued' && <button className="button secondary" disabled={busy} onClick={() => void act('cancel')}>Cancel</button>}
      {!['queued', 'running'].includes(job.status) && <button className="text-button" disabled={busy} onClick={() => void act('delete')}>Delete</button>}
    </div><ErrorNotice message={error} />
  </article>;
}

export function Images({ api, refresh, changed, conversationId, compact = false, showForm = true, onCreated }: { api: Api; refresh: number; changed: () => void; conversationId?: string | null; compact?: boolean; showForm?: boolean; onCreated?: (job: ImageJob) => void }) {
  const [localRefresh, setLocalRefresh] = useState(0);
  const jobs = useResource<ImageConfig>(api, '/v1/images/', refresh + localRefresh);
  const config = jobs;
  const visibleJobs = jobs.data?.jobs.filter(job => !compact || job.conversation_id === conversationId) || [];
  const update = () => { setLocalRefresh(value => value + 1); changed(); };
  const pending = visibleJobs.some(job => ['queued', 'running'].includes(job.status));
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => { if (!document.hidden) setLocalRefresh(value => value + 1); }, 3000);
    const foreground = () => { if (!document.hidden) setLocalRefresh(value => value + 1); };
    document.addEventListener('visibilitychange', foreground);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', foreground); };
  }, [pending]);
  if (compact && !showForm && !visibleJobs.length && !jobs.error) return null;
  return <section className={`stack images-page ${compact ? 'images-in-chat' : ''}`} aria-label={compact ? 'Images in this conversation' : 'Your images'}>
    {(!compact || showForm) && <div className="image-page-heading"><div><h2>{compact ? 'Generate an image' : 'Your images'}</h2><p className="muted">Your private image generations.</p></div><button className="button secondary" onClick={update}>Refresh images</button></div>}
    <ErrorNotice message={config.error || jobs.error} />
    {showForm && (config.loading && !config.data ? <Loading /> : config.data && <div className="panel"><ImageForm api={api} config={config.data} conversationId={conversationId} createConversation={compact} created={job => { update(); onCreated?.(job); }} /></div>)}
    <div className="image-grid">{visibleJobs.map(job => <ImageCard key={job.id} api={api} job={job} changed={update} />)}</div>
    {!jobs.loading && !!jobs.data && visibleJobs.length === 0 && <p className="muted">{compact ? 'Images created here will also appear on your Images page.' : 'Your generated images will appear here.'}</p>}
  </section>;
}
