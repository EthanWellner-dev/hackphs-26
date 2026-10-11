import { describe, expect, it, vi } from 'vitest';
// @ts-ignore shared JavaScript module
import { ForecastPlayback } from './playback.js';

describe('two-hour forecast playback', () => {
    it('renders every five-minute step and stops at two hours', async () => {
        vi.useFakeTimers();
        const render = vi.fn();
        const player = new ForecastPlayback({ load: async (timeMinutes: number) => ({ timeMinutes }), render, status: vi.fn() });
        const playing = player.play();
        await vi.runAllTimersAsync();
        await playing;
        expect(render.mock.calls.map(([frame]) => frame.timeMinutes)).toEqual(Array.from({ length: 25 }, (_, i) => i * 5));
        expect(player.playing).toBe(false);
        vi.useRealTimers();
    });
    it('pause prevents an in-flight result from moving the timeline', async () => {
        let finish!: (frame: unknown) => void;
        const render = vi.fn();
        const player = new ForecastPlayback({ load: () => new Promise(resolve => { finish = resolve; }), render, status: vi.fn() });
        const running = player.play();
        player.stop();
        finish({ timeMinutes: 0 });
        await running;
        expect(render).not.toHaveBeenCalled();
    });
    it('a failed frame pauses without skipping ahead', async () => {
        const status = vi.fn();
        const player = new ForecastPlayback({ load: async () => { throw new Error('offline'); }, render: vi.fn(), status });
        await player.play(60);
        expect(player.playing).toBe(false);
        expect(status).toHaveBeenLastCalledWith('error');
    });
});
