import { describe, expect, it } from 'vitest';
import { buildPlumeSurface, buildWindField, concentrationColor, createPlumeLayer, createSurfaceBuffers,
    MAX_FIELD_EVALUATIONS, MAX_PARTICLES, MAX_SURFACE_SAMPLES, MAX_SURFACE_VERTICES,
    renderMatrix, selectParticles, selectVisibleParticles, transportVector } from './plumeLayer.js';

const origin = { longitude: -74.65, latitude: 40.35 };

const puff = (x, y = 0, z = 40, color = [1, 0, 0]) => ({ x, y, z, radius: 12, color });

function components(mesh) {
    const roots = new Map();
    const root = key => {
        if (!roots.has(key)) roots.set(key, key);
        while (roots.get(key) !== key) { roots.set(key, roots.get(roots.get(key))); key = roots.get(key); }
        return key;
    };
    const edges = new Map();
    for (let i = 0; i < mesh.vertexCount; i += 3) {
        const keys = [0, 1, 2].map(j => Array.from(mesh.positions.subarray((i + j) * 3, (i + j + 1) * 3)).map(v => v.toFixed(4)).join(','));
        for (let j = 0; j < 3; j++) {
            roots.set(root(keys[j]), root(keys[(j + 1) % 3]));
            const edge = [keys[j], keys[(j + 1) % 3]].sort().join('|');
            edges.set(edge, (edges.get(edge) || 0) + 1);
        }
    }
    return { count: new Set([...roots.keys()].map(root)).size, edges };
}

describe('merged plume geometry', () => {
    it('creates one closed 3D shell for overlapping puffs with smooth normals and blended hazard colors', () => {
        const mesh = buildPlumeSurface([puff(-8), puff(8, 0, 40, [0, 0, 1])]);
        expect(mesh.sparse).toHaveLength(0);
        expect(mesh.mergedClusters).toBe(1);
        expect(mesh.vertexCount).toBeGreaterThan(100);
        const topology = components(mesh);
        expect(topology.count).toBe(1);
        expect([...topology.edges.values()].every(count => count === 2)).toBe(true);
        let blended = false, above = false, below = false, validNormals = true, validColors = true;
        for (let i = 0; i < mesh.vertexCount; i++) {
            validNormals &&= Math.abs(Math.hypot(...mesh.normals.subarray(i * 3, i * 3 + 3)) - 1) < 0.0001;
            const [r, g, b] = mesh.colors.subarray(i * 3, i * 3 + 3);
            validColors &&= Math.abs(r + g + b - 1) < 0.0001;
            blended ||= r > 0.05 && b > 0.05;
            above ||= mesh.positions[i * 3 + 2] > 45;
            below ||= mesh.positions[i * 3 + 2] < 35;
        }
        expect(blended && above && below && validNormals && validColors).toBe(true);
    });

    it('does not bridge disconnected horizontal or vertical clusters and preserves sparse spheres', () => {
        const isolated = puff(500);
        const mesh = buildPlumeSurface([puff(-8), puff(8), puff(-8, 0, 140), puff(8, 0, 140), isolated]);
        expect(mesh.mergedClusters).toBe(2);
        expect(components(mesh).count).toBe(2);
        expect(mesh.sparse).toEqual([isolated]);
        expect(buildPlumeSurface([puff(0), puff(25)]).vertexCount).toBe(0);
    });

    it('is deterministic, does not mutate inputs, and reuses attribute arrays', () => {
        const points = Object.freeze([Object.freeze(puff(-8)), Object.freeze(puff(8))]);
        const before = JSON.stringify(points), buffers = createSurfaceBuffers();
        const first = buildPlumeSurface(points, buffers);
        const positions = first.positions.slice(0, first.vertexCount * 3);
        const second = buildPlumeSurface(points, buffers);
        expect(second.positions).toBe(buffers.positions);
        expect(second.positions.slice(0, second.vertexCount * 3)).toEqual(positions);
        expect(JSON.stringify(points)).toBe(before);
        const empty = buildPlumeSurface([], buffers);
        expect(empty.vertexCount).toBe(0);
        expect(empty.sparse).toEqual([]);
    });

    it('bounds a worst-case dense frame and a widely distributed connected frame', () => {
        for (const points of [
            Array.from({ length: 2000 }, () => puff(0)),
            Array.from({ length: 1600 }, (_, i) => puff((i % 40) * 15, Math.floor(i / 40) * 15)),
        ]) {
            const mesh = buildPlumeSurface(points);
            expect(mesh.vertexCount).toBeGreaterThan(0);
            expect(mesh.vertexCount).toBeLessThanOrEqual(MAX_SURFACE_VERTICES);
            expect(mesh.sampleCount).toBeLessThanOrEqual(MAX_SURFACE_SAMPLES);
            expect(mesh.evaluations).toBeLessThanOrEqual(MAX_FIELD_EVALUATIONS);
            expect(mesh.positions.subarray(0, mesh.vertexCount * 3).every(Number.isFinite)).toBe(true);
        }
    }, 30000);

    it('allows plume visibility changes before initialization without changing wind', () => {
        const layer = createPlumeLayer({ maplibregl: { MercatorCoordinate: {} } });
        expect(() => { layer.setVisible(false); layer.update(null); layer.setVisible(true); }).not.toThrow();
        expect(layer.windLineCount).toBe(0);
    });
});

describe('render-only concentration decluttering', () => {
    it('culls only concentrations below 1% of trace, preserving useful sub-trace mass and physics inputs', () => {
        const particles = Object.freeze([0, 0.019, 0.02, 0.2, 2, 35].map(concentration =>
            Object.freeze({ ...origin, concentration })));
        const before = JSON.stringify(particles);
        const result = selectVisibleParticles(particles, { trace: 2 });
        expect(result.cutoffFraction).toBe(0.01);
        expect(result.cutoffConcentration).toBe(0.02);
        expect(result.culledParticleCount).toBe(2);
        expect(result.particles).toEqual(particles.slice(2));
        expect(result.particles[0]).toBe(particles[2]);
        expect(result.notice).toContain('not declared safe');
        expect(JSON.stringify(particles)).toBe(before);
    });

    it('supports aliases, configurable fractions, disabled filtering, and unknown concentrations', () => {
        const particles = [0, 0.1, 1, undefined, null, NaN].map(concentration => ({ ...origin, concentration }));
        expect(selectVisibleParticles(particles, { traceThreshold: 10 }, 0.05).particles).toEqual(particles.slice(2));
        expect(selectVisibleParticles(particles, { trace: 10 }, 0).particles).toEqual(particles);
        expect(selectVisibleParticles(particles, { trace: 0 }).particles).toEqual(particles);
        expect(selectVisibleParticles(particles, { trace: 10 }, NaN).cutoffFraction).toBe(0.01);
        expect(selectVisibleParticles().particles).toEqual([]);
    });

    it('filters before applying the render cap, so negligible puffs do not consume useful slots', () => {
        const particles = Array.from({ length: 3200 }, (_, i) => ({ ...origin, concentration: i % 2 ? 1 : 0 }));
        const result = selectVisibleParticles(particles, { trace: 2 });
        expect(result.particles).toHaveLength(MAX_PARTICLES);
        expect(result.particles.every(p => p.concentration === 1)).toBe(true);
        expect(result.culledParticleCount).toBe(1600);
    });
});

describe('physical plume layer helpers', () => {
    it('maps the actual threshold stops to saturated blue/cyan/yellow/red', () => {
        const thresholds = { trace: 2, pel: 8, idlh: 35 };
        expect([0, 2, 8, 35, 100].map(value => concentrationColor(value, thresholds)))
            .toEqual(['#1767ff', '#00d9fa', '#ffe32b', '#fa263f', '#fa263f']);
        expect(concentrationColor(4, thresholds)).not.toEqual(concentrationColor(4));
    });

    it('converts meteorological FROM bearings to actual transport, including zero and calm', () => {
        const northWind = transportVector({ windDirectionFromDegrees: 0, windSpeedMetersPerSecond: 7 });
        expect(northWind.east).toBeCloseTo(0);
        expect(northWind.north).toBeCloseTo(-7);
        expect(transportVector({ windDirectionFromDegrees: 270, windSpeedMetersPerSecond: 7 }).east).toBeCloseTo(7);
        expect(Math.hypot(...Object.values(transportVector({ windSpeedMetersPerSecond: 0 })))).toBe(0);
    });

    it('retains all points under cap without mutation or cluster aggregation', () => {
        const particles = Array.from({ length: 1500 }, (_, i) => Object.freeze({ ...origin, altitudeMeters: i, clusterId: 1 }));
        const selected = selectParticles(Object.freeze(particles));
        expect(selected).toEqual(particles);
        expect(selected[1499]).toBe(particles[1499]);
        const large = Array.from({ length: 3000 }, (_, i) => ({ ...origin, altitudeMeters: i }));
        const capped = selectParticles(large);
        expect(capped).toHaveLength(MAX_PARTICLES);
        expect(capped[0]).toBe(large[0]);
        expect(capped.at(-1)).toBe(large.at(-1));
    });

    it('supports MapLibre v3 and v6 render matrix inputs', () => {
        const matrix = new Float64Array(16);
        expect(renderMatrix(matrix)).toBe(matrix);
        expect(renderMatrix({ defaultProjectionData: { mainMatrix: matrix } })).toBe(matrix);
        expect(renderMatrix({})).toBeNull();
        expect(() => createPlumeLayer()).toThrow('MercatorCoordinate');
    });

    it('generates bounded deterministic world paths above the supplied rendered DEM', () => {
        const options = { origin, weather: { windDirectionFromDegrees: 270, windSpeedMetersPerSecond: 5 }, ground: () => 240 };
        const field = buildWindField(options);
        expect(field).toHaveLength(110);
        expect(field).toEqual(buildWindField(options));
        expect(field.every(line => line.length <= 29 && line.every(point =>
            Math.abs(point.x) <= 1500 && Math.abs(point.y) <= 1500 && point.z === 246))).toBe(true);
        expect(field.every(line => line.at(-1).x > line[0].x && Math.abs(line.at(-1).y - line[0].y) < 0.000001)).toBe(true);
    });

    it('uses backend vector directions instead of prevailing weather and hides calm wind', () => {
        const field = buildWindField({ origin, weather: { windDirectionFromDegrees: 270 },
            windVectors: [{ ...origin, eastMetersPerSecond: 0, northMetersPerSecond: -4 }] });
        expect(field[0].at(-1).y).toBeLessThan(field[0][0].y);
        expect(field[0].at(-1).x).toBeCloseTo(field[0][0].x);
        expect(buildWindField({ origin, weather: { windSpeedMetersPerSecond: 0 } })).toEqual([]);
    });

    it('lifts the field above roof bounds rather than drawing through buildings', () => {
        const buildings = [{ levels: 10, polygon: [
            [-74.67, 40.33], [-74.63, 40.33], [-74.63, 40.37], [-74.67, 40.37],
        ] }];
        const field = buildWindField({ origin, buildings, ground: () => 100 });
        expect(field[0][0].z).toBe(138);
    });
});
