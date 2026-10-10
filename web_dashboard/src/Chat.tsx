import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage, safeHttpUrl } from './api';
import type { Artifact, Citation, Conversation, Identifier, Message, Turn } from './types';
import { ErrorNotice, Icon, Loading, dateLabel, useResource } from './ui';

function Citations({ citations }: { citations?: Citation[] }) {
  return citations?.length ? <div className="sources"><span>Sources</span>{citations.map((citation, index) => {
    const href = safeHttpUrl(citation.url);
    return href ? <a href={href} key={`${href}-${index}`} target="_blank" rel="noopener noreferrer"><span>{index + 1}</span>{citation.title || citation.domain || new URL(href).hostname}<Icon name="link" size={12}/></a> : null;
  })}</div> : null;
}

function SearchSuggestions({html}:{html?:string[]}) {
  return html?.length ? <div className="search-suggestions">{html.map((content,index)=><iframe key={index} title={`Google Search suggestions ${index+1}`} srcDoc={content} sandbox="allow-popups" style={{width:'100%',height:100,border:0}}/>)}</div> : null;
}

function Artifacts({ artifacts, api }: { artifacts?: Artifact[]; api: Api }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function download(item: Artifact) {
    setBusy(true); setError(null);
    try { await api.download(`/v1/reports/${item.report_id || item.id}/download/?format=pdf`, `${item.title || item.name || 'report'}.pdf`); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return artifacts?.length ? <div className="artifacts">{artifacts.map((item, index) => item.report_id || item.id ? <button className="button secondary small" disabled={busy} key={index} onClick={() => download(item)}><Icon name="file" size={16}/>{item.title || item.name || 'Download report'}<Icon name="download" size={14}/></button> : safeHttpUrl(item.url) ? <a className="button secondary small" key={index} href={safeHttpUrl(item.url)} target="_blank" rel="noopener noreferrer">{item.title || item.name || 'Open artifact'}<Icon name="link" size={14}/></a> : null)}<ErrorNotice message={error}/></div> : null;
}

const suggestions = [
  { icon: 'file' as const, title: 'Explore an idea', detail: 'Research a topic with sources', prompt: 'Research the latest developments in ' },
  { icon: 'clock' as const, title: 'Free up your day', detail: 'Set a reminder or recurring task', prompt: 'Remind me every weekday at 9 AM to ' },
  { icon: 'spark' as const, title: 'Find your rhythm', detail: 'Draft an everyday automation', prompt: 'Draft a workflow that ' },
];

export function Chat({ api, refresh, changed, onAutomations }: { api: Api; refresh: number; changed: () => void; onAutomations: () => void }) {
  const conversations = useResource<Conversation[]>(api, '/v1/conversations/', refresh);
  const [conversation, setConversation] = useState<Identifier | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [audio, setAudio] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorderTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptEnd = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const loadSequence = useRef(0);

  useEffect(() => { transcriptEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [messages, busy]);
  useEffect(() => () => {
    if (recorderTimer.current) clearTimeout(recorderTimer.current);
    if (recorder.current?.state === 'recording') { recorder.current.onstop = null; recorder.current.stop(); }
    stream.current?.getTracks().forEach(track => track.stop());
  }, []);

  async function openConversation(id: Identifier) {
    if (busy) return;
    const seq = ++loadSequence.current;
    setLoading(true); setError(null);
    try {
      const result = await api.request<Conversation>(`/v1/conversations/${id}/`);
      if (seq !== loadSequence.current) return;
      setConversation(id); setMessages(result.messages || []);
    } catch (error) { if (seq === loadSequence.current) setError(errorMessage(error)); }
    finally { if (seq === loadSequence.current) setLoading(false); }
  }
  function newConversation() { ++loadSequence.current; setLoading(false); setConversation(null); setMessages([]); setError(null); setText(''); setAudio(null); input.current?.focus(); }
  async function removeConversation(id: Identifier) {
    if (!window.confirm('Delete this conversation and its messages?')) return;
    setError(null); setBusy(true);
    try { await api.delete(`/v1/conversations/${id}/`); if (conversation === id) newConversation(); changed(); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (busy || recording || (!text.trim() && !audio)) return;
    const content = audio ? `Voice note · ${audio.name}` : text.trim();
    setBusy(true); setError(null); setMessages(previous => [...previous, { role: 'user', content }]);
    try {
      let result: Turn;
      if (audio) {
        const body = new FormData(); body.append('audio', audio); if (conversation !== null) body.append('conversation_id', String(conversation));
        result = await api.request<Turn>('/v1/turn', { method: 'POST', body });
      } else result = await api.post<Turn>('/v1/turn', { text: text.trim(), ...(conversation !== null ? { conversation_id: conversation } : {}) });
      setConversation(result.conversation_id); setText(''); setAudio(null);
      setMessages(previous => [...previous, { role: 'assistant', content: result.reply_text, citations: result.citations, artifacts: result.artifacts, job_id: result.job_id, approval_needed: result.approval_needed, search_suggestions_html: result.search_suggestions_html }]);
      changed();
    } catch (error) { setMessages(previous => previous.slice(0, -1)); setError(errorMessage(error)); }
    finally { setBusy(false); input.current?.focus(); }
  }
  function selectAudio(file: File | undefined) {
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) { setError('Choose an audio file smaller than 20 MB.'); return; }
    setError(null); setAudio(file); setText('');
  }
  async function toggleRecording() {
    if (recording) { recorder.current?.stop(); return; }
    setError(null);
    if (!navigator.mediaDevices || typeof MediaRecorder === 'undefined') { setError('Microphone recording needs HTTPS or localhost and a supported browser. You can upload an audio file instead.'); return; }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
      const instance = new MediaRecorder(stream.current, mime ? { mimeType: mime } : undefined);
      recorder.current = instance;
      const chunks: BlobPart[] = [];
      instance.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      instance.onstop = () => {
        if (recorderTimer.current) clearTimeout(recorderTimer.current);
        stream.current?.getTracks().forEach(track => track.stop());
        const extension = instance.mimeType.includes('mp4') ? 'm4a' : instance.mimeType.includes('ogg') ? 'ogg' : 'webm';
        selectAudio(new File(chunks, `voice-note.${extension}`, { type: instance.mimeType })); setRecording(false);
      };
      instance.onerror = () => { setError('The recording stopped unexpectedly. Please try again.'); stream.current?.getTracks().forEach(track => track.stop()); setRecording(false); };
      instance.start(); setRecording(true);
      recorderTimer.current = setTimeout(() => { if (instance.state === 'recording') instance.stop(); }, 120_000);
    } catch (error) { setError(errorMessage(error)); stream.current?.getTracks().forEach(track => track.stop()); }
  }

  return <div className="chat-layout"><section className={`chat-main ${messages.length ? 'has-messages' : ''}`} aria-label="Conversation"><div className="transcript" aria-live="polite">{loading ? <Loading/> : messages.length ? messages.map((message, index) => <article key={message.id || index} className={`message ${message.role === 'user' ? 'from-user' : 'from-assistant'}`}><div className="message-label">{message.role === 'user' ? <span className="message-avatar">You</span> : <span className="assistant-avatar"><Icon name="spark" size={16}/></span>}<strong>{message.role === 'user' ? 'You' : 'Derek'}</strong>{message.created_at && <time>{dateLabel(message.created_at)}</time>}</div><div className="message-content">{message.content}</div><Citations citations={message.citations}/><SearchSuggestions html={message.search_suggestions_html}/><Artifacts artifacts={message.artifacts} api={api}/>{message.job_id && <button className="inline-action" onClick={onAutomations}>Task queued · View progress<Icon name="arrow" size={14}/></button>}{Boolean(message.approval_needed) && <button className="inline-action" onClick={onAutomations}>Your review is needed · Open approvals<Icon name="arrow" size={14}/></button>}</article>) : <div className="welcome"><span className="welcome-symbol"><Icon name="spark" size={38}/></span><span className="eyebrow">SOME THINGS ARE BETTER, TOGETHER.</span><h2>What’s on your mind?</h2><p>From a small reminder to your next big idea,<br/>I’m here to help you move things forward.</p><div className="suggestions">{suggestions.map(item => <button key={item.title} onClick={() => { setText(item.prompt); input.current?.focus(); }}><Icon name={item.icon} size={21}/><strong>{item.title}</strong><span>{item.detail}</span><Icon name="arrow" size={16}/></button>)}</div></div>}{busy && <div className="thinking" role="status"><span/><span/><span/>Derek is working on it</div>}<div ref={transcriptEnd}/></div><div className="composer-area"><ErrorNotice message={error}/><form className={`composer ${recording ? 'recording' : ''}`} onSubmit={send}>{audio ? <div className="audio-preview"><Icon name="mic"/><span>{audio.name}<small>Ready to send · {(audio.size / 1024).toFixed(0)} KB</small></span><button type="button" className="icon-button" aria-label="Remove audio" onClick={() => setAudio(null)} disabled={busy}><Icon name="close" size={16}/></button></div> : <textarea ref={input} aria-label="Message your assistant" value={text} onChange={event => setText(event.target.value)} placeholder={recording ? 'Recording… click the microphone to finish.' : 'Ask anything, plan something, or get things done…'} disabled={busy || recording || loading} rows={2} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!busy && (text.trim() || audio)) event.currentTarget.form?.requestSubmit(); } }}/>}<div className="composer-bottom"><div className="composer-tools"><button type="button" className={`icon-button ${recording ? 'is-recording' : ''}`} aria-label={recording ? 'Stop recording' : 'Record a voice note'} title={recording ? 'Stop recording' : 'Record voice note'} disabled={busy || loading} onClick={toggleRecording}><Icon name="mic" size={20}/></button><button type="button" className="text-button" disabled={busy || recording || loading} onClick={() => fileInput.current?.click()}>Upload audio</button><input ref={fileInput} type="file" accept="audio/*,.webm,.m4a,.wav,.mp3,.ogg" hidden onChange={event => { selectAudio(event.target.files?.[0]); event.target.value = ''; }}/></div><button type="submit" className="send-button" aria-label="Send message" disabled={busy || recording || loading || (!text.trim() && !audio)}><Icon name="arrow" size={20}/></button></div></form><p className="composer-note">{recording ? 'Recording up to 2 minutes. Review your voice note before sending.' : 'Enter to send · Shift + Enter for a new line · Review important details'}</p></div></section><aside className="chat-history"><div className="section-heading"><h2>Conversations</h2><button className="icon-button" title="New conversation" aria-label="New conversation" disabled={busy} onClick={newConversation}><Icon name="plus" size={18}/></button></div><ErrorNotice message={conversations.error}/>{conversations.loading && !conversations.data ? <Loading/> : conversations.data?.length ? <div className="history-list">{conversations.data.map(item => <div key={item.id} className={`history-item ${conversation === item.id ? 'current' : ''}`}><button className="history-open" disabled={busy} onClick={() => openConversation(item.id)}><span>{item.title || 'Untitled conversation'}</span><small>{dateLabel(item.created_at)}</small></button><button className="icon-button history-delete" title="Delete conversation" aria-label={`Delete ${item.title || 'conversation'}`} disabled={busy} onClick={() => removeConversation(item.id)}><Icon name="close" size={14}/></button></div>)}</div> : <p className="muted quiet">Your conversations will find a home here.</p>}<div className="sidebar-tip"><span className="eyebrow">A LITTLE INSPIRATION</span><p>“Remind me to take a break every afternoon at 3.”</p><span>Small routines. More room to breathe.</span></div></aside></div>;
}
