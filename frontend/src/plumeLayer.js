import * as THREE from 'three';

export const MAX_PARTICLES = 1600;
const WIND_COUNT = 110;
const WIND_STEPS = 28;
const METERS_PER_DEGREE = 111320;
const PALETTE = ['#1767ff', '#00d9fa', '#ffe32b', '#fa263f'];
const finite = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

/** Threshold stops are 0=blue, TRACE=cyan, PEL=yellow, IDLH=red. */
export function concentrationColor(concentration, thresholds = {}) {
    const trace = Math.max(0.000001, finite(thresholds.trace ?? thresholds.traceThreshold, 0.5));
    const pel = Math.max(trace + 0.000001, finite(thresholds.pel ?? thresholds.pelThreshold, 1));
    const idlh = Math.max(pel + 0.000001, finite(thresholds.idlh ?? thresholds.idlhThreshold, 10));
    const stops = [0, trace, pel, idlh];
    const value = Math.max(0, finite(concentration));
    const index = value <= trace ? 0 : value <= pel ? 1 : 2;
    const fraction = clamp((value - stops[index]) / (stops[index + 1] - stops[index]), 0, 1);
    return `#${[1, 3, 5].map(offset => {
        const start = parseInt(PALETTE[index].slice(offset, offset + 2), 16);
        const end = parseInt(PALETTE[index + 1].slice(offset, offset + 2), 16);
        return Math.round(start + (end - start) * fraction).toString(16).padStart(2, '0');
    }).join('')}`;
}

export function transportVector(weather = {}) {
    const bearing = (finite(weather.windDirectionFromDegrees, 225) + 180) * Math.PI / 180;
    const speed = Math.max(0, finite(weather.windSpeedMetersPerSecond, 4.5));
    return { east: Math.sin(bearing) * speed, north: Math.cos(bearing) * speed };
}

export function renderMatrix(input) {
    const matrix = input?.defaultProjectionData?.mainMatrix ?? input;
    return matrix?.length === 16 ? matrix : null;
}

/** Keep every point under the cap, and distribute larger frames across their full extent. */
export function selectParticles(particles = [], limit = MAX_PARTICLES) {
    const valid = particles.filter(p => Number.isFinite(p.longitude) && Number.isFinite(p.latitude)
        && Math.abs(p.latitude) < 85.051129 && Math.abs(p.longitude) <= 180);
    if (limit <= 0) return [];
    if (valid.length <= limit) return valid;
    if (limit === 1) return [valid[0]];
    return Array.from({ length: limit }, (_, i) => valid[Math.floor(i * (valid.length - 1) / (limit - 1))]);
}

export const DEFAULT_VISUAL_CUTOFF_FRACTION = 0.01;

/** Display decluttering only: never a health/safety threshold or a physics filter.
 * Unknown concentrations stay visible; zero disables concentration culling. */
export function selectVisibleParticles(particles = [], thresholds = {}, cutoffFraction = DEFAULT_VISUAL_CUTOFF_FRACTION) {
    const fraction = clamp(finite(cutoffFraction, DEFAULT_VISUAL_CUTOFF_FRACTION), 0, 1);
    const trace = Math.max(0, finite(thresholds.trace ?? thresholds.traceThreshold, 0.5));
    const cutoffConcentration = trace * fraction;
    const eligible = particles.filter(p => p.concentration == null || !Number.isFinite(Number(p.concentration))
        || Number(p.concentration) >= cutoffConcentration || cutoffConcentration === 0);
    return {
        particles: selectParticles(eligible), cutoffFraction: fraction, cutoffConcentration,
        culledParticleCount: particles.length - eligible.length,
        notice: 'Visual cutoff only; hidden concentrations are not declared safe. Physics and exposure data are unchanged.',
    };
}

function localCoordinates(origin) {
    const longitudeScale = METERS_PER_DEGREE * Math.cos(origin.latitude * Math.PI / 180);
    return {
        toLocal: (longitude, latitude) => [(longitude - origin.longitude) * longitudeScale, (latitude - origin.latitude) * METERS_PER_DEGREE],
        toLngLat: (east, north) => [origin.longitude + east / longitudeScale, origin.latitude + north / METERS_PER_DEGREE],
    };
}

function buildingBounds(buildings, toLocal) {
    return buildings.slice(0, 250).flatMap(building => {
        const points = (building.polygon || []).filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1])).map(p => toLocal(...p));
        if (points.length < 3) return [];
        return [{
            minX: Math.min(...points.map(p => p[0])), maxX: Math.max(...points.map(p => p[0])),
            minY: Math.min(...points.map(p => p[1])), maxY: Math.max(...points.map(p => p[1])),
            height: Math.max(3, finite(building.heightMeters, finite(building.levels, 3) * 3.2)),
        }];
    });
}

/** Fixed incident-space seeds; ground() returns rendered DEM elevation in meters.
 * Local slopes/footprint steering are illustrative, not a CFD solution. */
export function buildWindField({ origin, weather = {}, windVectors = [], buildings = [], ground = () => 0 }) {
    const { toLocal, toLngLat } = localCoordinates(origin);
    const bounds = buildingBounds(buildings, toLocal);
    const vectors = windVectors.slice(0, 100).filter(v => Number.isFinite(v.longitude) && Number.isFinite(v.latitude)
        && Number.isFinite(v.eastMetersPerSecond) && Number.isFinite(v.northMetersPerSecond)).map(v => ({
        point: toLocal(v.longitude, v.latitude), east: v.eastMetersPerSecond, north: v.northMetersPerSecond,
    }));
    const base = transportVector(weather);
    const cache = new Map();
    const elevation = (x, y) => {
        const key = `${Math.round(x / 12)},${Math.round(y / 12)}`;
        if (!cache.has(key)) cache.set(key, finite(ground(...toLngLat(x, y))));
        return cache.get(key);
    };
    const sample = (x, y) => {
        let east = base.east, north = base.north;
        if (vectors.length) {
            let weight = 0;
            east = 0; north = 0;
            for (const vector of vectors) {
                const w = 1 / Math.max(100, (x - vector.point[0]) ** 2 + (y - vector.point[1]) ** 2);
                east += vector.east * w; north += vector.north * w; weight += w;
            }
            east /= weight; north /= weight;
        } else {
            const speed = Math.hypot(east, north);
            // Small cross-wind slope response cannot reverse the authoritative transport.
            const dx = (elevation(x + 20, y) - elevation(x - 20, y)) / 40;
            const dy = (elevation(x, y + 20) - elevation(x, y - 20)) / 40;
            const crossSlope = speed > 0 ? (-north * dx + east * dy) / speed : 0;
            const bend = clamp(-crossSlope * 0.5, -0.35, 0.35);
            [east, north] = [east - north * bend, north + east * bend];
            for (const box of bounds) {
                const cx = (box.minX + box.maxX) / 2, cy = (box.minY + box.maxY) / 2;
                const influence = Math.max(box.maxX - box.minX, box.maxY - box.minY) / 2 + 45;
                const distance = Math.hypot(x - cx, y - cy);
                if (distance > influence || speed < 0.01) continue;
                const side = Math.sign((x - cx) * -north + (y - cy) * east) || 1;
                const bend = side * 0.65 * (1 - distance / influence);
                [east, north] = [east - north * bend, north + east * bend];
            }
        }
        return { east, north };
    };
    const surface = (x, y) => {
        let height = elevation(x, y);
        for (const box of bounds) {
            // Padded bounds lift the approaching path before it meets the roof edge.
            const distance = Math.hypot(Math.max(box.minX - x, 0, x - box.maxX), Math.max(box.minY - y, 0, y - box.maxY));
            if (distance < 35) height = Math.max(height, elevation((box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2) + box.height * (1 - distance / 35));
        }
        return height + 6;
    };
    const lines = [];
    for (let i = 0; i < WIND_COUNT; i++) {
        // Deterministic jitter avoids a rigid grid without changing seeds on frame/camera updates.
        let x = ((i % 11) - 5) * 200 + Math.sin(i * 12.9898) * 38;
        let y = (Math.floor(i / 11) - 4.5) * 220 + Math.cos(i * 7.233) * 38;
        const line = [];
        let distance = (i * 37) % 130;
        for (let step = 0; step <= WIND_STEPS; step++) {
            const velocity = sample(x, y);
            const speed = Math.hypot(velocity.east, velocity.north);
            if (speed < 0.05 || Math.abs(x) > 1500 || Math.abs(y) > 1500) break;
            line.push({ x, y, z: surface(x, y), distance, speed });
            x += velocity.east / speed * 12;
            y += velocity.north / speed * 12;
            distance += 12;
        }
        if (line.length > 1) lines.push(line);
    }
    return lines;
}

// Hard per-frame budgets. Adaptive sampling is independent of the camera.
export const MAX_SURFACE_SAMPLES = 30000;
export const MAX_SURFACE_VERTICES = 240000;
export const MAX_FIELD_EVALUATIONS = 1500000;
const ISO_LEVEL = 0.125;
const SUPPORT = Math.SQRT2;
const TETRAHEDRA = [[0, 5, 1, 6], [0, 1, 2, 6], [0, 2, 3, 6], [0, 3, 7, 6], [0, 7, 4, 6], [0, 4, 5, 6]];

/** Reused scalar/gradient/color workspace and GPU attribute storage. */
export function createSurfaceBuffers() {
    return {
        positions: new Float32Array(MAX_SURFACE_VERTICES * 3),
        normals: new Float32Array(MAX_SURFACE_VERTICES * 3),
        colors: new Float32Array(MAX_SURFACE_VERTICES * 3),
        field: new Float32Array(MAX_SURFACE_SAMPLES * 7),
    };
}

/** Compact-support metaballs, grouped by actual 3D sphere contact (not clusterId).
 * Inputs are incident-local meters and linear RGB. Disjoint puffs never share a field.
 * Dense surfaces replace their spheres, rather than adding another transparent shell. */
export function buildPlumeSurface(points = [], buffers = createSurfaceBuffers()) {
    const valid = points.slice(0, MAX_PARTICLES).filter(p =>
        [p.x, p.y, p.z, p.radius].every(Number.isFinite) && p.radius > 0);
    const parent = Int32Array.from(valid, (_, i) => i);
    const root = i => {
        while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; }
        return i;
    };
    // At most 1,279,200 cheap contact tests; no unbounded neighbor search.
    for (let i = 0; i < valid.length; i++) {
        for (let j = 0; j < i; j++) {
            const a = valid[i], b = valid[j], radius = a.radius + b.radius;
            if ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2 <= radius * radius) {
                parent[root(i)] = root(j);
            }
        }
    }
    const groups = new Map();
    valid.forEach((point, i) => {
        const key = root(i);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(point);
    });
    const sparse = [], clusters = [];
    for (const group of groups.values()) {
        if (group.length === 1) { sparse.push(group[0]); continue; }
        const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
        let radius = Infinity;
        for (const p of group) {
            radius = Math.min(radius, p.radius);
            [p.x, p.y, p.z].forEach((value, axis) => {
                min[axis] = Math.min(min[axis], value - p.radius * SUPPORT);
                max[axis] = Math.max(max[axis], value + p.radius * SUPPORT);
            });
        }
        clusters.push({ group, min, max, step: radius / 2 });
    }
    const { positions, normals, colors, field } = buffers;
    let count = 0, sampleCount = 0, evaluations = 0;
    const corners = new Int32Array(8), inside = new Int32Array(4), outside = new Int32Array(4);
    const vertices = new Float64Array(4 * 9);
    const plan = (cluster, factor) => {
        const { min, max, step, group } = cluster;
        const size = min.map((value, axis) => Math.max(2, Math.ceil((max[axis] - value) / (step * factor))));
        const spacing = min.map((value, axis) => (max[axis] - value) / size[axis]);
        const samples = (size[0] + 1) * (size[1] + 1) * (size[2] + 1);
        const work = group.reduce((sum, p) => sum + spacing.reduce((product, delta, axis) =>
            product * Math.min(size[axis] + 1, Math.ceil(2 * SUPPORT * p.radius / delta) + 1), 1), 0);
        return { ...cluster, size, spacing, samples, work };
    };
    // Replan before allocating or evaluating any field; coarsening has a fixed iteration cap.
    let factor = 1, plans = [];
    for (let attempt = 0; attempt < 32; attempt++, factor *= 1.5) {
        plans = clusters.map(cluster => plan(cluster, factor));
        if (plans.reduce((sum, p) => sum + p.samples, 0) <= MAX_SURFACE_SAMPLES
            && plans.reduce((sum, p) => sum + p.work, 0) <= MAX_FIELD_EVALUATIONS) break;
    }
    let mergedClusters = 0;
    for (const grid of plans) {
        const { group, min, size: [nx, ny, nz], spacing: [dx, dy, dz], samples, work } = grid;
        // Pathological aspect ratios fall back to physical spheres, never a giant proxy blob.
        if (sampleCount + samples > MAX_SURFACE_SAMPLES || evaluations + work > MAX_FIELD_EVALUATIONS) {
            sparse.push(...group); continue;
        }
        sampleCount += samples;
        field.fill(0, 0, samples * 7);
        const sx = nx + 1, sy = ny + 1, plane = sx * sy;
        for (const p of group) {
            const support = p.radius * SUPPORT, support2 = support * support;
            const starts = [p.x, p.y, p.z].map((value, axis) => Math.max(0, Math.ceil((value - support - min[axis]) / grid.spacing[axis])));
            const ends = [p.x, p.y, p.z].map((value, axis) => Math.min(grid.size[axis], Math.floor((value + support - min[axis]) / grid.spacing[axis])));
            const rgb = p.color || [1, 1, 1];
            for (let z = starts[2]; z <= ends[2]; z++) for (let y = starts[1]; y <= ends[1]; y++) for (let x = starts[0]; x <= ends[0]; x++) {
                evaluations++;
                const vx = min[0] + x * dx - p.x, vy = min[1] + y * dy - p.y, vz = min[2] + z * dz - p.z;
                const q = 1 - (vx * vx + vy * vy + vz * vz) / support2;
                if (q <= 0) continue;
                const weight = q * q * q, gradient = 6 * q * q / support2;
                const offset = (x + y * sx + z * plane) * 7;
                field[offset] += weight;
                field[offset + 1] += vx * gradient; field[offset + 2] += vy * gradient; field[offset + 3] += vz * gradient;
                field[offset + 4] += rgb[0] * weight; field[offset + 5] += rgb[1] * weight; field[offset + 6] += rgb[2] * weight;
            }
        }
        const startCount = count;
        let overflow = false;
        const edge = (a, b, slot) => {
            const ia = corners[a], ib = corners[b], fa = ia * 7, fb = ib * 7;
            const t = (ISO_LEVEL - field[fa]) / (field[fb] - field[fa]);
            const offset = slot * 9;
            const ax = ia % sx, ay = Math.floor(ia / sx) % sy, az = Math.floor(ia / plane);
            const bx = ib % sx, by = Math.floor(ib / sx) % sy, bz = Math.floor(ib / plane);
            vertices[offset] = min[0] + (ax + (bx - ax) * t) * dx;
            vertices[offset + 1] = min[1] + (ay + (by - ay) * t) * dy;
            vertices[offset + 2] = min[2] + (az + (bz - az) * t) * dz;
            let length = 0;
            for (let axis = 0; axis < 3; axis++) {
                const value = field[fa + 1 + axis] * (1 - t) + field[fb + 1 + axis] * t;
                vertices[offset + 3 + axis] = value; length += value * value;
                vertices[offset + 6 + axis] = (field[fa + 4 + axis] * (1 - t) + field[fb + 4 + axis] * t) / ISO_LEVEL;
            }
            length = Math.sqrt(length) || 1;
            for (let axis = 0; axis < 3; axis++) vertices[offset + 3 + axis] /= length;
        };
        const triangle = (a, b, c) => {
            if (count + 3 > MAX_SURFACE_VERTICES) { overflow = true; return; }
            const ia = a * 9, ib = b * 9, ic = c * 9;
            const ux = vertices[ib] - vertices[ia], uy = vertices[ib + 1] - vertices[ia + 1], uz = vertices[ib + 2] - vertices[ia + 2];
            const vx = vertices[ic] - vertices[ia], vy = vertices[ic + 1] - vertices[ia + 1], vz = vertices[ic + 2] - vertices[ia + 2];
            if ((uy * vz - uz * vy) * vertices[ia + 3] + (uz * vx - ux * vz) * vertices[ia + 4]
                + (ux * vy - uy * vx) * vertices[ia + 5] < 0) [b, c] = [c, b];
            for (const slot of [a, b, c]) {
                for (let axis = 0; axis < 3; axis++) {
                    positions[count * 3 + axis] = vertices[slot * 9 + axis];
                    normals[count * 3 + axis] = vertices[slot * 9 + axis + 3];
                    colors[count * 3 + axis] = vertices[slot * 9 + axis + 6];
                }
                count++;
            }
        };
        for (let z = 0; z < nz && !overflow; z++) for (let y = 0; y < ny && !overflow; y++) for (let x = 0; x < nx && !overflow; x++) {
            const base = x + y * sx + z * plane;
            corners.set([base, base + 1, base + sx + 1, base + sx, base + plane, base + plane + 1, base + plane + sx + 1, base + plane + sx]);
            let totalInside = 0;
            for (const corner of corners) if (field[corner * 7] >= ISO_LEVEL) totalInside++;
            if (totalInside === 0 || totalInside === 8) continue;
            for (const tetra of TETRAHEDRA) {
                let ni = 0, no = 0;
                for (const corner of tetra) {
                    if (field[corners[corner] * 7] >= ISO_LEVEL) inside[ni++] = corner;
                    else outside[no++] = corner;
                }
                if (ni === 0 || ni === 4) continue;
                if (ni === 1 || ni === 3) {
                    const one = ni === 1 ? inside : outside, three = ni === 1 ? outside : inside;
                    for (let i = 0; i < 3; i++) edge(one[0], three[i], i);
                    triangle(0, 1, 2);
                } else {
                    edge(inside[0], outside[0], 0); edge(inside[0], outside[1], 1);
                    edge(inside[1], outside[0], 2); edge(inside[1], outside[1], 3);
                    triangle(0, 1, 2); triangle(1, 3, 2);
                }
            }
        }
        if (overflow || count === startCount) {
            // Never upload a truncated/open shell when a component exhausts the mesh budget.
            count = startCount; sparse.push(...group);
        } else mergedClusters++;
    }
    return { ...buffers, vertexCount: count, sparse, mergedClusters, sampleCount, evaluations };
}

const sphereVertex = `
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec3 vColor;
    void main() {
        vec4 local = vec4(position, 1.0);
        vNormal = normal;
        #ifdef USE_INSTANCING
            local = instanceMatrix * local;
            vNormal = normalize(mat3(instanceMatrix) * normal);
            vColor = instanceColor;
        #else
            vColor = color;
        #endif
        vPosition = local.xyz;
        gl_Position = projectionMatrix * modelViewMatrix * local;
    }
`;
const sphereFragment = `
    uniform vec3 eyeLocal;
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec3 vColor;
    void main() {
        vec3 normal = normalize(vNormal);
        vec3 view = normalize(eyeLocal - vPosition);
        float facing = clamp(abs(dot(normal, view)), 0.0, 1.0);
        // Inverse Fresnel fades the silhouette instead of outlining a solid shell.
        float edge = smoothstep(0.0, 0.85, facing);
        // Low-frequency incident-space variation: soft wisps, no screen-space grain,
        // animated boiling, white highlights, or camera-dependent geometry.
        vec3 p = vPosition * 0.045;
        float wisp = 0.5 + 0.25 * sin(p.x + sin(p.z * 0.7))
            + 0.25 * sin(p.y * 0.8 - p.z + sin(p.x * 0.6));
        float alpha = 0.5 * edge * mix(0.82, 1.0, wisp);
        vec3 color = vColor * mix(0.96, 1.0, wisp);
        gl_FragColor = vec4(color, alpha);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
    }
`;
const windVertex = `
    attribute float distanceAlong;
    attribute float flowSpeed;
    attribute float arrow;
    varying float vDistance;
    varying float vSpeed;
    varying float vArrow;
    void main() {
        vDistance = distanceAlong; vSpeed = flowSpeed; vArrow = arrow;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
`;
const windFragment = `
    uniform float time;
    varying float vDistance;
    varying float vSpeed;
    varying float vArrow;
    void main() {
        if (vArrow < 0.5 && mod(vDistance - time * vSpeed, 90.0) > 52.0) discard;
        gl_FragColor = vec4(0.55, 0.88, 1.0, 0.9);
        #include <colorspace_fragment>
    }
`;

/** Mercator-only custom layer. Add after terrain/building layers for shared depth occlusion.
 * update(frame, scenario, context) accepts AGL particle meters and context.buildings.
 * setVisible(boolean) hides only the plume; wind remains visible. Contact groups get
 * smooth compact-support shells, isolated points retain physical-radius spheres.
 * CPU/GPU buffers are reused; only update()/debounced DEM events rebuild geometry.
 * A depth-only prepass selects the nearest shell: 50% maximum opacity, fading rims.
 * visualCutoffFraction defaults to 1% of TRACE and can be overridden in context;
 * zero disables this render-only filter. layer.visualFilter reports its metadata.
 * DEM and roof-following wind is approximate; no camera-dependent particle sizing. */
export function createPlumeLayer({ id = 'hazard-volume', maplibregl,
    visualCutoffFraction = DEFAULT_VISUAL_CUTOFF_FRACTION } = {}) {
    if (!maplibregl?.MercatorCoordinate) throw new Error('createPlumeLayer requires maplibregl.MercatorCoordinate');
    let map, renderer, scene, camera, spheres, surface, depthMaterial, wind, modelMatrix;
    let frame, scenario, context, origin, timer, terrainTimer;
    let active = false, visible = true;
    const surfaceBuffers = createSurfaceBuffers();
    const transform = new THREE.Object3D();
    const color = new THREE.Color();
    const inverse = new THREE.Matrix4();
    const maxWindVertices = WIND_COUNT * (WIND_STEPS * 6 + 6);
    const positions = new Float32Array(maxWindVertices * 3);
    const distances = new Float32Array(maxWindVertices);
    const speeds = new Float32Array(maxWindVertices);
    const arrows = new Float32Array(maxWindVertices);

    const ground = (longitude, latitude) => {
        // MapLibre already includes terrain exaggeration. Never multiply this twice.
        if (!map?.getTerrain?.()) return 0;
        const sampled = map.queryTerrainElevation([longitude, latitude]);
        return Number.isFinite(sampled) ? sampled : 0;
    };
    const upload = () => {
        if (!active || !frame || !origin) return;
        const anchor = maplibregl.MercatorCoordinate.fromLngLat([origin.longitude, origin.latitude], 0);
        const scale = anchor.meterInMercatorCoordinateUnits();
        modelMatrix = new THREE.Matrix4().makeTranslation(anchor.x, anchor.y, 0)
            .multiply(new THREE.Matrix4().makeScale(scale, -scale, scale));
        const thresholds = frame.thresholds || scenario?.hazard || {};
        const { particles, ...visualFilter } = selectVisibleParticles(frame.particles, thresholds,
            context?.visualCutoffFraction ?? visualCutoffFraction);
        layer.visualFilter = visualFilter;
        const points = particles.map(particle => {
            const elevation = ground(particle.longitude, particle.latitude) + Math.max(0, finite(particle.altitudeMeters));
            const position = maplibregl.MercatorCoordinate.fromLngLat([particle.longitude, particle.latitude], elevation);
            color.set(concentrationColor(particle.concentration, thresholds));
            return {
                x: (position.x - anchor.x) / scale, y: -(position.y - anchor.y) / scale, z: position.z / scale,
                radius: Math.max(1, finite(particle.radiusMeters, 12)) * position.meterInMercatorCoordinateUnits() / scale,
                color: [color.r, color.g, color.b],
            };
        });
        const mesh = buildPlumeSurface(points, surfaceBuffers);
        mesh.sparse.forEach((point, i) => {
            transform.position.set(point.x, point.y, point.z);
            transform.scale.setScalar(point.radius);
            transform.updateMatrix();
            spheres.setMatrixAt(i, transform.matrix);
            spheres.setColorAt(i, color.fromArray(point.color));
        });
        surface.geometry.setDrawRange(0, mesh.vertexCount);
        Object.values(surface.geometry.attributes).forEach(attribute => {
            attribute.clearUpdateRanges();
            attribute.addUpdateRange(0, mesh.vertexCount * 3);
            attribute.needsUpdate = true;
        });
        layer.mergedClusterCount = mesh.mergedClusters;
        layer.surfaceVertexCount = mesh.vertexCount;
        spheres.count = mesh.sparse.length;
        spheres.instanceMatrix.needsUpdate = true;
        if (spheres.instanceColor) spheres.instanceColor.needsUpdate = true;
        const lines = buildWindField({ origin, weather: scenario?.weather || context?.weather, windVectors: frame.windVectors,
            buildings: context?.buildings || frame.buildingContamination || [], ground });
        const { toLngLat } = localCoordinates(origin);
        let cursor = 0;
        const vertex = (point, dx, dy, isArrow = 0) => {
            const coordinate = maplibregl.MercatorCoordinate.fromLngLat(toLngLat(point.x + dx, point.y + dy), point.z);
            positions[cursor * 3] = (coordinate.x - anchor.x) / scale;
            positions[cursor * 3 + 1] = -(coordinate.y - anchor.y) / scale;
            positions[cursor * 3 + 2] = coordinate.z / scale;
            distances[cursor] = point.distance; speeds[cursor] = point.speed; arrows[cursor] = isArrow;
            cursor++;
        };
        for (const line of lines) {
            for (let i = 1; i < line.length; i++) {
                const a = line[i - 1], b = line[i];
                const length = Math.hypot(b.x - a.x, b.y - a.y);
                const dx = -(b.y - a.y) / length * 1.35, dy = (b.x - a.x) / length * 1.35;
                vertex(a, dx, dy); vertex(a, -dx, -dy); vertex(b, dx, dy);
                vertex(b, dx, dy); vertex(a, -dx, -dy); vertex(b, -dx, -dy);
                if (i === Math.floor(line.length / 2) || i === line.length - 1) {
                    const ux = (b.x - a.x) / length, uy = (b.y - a.y) / length;
                    vertex(b, ux * 5, uy * 5, 1);
                    vertex(b, -ux * 9 - uy * 6, -uy * 9 + ux * 6, 1);
                    vertex(b, -ux * 9 + uy * 6, -uy * 9 - ux * 6, 1);
                }
            }
        }
        wind.geometry.setDrawRange(0, cursor);
        Object.values(wind.geometry.attributes).forEach(attribute => { attribute.needsUpdate = true; });
        layer.particleCount = particles.length;
        layer.windLineCount = lines.length;
        layer.windSource = frame.windVectors?.length ? 'backend vectors (approximate)' : 'local terrain/building approximation';
        map.triggerRepaint();
    };
    const onTerrainData = event => {
        if (event?.type === 'sourcedata' && event.source?.type !== 'raster-dem' && event.sourceId !== map.getTerrain?.()?.source) return;
        clearTimeout(terrainTimer);
        terrainTimer = setTimeout(upload, 350);
    };
    const animate = () => {
        if (!active) return;
        if (layer.windLineCount) map.triggerRepaint();
        timer = setTimeout(animate, 1000 / 30);
    };
    const layer = {
        id, type: 'custom', renderingMode: '3d', particleCount: 0, windLineCount: 0,
        mergedClusterCount: 0, surfaceVertexCount: 0, visualFilter: null,
        windSource: 'local terrain/building approximation',
        setVisible(nextVisible) {
            visible = Boolean(nextVisible);
            if (spheres) spheres.visible = visible;
            if (surface) surface.visible = visible;
            map?.triggerRepaint();
        },
        update(nextFrame, nextScenario, nextContext) {
            frame = nextFrame; scenario = nextScenario; context = nextContext;
            const location = frame?.sourceLocation || scenario?.sourceLocation || scenario?.location || frame?.particles?.[0];
            origin = location && Number.isFinite(location.longitude) && Number.isFinite(location.latitude) ? location : null;
            if (!frame || !origin) {
                if (spheres) spheres.count = 0;
                if (surface) surface.geometry.setDrawRange(0, 0);
                if (wind) wind.geometry.setDrawRange(0, 0);
                layer.particleCount = 0; layer.windLineCount = 0;
                layer.mergedClusterCount = 0; layer.surfaceVertexCount = 0; layer.visualFilter = null;
                map?.triggerRepaint();
                return;
            }
            upload();
        },
        onAdd(nextMap, gl) {
            map = nextMap; active = true;
            scene = new THREE.Scene(); camera = new THREE.Camera();
            renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true });
            renderer.autoClear = false;
            const material = new THREE.ShaderMaterial({ vertexShader: sphereVertex, fragmentShader: sphereFragment,
                uniforms: { eyeLocal: { value: new THREE.Vector3() } }, depthTest: true, depthWrite: false,
                transparent: true, vertexColors: true, blending: THREE.NormalBlending });
            // Nearest-surface depth prepass makes overlap remain 50%, not near-opaque.
            depthMaterial = new THREE.ShaderMaterial({ vertexShader: sphereVertex,
                fragmentShader: 'void main() { gl_FragColor = vec4(0.0); }', vertexColors: true,
                colorWrite: false, depthWrite: true, depthTest: true });
            const surfaceGeometry = new THREE.BufferGeometry();
            for (const [name, array] of [['position', surfaceBuffers.positions], ['normal', surfaceBuffers.normals], ['color', surfaceBuffers.colors]]) {
                surfaceGeometry.setAttribute(name, new THREE.BufferAttribute(array, 3).setUsage(THREE.DynamicDrawUsage));
            }
            surfaceGeometry.setDrawRange(0, 0);
            surface = new THREE.Mesh(surfaceGeometry, material);
            surface.visible = visible; surface.frustumCulled = false; scene.add(surface);
            spheres = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 20, 14), material, MAX_PARTICLES);
            spheres.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            // Allocate instanceColor even when the initial frame is empty.
            spheres.setColorAt(0, color.set('#1767ff'));
            spheres.instanceColor.setUsage(THREE.DynamicDrawUsage);
            spheres.count = 0; spheres.visible = visible; spheres.frustumCulled = false; scene.add(spheres);
            const geometry = new THREE.BufferGeometry();
            for (const [name, array, size] of [['position', positions, 3], ['distanceAlong', distances, 1], ['flowSpeed', speeds, 1], ['arrow', arrows, 1]]) {
                geometry.setAttribute(name, new THREE.BufferAttribute(array, size).setUsage(THREE.DynamicDrawUsage));
            }
            geometry.setDrawRange(0, 0);
            wind = new THREE.Mesh(geometry, new THREE.ShaderMaterial({ vertexShader: windVertex, fragmentShader: windFragment,
                uniforms: { time: { value: 0 } }, side: THREE.DoubleSide, depthTest: true, depthWrite: false, transparent: true }));
            wind.frustumCulled = false; scene.add(wind);
            map.on('sourcedata', onTerrainData); map.on('terrain', onTerrainData);
            upload(); animate();
        },
        render(gl, input) {
            const matrix = renderMatrix(input);
            if (!active || !modelMatrix || !matrix) return;
            camera.projectionMatrix.fromArray(matrix).multiply(modelMatrix);
            camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
            inverse.copy(camera.projectionMatrixInverse);
            spheres.material.uniforms.eyeLocal.value.set(0, 0, -1).applyMatrix4(inverse);
            wind.material.uniforms.time.value = Math.floor(performance.now() / (1000 / 30)) / 30;
            // Three resets framebuffer/viewport/depth range; retain MapLibre's actual target,
            // including its depth attachment, rather than accidentally rendering an overlay.
            const framebuffer = gl.getParameter(gl.FRAMEBUFFER_BINDING);
            const viewport = gl.getParameter(gl.VIEWPORT);
            const depthRange = gl.getParameter(gl.DEPTH_RANGE);
            renderer.resetState();
            gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
            gl.viewport(...viewport);
            gl.depthRange(...depthRange);
            if (visible) {
                wind.visible = false;
                scene.overrideMaterial = depthMaterial;
                renderer.render(scene, camera);
                scene.overrideMaterial = null;
                wind.visible = true;
            }
            renderer.render(scene, camera);
            renderer.resetState();
            gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
            gl.viewport(...viewport);
            gl.depthRange(...depthRange);
        },
        onRemove() {
            active = false; clearTimeout(timer); clearTimeout(terrainTimer);
            map?.off('sourcedata', onTerrainData); map?.off('terrain', onTerrainData);
            spheres?.geometry.dispose(); spheres?.material.dispose(); spheres?.dispose();
            surface?.geometry.dispose(); depthMaterial?.dispose();
            wind?.geometry.dispose(); wind?.material.dispose();
            renderer?.dispose();
            // Never forceContextLoss(): the WebGL context belongs to MapLibre.
            scene?.clear(); renderer = null; map = null;
        },
    };
    return layer;
}
