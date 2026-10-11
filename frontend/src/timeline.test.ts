import { describe, expect, it } from 'vitest';
// @ts-ignore JavaScript helpers are shared with the map entry point.
import { TimelineFrames, timelineMinute, formatConcentration, releaseMass, mergeWeatherTimeline } from './timeline.js';

describe('scenario-scoped timeline cache', () => {
    it('deduplicates requests and bounds the cache to 25 five-minute frames', async () => {
        let calls = 0;
        const frames = new TimelineFrames(async (timeMinutes: number) => { calls++; return { timeMinutes }; });
        await Promise.all([frames.get(31), frames.get(30)]);
        expect(calls).toBe(1);
        for (let minute = -10; minute < 140; minute++) await frames.get(minute);
        expect(frames.cache.size).toBe(25);
        expect(timelineMinute(123)).toBe(120);
    });
    it('does not let a stale weather/scenario response refill the cache', async () => {
        let complete!: (value: unknown) => void;
        const frames = new TimelineFrames(() => new Promise(resolve => { complete = resolve; }));
        const pending = frames.get(30);
        frames.invalidate();
        complete({ timeMinutes: 30, maxConcentration: 54 });
        expect(await pending).toBeNull();
        expect(frames.cache.size).toBe(0);
    });
    it('retains earlier winds when a refresh changes the future forecast', () => {
        const previous = [{ minutesFromNow: 0, windDirectionFromDegrees: 90 }, { minutesFromNow: 5, windDirectionFromDegrees: 90 }];
        const incoming = [{ minutesFromNow: 0, windDirectionFromDegrees: 180 }, { minutesFromNow: 5, windDirectionFromDegrees: 200 }];
        expect(mergeWeatherTimeline(previous, incoming, 5)).toEqual([previous[0], { minutesFromNow: 5, windDirectionFromDegrees: 180 }, { minutesFromNow: 10, windDirectionFromDegrees: 200 }]);
    });
});

describe('truthful metrics', () => {
    it('distinguishes missing, zero, and small nonzero concentrations', () => {
        expect(formatConcentration(null)).toBe('Unavailable');
        expect(formatConcentration(0)).toBe('0 ppm');
        expect(formatConcentration(0.00012)).toBe('1.20e-4 ppm');
        expect(formatConcentration(2, 'Bq/m³')).toContain('Bq/m³');
    });
    it('derives total release mass including an impulse', () => {
        expect(releaseMass({ rateKgPerSecond: 0.01, durationMinutes: 10, impulseMassKg: 4 })).toBe(10);
    });
});
