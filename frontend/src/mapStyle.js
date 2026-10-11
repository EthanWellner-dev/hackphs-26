export const BUILDING_MIN_ZOOM = 12

export function prepareMapStyle(style) {
    const result = structuredClone(style);
    for (const layer of result.layers || []) {
        if (layer['source-layer'] === 'building' || /building/i.test(layer.id)) {
            layer.minzoom = BUILDING_MIN_ZOOM;
            if (layer.type === 'fill-extrusion') {
                layer.layout = { ...layer.layout, visibility: 'visible' };
                layer.paint = { ...layer.paint,
                    'fill-extrusion-height': ['max', 5, ['to-number', ['get', 'render_height'], ['get', 'height'], 8]],
                    'fill-extrusion-base': ['max', 0, ['to-number', ['get', 'render_min_height'], 0]],
                    'fill-extrusion-opacity': 0.9,
                };
            }
        }
    }
    return result;
}
