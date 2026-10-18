type Pending = { id: string; commandId?: string };
export type ChatState = { conversation: string | null; pending: Pending | null };
export function stateKey(token: string, base: string): string {
  // An opaque per-session namespace, not an authentication mechanism. The
  // stored value contains IDs only, never the token or message contents.
  let hash = 2166136261;
  for (const char of token + base) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return `derek.chat.${(hash >>> 0).toString(16)}`;
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function readChat(key: string): ChatState {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '{}');
    return {
      conversation:
        typeof value.conversation === 'string' && uuid.test(value.conversation) ? value.conversation : null,
      pending:
        value.pending && uuid.test(value.pending.id)
          ? {
              id: value.pending.id,
              ...(uuid.test(value.pending.commandId || '') ? { commandId: value.pending.commandId } : {}),
            }
          : null,
    };
  } catch {
    return { conversation: null, pending: null };
  }
}
export function saveChat(key: string, value: ChatState) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* IDs can still live in this tab when storage is unavailable. */
  }
}
