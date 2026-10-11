import { describe, expect, it, vi } from 'vitest';
import { createDispatchPayload, submitDispatch, toggleDispatchInput } from './aiDispatch';

describe('AI dispatch orb helpers', () => {
  it('toggles the dispatch input open and closed', () => {
    expect(toggleDispatchInput(false)).toBe(true);
    expect(toggleDispatchInput(true)).toBe(false);
  });

  it('submits a trimmed dispatch payload without browser APIs', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ assistantText: 'Wind update accepted', scenario: { version: 2 } }),
    });

    const response = await submitDispatch(fetcher, '/api/dispatch', '  wind shifted southwest  ', { version: 1 }, { source: 'DEMO' });

    expect(fetcher).toHaveBeenCalledWith('/api/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...createDispatchPayload('wind shifted southwest', { version: 1 }, { source: 'DEMO' }), timeMinutes: 30 }),
    });
    expect(response.assistantText).toBe('Wind update accepted');
  });

  it('rejects empty dispatch text before making a request', async () => {
    const fetcher = vi.fn();
    await expect(submitDispatch(fetcher, '/api/dispatch', '   ', {}, null)).rejects.toThrow('Dispatch text is required');
    expect(fetcher).not.toHaveBeenCalled();
  });
});
