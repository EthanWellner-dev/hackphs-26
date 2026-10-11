import { describe, expect, it } from 'vitest';
// @ts-ignore shared JavaScript helper
import { csvCell, exposureCsv } from './exports.js';

describe('exposure CSV', () => {
    it('escapes separators, quotes and spreadsheet formulas', () => {
        expect(csvCell('House, "A"')).toBe('"House, ""A"""');
        expect(csvCell('=cmd()')).toBe('"\'=cmd()"');
        expect(csvCell(-74)).toBe('"-74"');
    });
    it('exports every property with explicit units and limitations', () => {
        const buildings = Array.from({ length: 12 }, (_, i) => ({ footprintId: i, displayName: `House ${i}`, longitude: -74, latitude: 40, timeIntegratedConcentration: 12, meanConcentration: 0.1, peakConcentration: 1 }));
        const csv = exposureCsv({ buildings, exposureUnit: 'ppm·min', concentrationUnit: 'ppm' });
        expect(csv.split('\r\n')).toHaveLength(13);
        expect(csv).toContain('House 11');
        expect(csv).toContain('ppm·min');
        expect(csv).toContain('not absorbed dose');
    });
});
