import type { Schedule } from './types';
const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
export function scheduleLabel(schedule: Schedule): string {
  if (schedule.kind === 'once') {
    if (!schedule.at) return 'One time';
    const date = new Date(schedule.at);
    return Number.isNaN(date.getTime())
      ? schedule.at
      : new Intl.DateTimeFormat('en-IN', {
          dateStyle: 'medium',
          timeStyle: 'short',
          timeZone: schedule.timezone,
        }).format(date) + ` · ${schedule.timezone}`;
  }
  const time = schedule.time || '00:00';
  const [hour, minute] = time.split(':').map(Number);
  const label = `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`;
  const repeat =
    schedule.kind === 'daily'
      ? 'Every day'
      : schedule.weekdays?.join(',') === '0,1,2,3,4'
        ? 'Weekdays'
        : (schedule.weekdays || []).map((day) => days[day]).join(', ');
  return `${repeat} at ${label} · ${schedule.timezone}`;
}
export function localDateInput(value?: string): string {
  if (!value) return '';
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: 'Asia/Kolkata',
  }).formatToParts(new Date(value));
  const get = (type: string) => parts.find((part) => part.type === type)?.value || '';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
}
