const pending = new Map();
const memory = new Map();

export async function cachedJson(url, ttlMs, { fetcher = fetch, storage = globalThis.localStorage, now = Date.now } = {}) {
    let cached = memory.get(url);
    try { cached ||= JSON.parse(storage?.getItem('aero:' + url) || 'null'); } catch { /* Storage may be unavailable. */ }
    if (cached && now() - cached.savedAt < ttlMs) return cached.data;
    if (pending.has(url)) return pending.get(url);
    const request = (async () => {
        try {
            const response = await fetcher(url, { signal: AbortSignal.timeout(8000) });
            if (!response.ok) throw new Error(`Request failed (${response.status})`);
            const data = await response.json();
            const entry = { data, savedAt: now() };
            memory.set(url, entry);
            if (memory.size > 64) memory.delete(memory.keys().next().value);
            try { storage?.setItem('aero:' + url, JSON.stringify(entry)); } catch { /* Cache is optional. */ }
            return data;
        } finally { pending.delete(url); }
    })();
    pending.set(url, request);
    return request;
}

export const loadMapStyle = () => cachedJson('https://tiles.openfreemap.org/styles/liberty', 24 * 60 * 60 * 1000);

let searchQueue = Promise.resolve();
let lastSearch = 0;
export function searchPlaces(query) {
    const url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&q=' + encodeURIComponent(query.trim());
    return cachedJson(url, 24 * 60 * 60 * 1000, { fetcher: (...args) => {
        const request = searchQueue.then(async () => {
            const delay = Math.max(0, 1100 - (Date.now() - lastSearch));
            if (delay) await new Promise(resolve => setTimeout(resolve, delay));
            lastSearch = Date.now();
            return fetch(...args);
        });
        searchQueue = request.catch(() => {});
        return request;
    } });
}

export function deploymentLocation(text) {
    if (!/\b(?:team|engine|ambulance|hazmat|fire|responding|deploy|send)\b/i.test(text)) return null;
    const match = /\b(?:at|on|to)\s+([^;]+)(?=;|$)/i.exec(text);
    if (!match) return null;
    const query = match[1].trim();
    if (/^(?:the\s+)?source[.!]?$/i.test(query) || /^[+-]?\d+(?:\.\d+)?\s*,\s*[+-]?\d+(?:\.\d+)?[.!]?$/.test(query)
        || /^(?:\d+(?:\.\d+)?\s*(?:m|km|meters?)\s+)?(?:north|south|east|west)(?:\s+of\s+(?:the\s+)?source)?[.!]?$/i.test(query)) return null;
    return { query, start: match.index + match[0].indexOf(match[1]), end: match.index + match[0].length };
}
