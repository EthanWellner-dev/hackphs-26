import { describe, it, expect, vi } from 'vitest';
vi.mock('three', async importOriginal => {
    const three = await importOriginal();
    return { ...three, WebGLRenderer: class { dispose() {} } };
});
import { createPlumeLayer } from './plumeLayer.js';

describe('plume renderer initialization', () => {
    it('creates all meshes before accepting data and cleans up', () => {
        const layer = createPlumeLayer({ maplibregl: { MercatorCoordinate: {
            fromLngLat: ([longitude, latitude], altitude = 0) => ({ x: longitude / 360, y: latitude / 360, z: altitude / 40000000, meterInMercatorCoordinateUnits: () => 1 / 40000000 }),
        } } });
        const map = { getCanvas: () => ({}), on: vi.fn(), off: vi.fn(), triggerRepaint: vi.fn(), getTerrain: () => null };
        const frame = { sourceLocation: { longitude: -74.65, latitude: 40.35 }, particles: [{ longitude: -74.65, latitude: 40.35, altitudeMeters: 20, radiusMeters: 12, concentration: 2 }] };
        expect(() => layer.update(frame)).not.toThrow();
        expect(() => layer.onAdd(map, {})).not.toThrow();
        expect(layer.particleCount).toBe(1);
        expect(() => layer.update(frame)).not.toThrow();
        expect(() => layer.onRemove()).not.toThrow();
    });
});
