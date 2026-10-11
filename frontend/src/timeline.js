export const timelineMinute = (value) => Math.max(0, Math.min(120, Math.round((Number(value) || 0) / 5) * 5));

// One bounded cache per immutable scenario/context revision, never per camera angle.
export class TimelineFrames {
    constructor(load) {
        this.load = load;
        this.revision = 0;
        this.cache = new Map();
        this.pending = new Map();
    }
    invalidate() {
        this.revision++;
        for (const request of this.pending.values()) request.controller.abort();
        this.pending.clear();
        this.cache.clear();
    }
    seed(frame) {
        if (frame && Number.isFinite(frame.timeMinutes)) this.cache.set(timelineMinute(frame.timeMinutes), frame);
    }
    async get(value) {
        const minute = timelineMinute(value);
        if (this.cache.has(minute)) return this.cache.get(minute);
        if (this.pending.has(minute)) return this.pending.get(minute).promise;
        const revision = this.revision;
        const controller = new AbortController();
        const promise = this.load(minute, controller.signal).then(frame => {
            if (revision !== this.revision) return null;
            this.cache.set(minute, frame);
            return frame;
        }).finally(() => {
            if (this.pending.get(minute)?.controller === controller) this.pending.delete(minute);
        });
        this.pending.set(minute, { controller, promise });
        return promise;
    }
    cancelExcept(minute) {
        for (const [key, request] of this.pending) {
            if (key !== minute) { request.controller.abort(); this.pending.delete(key); }
        }
    }
}

export function formatConcentration(value, unit = 'ppm') {
    if (value == null || !Number.isFinite(Number(value))) return 'Unavailable';
    const amount = Number(value);
    if (amount === 0) return `0 ${unit}`;
    return `${amount < 0.01 ? amount.toExponential(2) : amount.toLocaleString(undefined, { maximumFractionDigits: 3 })} ${unit}`;
}

export function releaseMass(release) {
    if (!release) return null;
    const continuous = release.mode === 'IMPULSIVE' ? 0 : Number(release.rateKgPerSecond || 0) * Number(release.durationMinutes || 0) * 60;
    return continuous + (release.mode === 'CONTINUOUS' ? 0 : Number(release.impulseMassKg || 0));
}

export function mergeWeatherTimeline(previous, incoming, elapsedMinutes) {
    const retained = (previous || []).filter(point => point.minutesFromNow < elapsedMinutes);
    const forecast = (incoming || []).map(point => ({ ...point, minutesFromNow: point.minutesFromNow + elapsedMinutes }));
    return [...retained, ...forecast].filter(point => point.minutesFromNow <= 120);
}
