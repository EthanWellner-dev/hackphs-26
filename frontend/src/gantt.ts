import markdown from '../../gantt.md?raw';
import { hourOverlap, readMarkdownTable, targetWindow, timelineEnd, timelineStart } from './ganttData';
import './gantt.css';

function cell(tag: 'td' | 'th', text: string, className = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  if (tag === 'th') element.setAttribute('scope', 'col');
  return element;
}

function caption(table: HTMLTableElement, text: string) {
  table.createCaption().textContent = text;
}

const schedule = document.querySelector<HTMLTableElement>('#schedule')!;
const priority = document.querySelector<HTMLSelectElement>('#priority')!;
const [, ...workstreams] = readMarkdownTable(markdown, 'Workstream schedule and current status');
const hours = Array.from({ length: (timelineEnd - timelineStart) / 60 }, (_, i) => timelineStart + i * 60);
const colors: Record<string, string> = { P0: 'core', P1: 'polish', Optional: 'optional', P2: 'stretch' };

function renderSchedule() {
  schedule.replaceChildren();
  caption(schedule, 'Original target windows · All times EDT · Audited October 11, 2026');
  const head = schedule.createTHead();
  const days = head.insertRow();
  const summary = cell('th', 'Workstream / audited status', 'workstream');
  summary.rowSpan = 2;
  days.append(summary);
  for (const [text, span] of [['Saturday · Oct 10', 9], ['Sunday · Oct 11', 8]] as const) {
    const day = cell('th', text, 'day');
    day.colSpan = span;
    day.scope = 'colgroup';
    days.append(day);
  }
  const gate = cell('th', 'Exit gate / remaining work', 'exit-gate');
  gate.rowSpan = 2;
  days.append(gate);
  const ticks = head.insertRow();
  for (const hour of hours) {
    const h = hour / 60 % 24;
    ticks.append(cell('th', `${h % 12 || 12}${h < 12 ? 'a' : 'p'}`, 'tick'));
  }
  const body = schedule.createTBody();
  const visible = workstreams.filter((row) => priority.value === 'all' || row[3] === priority.value);
  for (const [name, windowText, status, level, exit] of visible) {
    const row = body.insertRow();
    const label = cell('th', '', 'workstream');
    label.scope = 'row';
    const title = document.createElement('strong');
    title.textContent = name;
    const windowLabel = document.createElement('span');
    windowLabel.className = 'window-label';
    windowLabel.textContent = windowText;
    const badge = document.createElement('span');
    badge.className = `badge ${colors[level] || 'stretch'}`;
    badge.textContent = level;
    const state = document.createElement('span');
    state.className = 'state';
    state.textContent = status;
    label.append(title, windowLabel, badge, state);
    row.append(label);
    const window = targetWindow(windowText);
    if (!window) {
      const deferred = cell('td', 'Deferred · after verified freeze only', 'deferred');
      deferred.colSpan = hours.length;
      row.append(deferred);
    } else {
      for (const hour of hours) {
        const block = cell('td', '', `time-cell ${hour === 1440 ? 'midnight' : ''}`);
        const overlap = hourOverlap(window, hour);
        if (overlap) {
          const bar = document.createElement('span');
          bar.className = `bar ${colors[level] || 'stretch'}`;
          bar.style.left = `${overlap.offset}%`;
          bar.style.width = `${overlap.width}%`;
          bar.setAttribute('aria-hidden', 'true');
          block.title = `${name}: ${windowText} EDT — ${status}`;
          block.append(bar);
        }
        row.append(block);
      }
    }
    row.append(cell('td', exit, 'exit-gate'));
  }
  document.querySelector('#row-count')!.textContent = `${visible.length} of ${workstreams.length} workstreams shown`;
}

const gates = document.querySelector<HTMLTableElement>('#gates')!;
const [gateHeaders, ...gateRows] = readMarkdownTable(markdown, 'Milestone acceptance gates');
caption(gates, 'Acceptance requires evidence, not elapsed time.');
const header = gates.createTHead().insertRow();
gateHeaders.forEach((text) => header.append(cell('th', text)));
const body = gates.createTBody();
gateRows.forEach((values) => {
  const row = body.insertRow();
  values.forEach((text, index) => {
    const entry = cell(index === 0 ? 'th' : 'td', text);
    if (index === 0) entry.setAttribute('scope', 'row');
    row.append(entry);
  });
});
priority.addEventListener('change', renderSchedule);
renderSchedule();
