/** Schedules are evaluated in this timezone (see scheduler/deployments.py). */
export const CRON_TIMEZONE = 'IST';

export const CRON_PRESETS: { label: string; cron: string }[] = [
  { label: 'Every day at 07:30', cron: '30 7 * * *' },
  { label: 'Every day at 09:00 and 18:00', cron: '0 9,18 * * *' },
  { label: 'Weekdays at 09:00', cron: '0 9 * * 1-5' },
  { label: 'Every 6 hours', cron: '0 */6 * * *' },
  { label: 'Every Monday at 08:00', cron: '0 8 * * 1' },
];

const pad = (n: string) => n.padStart(2, '0');
const isNum = (v: string) => /^\d+$/.test(v);

/** Plain-English summary of common cron patterns; falls back to the raw expression. */
export function describeCron(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return expr;
  const [min, hour, dom, mon, dow] = parts;
  const anyDay = dom === '*' && mon === '*';

  const every = /^\*\/(\d+)$/.exec(hour);
  if (anyDay && dow === '*' && min === '0' && every) return `Every ${every[1]} hours`;

  if (!anyDay || !isNum(min)) return expr;
  const hours = hour.split(',');
  if (!hours.every(isNum)) return expr;
  const times = hours.map(h => `${pad(h)}:${pad(min)}`).join(' and ');

  if (dow === '*') return `Every day at ${times} ${CRON_TIMEZONE}`;
  if (dow === '1-5') return `Weekdays at ${times} ${CRON_TIMEZONE}`;
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  if (isNum(dow) && +dow <= 7) return `Every ${days[+dow]} at ${times} ${CRON_TIMEZONE}`;
  return expr;
}
