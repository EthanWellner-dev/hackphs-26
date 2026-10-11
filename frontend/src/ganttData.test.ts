import { describe, expect, it } from 'vitest';
import markdown from '../../gantt.md?raw';
import { hourOverlap, readMarkdownTable, targetWindow, timelineStart, timelineEnd } from './ganttData';

describe('Gantt document rendering data', () => {
  it('reads every workstream and gate from the source document', () => {
    const [headers, ...rows] = readMarkdownTable(markdown, 'Workstream schedule and current status');
    expect(headers).toHaveLength(5);
    expect(rows).toHaveLength(16);
    expect(rows.every((row) => row.length === 5)).toBe(true);
    expect(readMarkdownTable(markdown, 'Milestone acceptance gates')).toHaveLength(9);
    for (const row of rows) {
      const window = targetWindow(row[1]);
      if (window) {
        expect(window.start).toBeGreaterThanOrEqual(timelineStart);
        expect(window.end).toBeLessThanOrEqual(timelineEnd);
      }
    }
  });

  it('keeps exact minute boundaries and infers a shared AM/PM suffix', () => {
    expect(targetWindow('Sat 3:15–4:00 PM')).toEqual({ start: 915, end: 960 });
    const window = targetWindow('Sat 8:00–8:20 PM')!;
    expect(hourOverlap(window, 1200)?.offset).toBe(0);
    expect(hourOverlap(window, 1200)?.width).toBeCloseTo(100 / 3);
    expect(hourOverlap(window, 1260)).toBeNull();
  });

  it('places cross-midnight work and Sunday freeze correctly', () => {
    expect(targetWindow('Sat 11:30 PM–Sun 1:00 AM')).toEqual({ start: 1410, end: 1500 });
    expect(targetWindow('Sun 7:30–8:00 AM')).toEqual({ start: 1890, end: 1920 });
    expect(targetWindow('After verified freeze only')).toBeNull();
  });

  it('fails visibly for unsupported source formats instead of inventing dates', () => {
    expect(() => targetWindow('Whenever')).toThrow('Unsupported target window');
    expect(() => readMarkdownTable('', 'Missing')).toThrow('Missing schedule section');
  });
});
