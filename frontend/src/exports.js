export function csvCell(value) {
    let text = value == null ? '' : String(value);
    if (typeof value === 'string' && /^[\s]*[=+\-@]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
}

export function exposureCsv(data) {
    const header = ['property_id', 'name', 'longitude', 'latitude', 'start_min', 'end_min', 'outdoor_exposure', 'exposure_unit', 'mean_concentration', 'peak_concentration', 'concentration_unit', 'interpretation'];
    const rows = (data.buildings || []).map(item => [item.footprintId ?? item.id, item.displayName, item.longitude, item.latitude, data.startMinutes ?? 0, data.endMinutes ?? 120, item.timeIntegratedConcentration, data.exposureUnit, item.meanConcentration, item.peakConcentration, data.concentrationUnit, 'Modeled outdoor concentration-time integral; not absorbed dose; occupancy/indoor/PPE not modeled']);
    return '\uFEFF' + [header, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n');
}

export function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
}

export function recordMapVideo(map, caption) {
    if (!globalThis.MediaRecorder || !map.getCanvas().captureStream) throw new Error('Video recording is unavailable in this browser');
    const canvas = document.createElement('canvas');
    canvas.width = map.getCanvas().width;
    canvas.height = map.getCanvas().height + 90;
    const ctx = canvas.getContext('2d');
    const draw = () => {
        ctx.fillStyle = '#101a22'; ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(map.getCanvas(), 0, 0);
        ctx.fillStyle = '#eaf4f7'; ctx.font = '16px sans-serif';
        ctx.fillText(caption(), 14, canvas.height - 62, canvas.width - 28);
        ctx.fillText('Simulation only / not emergency guidance. Forecast playback, not real time.', 14, canvas.height - 38, canvas.width - 28);
        ctx.fillText('OpenFreeMap / OpenMapTiles / © OpenStreetMap contributors; AWS terrain', 14, canvas.height - 14, canvas.width - 28);
    };
    map.on('render', draw);
    const stream = canvas.captureStream(30);
    const mimeType = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) { map.off('render', draw); stream.getTracks().forEach(track => track.stop()); throw new Error('WebM recording is unavailable'); }
    const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6000000 });
    const chunks = [];
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    recorder.start(1000);
    return () => new Promise((resolve, reject) => {
        recorder.onstop = () => {
            map.off('render', draw);
            stream.getTracks().forEach(track => track.stop());
            const blob = new Blob(chunks, { type: mimeType });
            if (blob.size) { downloadBlob(blob, 'aero-hazard-forecast.webm'); resolve(); }
            else reject(new Error('Empty recording'));
        };
        recorder.stop();
    });
}

export async function downloadMapImage(map, format, lines) {
    const source = await new Promise((resolve, reject) => {
        const capture = () => {
            clearTimeout(timeout);
            try {
                const copy = document.createElement('canvas');
                copy.width = map.getCanvas().width;
                copy.height = map.getCanvas().height;
                copy.getContext('2d').drawImage(map.getCanvas(), 0, 0);
                resolve(copy);
            } catch (error) { reject(error); }
        };
        const timeout = setTimeout(() => { map.off('render', capture); reject(new Error('Map render timed out')); }, 10000);
        map.once('render', capture);
        map.triggerRepaint();
    });
    const footer = 130;
    const canvas = document.createElement('canvas');
    canvas.width = source.width;
    canvas.height = source.height + footer;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#101a22';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(source, 0, 0);
    ctx.font = '14px sans-serif';
    ctx.fillStyle = '#ecf4f7';
    [...lines, 'Map: OpenFreeMap / OpenMapTiles / © OpenStreetMap contributors; terrain: AWS Open Data', 'SIMULATION ONLY - outdoor exposure, not absorbed dose or emergency guidance.'].forEach((line, index) => ctx.fillText(line, 16, source.height + 24 + index * 22, canvas.width - 32));
    const mime = format === 'jpg' ? 'image/jpeg' : 'image/png';
    const blob = await new Promise(resolve => canvas.toBlob(resolve, mime, 0.93));
    if (!blob) throw new Error('Map image capture unavailable');
    downloadBlob(blob, 'aero-hazard-exposure.' + format);
}
