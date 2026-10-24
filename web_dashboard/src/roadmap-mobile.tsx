import { createRoot } from 'react-dom/client';
import { Api } from './api';
import { Roadmap } from './Roadmap';
import './roadmap-mobile.css';

// Static Pages host: this adapter never contacts Derek or accepts credentials.
// Edits belong to this browser. Export JSON or copy prompts to transfer them.
class SnapshotApi extends Api {
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (path !== '/v1/roadmap/') throw new Error('Unavailable in the portable roadmap.');
    const key = 'derek.roadmap.mobile.v1';
    let saved = localStorage.getItem(key);
    if (!saved) {
      const response = await fetch('./catalog.json');
      if (!response.ok) throw new Error('Roadmap catalog unavailable. Reload when online.');
      saved = JSON.stringify({ version: 1, items: await response.json() });
      localStorage.setItem(key, saved);
    }
    const current = JSON.parse(saved);
    if (options.method === 'PUT') {
      const next = JSON.parse(String(options.body));
      if (next.version !== current.version) throw new Error('Changed in another tab. Reload first.');
      if (next.items.some((b: {status: string; test_result: string; evidence: string}) => (b.status === 'verified' || b.test_result === 'passed') && !b.evidence.trim())) throw new Error('Record evidence before marking passed or verified.');
      next.version++;
      localStorage.setItem(key, JSON.stringify(next));
      return next as T;
    }
    return current as T;
  }
}
const api = new SnapshotApi('');
createRoot(document.getElementById('root')!).render(<><div className="mobile-notice"><strong>Portable roadmap · snapshot dated October 23, 2026</strong><p>Works from your phone while the laptop is off. Saves stay in this browser; they do not sync to Derek. Export JSON or copy a prompt to transfer changes. No laptop status, private notes or runtime controls are published.</p></div><Roadmap api={api} portable /></>);
