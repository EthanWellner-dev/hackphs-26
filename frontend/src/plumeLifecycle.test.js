import { describe, it, expect, vi } from 'vitest';
const { meshes } = vi.hoisted(() => ({ meshes: [] }));
vi.mock('three', async importOriginal => {
    const three = await importOriginal();
    return { ...three, WebGLRenderer: class { dispose() {} },
        InstancedMesh: class extends three.InstancedMesh {
            constructor(...args) { super(...args); meshes.push(this); }
        } };
});
import { Matrix4 } from 'three';
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
        const overlapping = { ...frame, particles: [frame.particles[0], { ...frame.particles[0], longitude: -74.65001 }] };
        expect(() => layer.update(overlapping)).not.toThrow();
        expect(layer.particleCount).toBe(2);
        const mesh = meshes.at(-1);
        const second = new Matrix4();
        mesh.getMatrixAt(1, second);
        expect(second.elements[0]).toBeCloseTo(12);
        expect(second.elements[12]).not.toBe(0);
        expect(second.elements[14]).toBeCloseTo(20);
        expect(layer.mergedClusterCount).toBe(0);
        expect(layer.surfaceVertexCount).toBe(0);
        const dense = { ...frame, particles: Array.from({ length: 500 }, (_, i) => ({
            ...frame.particles[0], longitude: -74.65 + i * 0.0000001,
        })) };
        expect(() => layer.update(dense)).not.toThrow();
        expect(layer.particleCount).toBe(500);
        expect(mesh.count).toBe(500);
        for (let i = 0; i < 500; i++) {
            mesh.getMatrixAt(i, second);
            expect(second.elements[0]).toBeCloseTo(12);
            expect(second.elements[14]).toBeCloseTo(20);
        }
        layer.update({ ...dense, thresholds: { trace: 0.5 }, particles: dense.particles.map((p, i) => ({
            ...p, concentration: i < 250 ? 0.004 : 0.005,
        })) });
        expect(layer.particleCount).toBe(250);
        expect(mesh.count).toBe(250);
        expect(layer.visualFilter.culledParticleCount).toBe(250);
        layer.update({ ...frame, particles: [{ ...frame.particles[0], concentration: 0.001 }] });
        expect(mesh.count).toBe(0);
        expect(() => layer.update(frame)).not.toThrow();
        expect(mesh.count).toBe(1);
        expect(() => layer.onRemove()).not.toThrow();
    });
});
