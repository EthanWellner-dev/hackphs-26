export const BUILDING_MIN_ZOOM = 16

export function prepareMapStyle(style) {
    const result = structuredClone(style);
    for (const layer of result.layers || []) {
        if (layer['source-layer'] === 'building' || /building/i.test(layer.id)) {
            layer.minzoom = Math.max(BUILDING_MIN_ZOOM, layer.minzoom || 0);
        }
    }
    return result;
}
