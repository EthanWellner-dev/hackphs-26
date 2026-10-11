export const timelineStart = 15 * 60;
export const timelineEnd = (24 + 8) * 60;

export function readMarkdownTable(markdown: string, heading: string): string[][] {
  const section = markdown.split(`## ${heading}`)[1]?.split(/\r?\n## /)[0];
  if (!section) throw new Error(`Missing schedule section: ${heading}`);
  return section.split(/\r?\n/)
    .filter((line) => line.startsWith('|'))
    .map((line) => line.split('|').slice(1, -1).map((cell) => cell.trim()))
    .filter((row) => !row.every((cell) => /^:?-+:?$/.test(cell)));
}

export function targetWindow(window: string): { start: number; end: number } | null {
  if (window === 'After verified freeze only') return null;
  const match = /^(Sat|Sun) (\d{1,2}):(\d{2})(?: (AM|PM))?–(?:(Sat|Sun) )?(\d{1,2}):(\d{2}) (AM|PM)$/.exec(window);
  if (!match) throw new Error(`Unsupported target window: ${window}`);
  const [, day, hour, minute, period, endDay, endHour, endMinute, endPeriod] = match;
  const minutes = (day: string, hour: string, minute: string, period: string) =>
    (day === 'Sun' ? 1440 : 0) + (Number(hour) % 12 + (period === 'PM' ? 12 : 0)) * 60 + Number(minute);
  const start = minutes(day, hour, minute, period || endPeriod);
  const end = minutes(endDay || day, endHour, endMinute, endPeriod);
  if (end <= start) throw new Error(`Invalid target window: ${window}`);
  return { start, end };
}

export function hourOverlap(window: { start: number; end: number }, hour: number) {
  const start = Math.max(window.start, hour);
  const end = Math.min(window.end, hour + 60);
  return end > start ? { offset: (start - hour) / 60 * 100, width: (end - start) / 60 * 100 } : null;
}
