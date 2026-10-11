import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

maplibregl.setWorkerUrl(new URL('../node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs', import.meta.url).href);
import { createPlumeLayer } from './plumeLayer.js';
import { ForecastPlayback } from './playback.js';
import { exposureCsv, downloadBlob, downloadMapImage, recordMapVideo } from './exports.js';
import { TimelineFrames, timelineMinute, formatConcentration, releaseMass, mergeWeatherTimeline } from './timeline.js';

        let map;
        let currentMarker = null;
        let sourceMarker = null;
        let scenario = null;
        let contextSnapshot = null;
        let plumeFrame = null;
        let plumeIsFallback = false;
        let selectedTimeMinutes = 30;
        let timelineTimer = null;
        let weatherRefreshTimer = null;
        let weatherRequest = null;
        let weatherFailed = false;
        let plumeLayer = null;
        let incidentStartedAt = Date.now();
        const API_BASE = window.__AERO_API_BASE__ || '';
        const WEATHER_REFRESH_MS = 5 * 60 * 1000;
        const TIMELINE_DEBOUNCE_MS = 90;
        const frames = new TimelineFrames(async (minute, signal) => {
            const response = await fetch(API_BASE + '/api/plume?timeMinutes=' + minute, {
                method: 'POST', signal, headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({ scenario, context: contextSnapshot })
            });
            if (!response.ok) throw new Error('timeline ' + response.status);
            return response.json();
        });

        let videoBusy = false;
        let unitMarkers = new Map();
        let voiceRecognition = null;
        let hazardLibrary = {};
        let playbackStarted = false;
        let exposureMode = false;
        let exposureData = null;
        let exposureRequest = null;
        let exposurePopup = null;
        const playback = new ForecastPlayback({
            load: minute => frames.get(minute),
            render: frame => renderPlume(frame),
            status: (state, minute) => {
                const button = document.getElementById('forecast-play');
                if (!button) return;
                button.textContent = playback.playing ? '❚❚ PAUSE' : '▶ PLAY 2 HOURS';
                button.setAttribute('aria-pressed', String(playback.playing));
                document.getElementById('forecast-status').textContent = state === 'loading' ? `Buffering T+${minute}…` : state === 'error' ? 'Forecast unavailable. Retry play.' : '5-minute steps · stops at T+120';
            }
        });

        function invalidateForecasts() {
            playback.stop();
            clearTimeout(timelineTimer);
            frames.invalidate();
            playbackStarted = false;
            exposureRequest?.abort();
            exposureRequest = null;
            exposureData = null;
            exposurePopup?.remove();
            for (const id of ['exposure-areas', 'exposure-buildings']) map?.getSource(id)?.setData({ type: 'FeatureCollection', features: [] });
            if (exposureMode) setTimeout(loadExposure, 0);
        }

        // Global DEM Terrain Source Configuration (Terrarium Encoding)
        const PRINCETON_MIDDLE_SCHOOL = [-74.6542123, 40.360556];


        const TERRAIN_DISABLE_ZOOM = 17;
        const terrainSourceConfig = {
            type: 'raster-dem',
            tiles: [
                'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
            ],
            encoding: 'terrarium',
            tileSize: 256,
            maxzoom: TERRAIN_DISABLE_ZOOM
        };

        async function initMap() {
            try {
                // Fetch Liberty Style from OpenFreeMap
                const res = await fetch('https://tiles.openfreemap.org/styles/liberty');
                const styleJson = await res.json();

                // Inject DEM terrain. No satellite provider is configured in this deployment.
                if (!styleJson.sources) styleJson.sources = {};
                styleJson.sources['terrain-source'] = terrainSourceConfig;
                // Keep DEM enabled in the initial command-center view so every plume
                // volume and terrain vector is grounded in the same 3D surface.
                styleJson.terrain = { source: 'terrain-source', exaggeration: 2.4 };

                map = new maplibregl.Map({
                    container: 'map',
                    style: styleJson,
                    center: PRINCETON_MIDDLE_SCHOOL,
                    zoom: 13.5,
                    pitch: 68,
                    bearing: -20,
                    attributionControl: true,
                    maxTileCacheSize: 128,
                    fadeDuration: 0,
                    refreshExpiredTiles: false,
                    transformRequest: (url) => ({ url })
                });

                // Stop requesting DEM data once the view is zoomed in past the useful terrain scale.
                map.on('zoom', () => {
                    const terrainEnabled = map.getZoom() <= TERRAIN_DISABLE_ZOOM;
                    if (terrainEnabled && !map.getTerrain()) map.setTerrain({ source: 'terrain-source', exaggeration: 1.8 });
                });

                map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

                map.once('style.load', () => {
                    addSourcePin();
                    addAffectedPropertyLayer();
                    addExposureLayers();
                    plumeLayer = createPlumeLayer({ maplibregl });
                    map.addLayer(plumeLayer);
                    map.on('rotate', updateWindBadge);
                    showToast("Princeton Middle School map ready. Terrain and 3D chlorine plume loaded.");
                    loadBackendData();
                });

                setupSearchEngine();
                setupEventListeners();
            } catch (err) {
                console.error("Error initializing MapLibre map:", err);
                showToast("Error loading map engine.");
            }
        }

        function addSourcePin() {
            if (!map || sourceMarker) return;
            const el = document.createElement('div');
            el.className = 'source-marker';
            el.textContent = '⚠';
            sourceMarker = new maplibregl.Marker({ element: el })
                .setLngLat(PRINCETON_MIDDLE_SCHOOL)
                .setPopup(new maplibregl.Popup({ offset: 20 }).setHTML('<strong style="color:#111">Incident source</strong><br><span style="color:#333">Princeton Middle School · chlorine release</span>'))
                .addTo(map);
        }

        function updateWindBadge() {
            const arrow = document.getElementById('wind-arrow');
            if (arrow && scenario?.weather) arrow.style.transform = 'rotate(' + ((Number(scenario.weather.windDirectionFromDegrees) + 180 - (map?.getBearing() || 0) + 360) % 360) + 'deg)';
        }

        function addAffectedPropertyLayer() {
            if (!map || map.getSource('affected-properties')) return;
            map.addSource('affected-properties', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            map.addLayer({ id: 'affected-properties-fill', type: 'fill-extrusion', source: 'affected-properties', paint: { 'fill-extrusion-color': ['get', 'color'], 'fill-extrusion-height': 8, 'fill-extrusion-opacity': 0.45 } });
        }

        function addExposureLayers() {
            for (const id of ['exposure-areas', 'exposure-buildings']) {
                map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            }
            map.addLayer({ id: 'exposure-area-fill', type: 'fill', source: 'exposure-areas', layout: { visibility: 'none' }, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.38 } });
            map.addLayer({ id: 'exposure-building-fill', type: 'fill-extrusion', source: 'exposure-buildings', layout: { visibility: 'none' }, paint: { 'fill-extrusion-color': ['get', 'color'], 'fill-extrusion-height': 10, 'fill-extrusion-opacity': 0.85 } });
            map.on('click', event => {
                if (!exposureMode || !exposureData) return;
                const hits = map.queryRenderedFeatures(event.point, { layers: ['exposure-building-fill', 'exposure-area-fill'] });
                const feature = hits.find(item => item.layer.id === 'exposure-building-fill') || hits[0];
                if (!feature) return;
                const info = feature.properties;
                const content = document.createElement('div');
                content.className = 'exposure-popup';
                const title = document.createElement('strong');
                title.textContent = info.displayName || 'Area sample';
                content.append(title);
                for (const text of [
                    `T+0–120 outdoor exposure: ${formatConcentration(info.timeIntegratedConcentration, exposureData.exposureUnit)}`,
                    `Mean: ${formatConcentration(info.meanConcentration, exposureData.concentrationUnit)}`,
                    `Peak: ${formatConcentration(info.peakConcentration, exposureData.concentrationUnit)}`
                ]) { const line = document.createElement('div'); line.textContent = text; content.append(line); }
                const warning = document.createElement('small');
                warning.textContent = 'Not personal dose. Indoor shelter, occupancy and PPE are not modeled. Color describes mean concentration, not a safe-dose limit.';
                content.append(warning);
                exposurePopup?.remove();
                exposurePopup = new maplibregl.Popup().setLngLat(event.lngLat).setDOMContent(content).addTo(map);
            });
        }

        function setExposureMode(enabled) {
            exposureMode = enabled;
            if (enabled) playback.stop();
            document.getElementById('view-plume').setAttribute('aria-pressed', String(!enabled));
            document.getElementById('view-exposure').setAttribute('aria-pressed', String(enabled));
            document.getElementById('exposure-summary').hidden = !enabled;
            document.getElementById('export-controls').hidden = !enabled;
            plumeLayer?.setVisible?.(!enabled);
            for (const id of ['exposure-area-fill', 'exposure-building-fill']) if (map?.getLayer(id)) map.setLayoutProperty(id, 'visibility', enabled ? 'visible' : 'none');
            if (map?.getLayer('affected-properties-fill')) map.setLayoutProperty('affected-properties-fill', 'visibility', enabled ? 'none' : 'visible');
            exposurePopup?.remove();
            if (enabled) loadExposure();
            else updateAffectedProperties(plumeFrame);
        }

        function renderExposure(data) {
            const collection = items => ({ type: 'FeatureCollection', features: items.filter(item => item.polygon?.length >= 3).map(item => {
                const ring = [...item.polygon];
                if (String(ring[0]) !== String(ring[ring.length - 1])) ring.push(ring[0]);
                return { type: 'Feature', properties: { displayName: item.displayName, color: item.color, peakConcentration: item.peakConcentration, meanConcentration: item.meanConcentration, timeIntegratedConcentration: item.timeIntegratedConcentration }, geometry: { type: 'Polygon', coordinates: [ring] } };
            }) });
            map.getSource('exposure-areas').setData(collection(data.areas || []));
            map.getSource('exposure-buildings').setData(collection(data.buildings || []));
            document.getElementById('exposure-summary').textContent = `T+0–120 · ${data.exposureUnit} outdoor exposure. Colors: blue → yellow → red by mean concentration. Click a building or area. Grid ${data.gridResolutionMeters} m; ${data.domainTruncated ? 'bounded / truncated coverage' : 'sampled coverage'}. Not personal dose.`;
            const list = document.getElementById('affected-list');
            list.replaceChildren();
            const ranked = [...(data.buildings || [])].sort((a, b) => b.timeIntegratedConcentration - a.timeIntegratedConcentration).slice(0, 8);
            if (!ranked.length) list.textContent = 'No building footprints available. Click the sampled area layer instead.';
            for (const item of ranked) {
                const row = document.createElement('span');
                row.textContent = `${item.displayName}: ${formatConcentration(item.timeIntegratedConcentration, data.exposureUnit)}`;
                row.style.borderLeft = `3px solid ${item.color}`;
                row.style.paddingLeft = '6px';
                list.append(row);
            }
        }

        async function loadExposure() {
            if (!scenario || !exposureMode) return;
            if (exposureData) return renderExposure(exposureData);
            if (exposureRequest) return;
            const revision = frames.revision;
            const controller = new AbortController();
            exposureRequest = controller;
            document.getElementById('exposure-summary').textContent = 'Integrating 25 forecast steps…';
            const timeout = setTimeout(() => controller.abort(), 60000);
            try {
                const response = await fetch(API_BASE + '/api/exposure', { method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario, context: contextSnapshot }) });
                if (!response.ok) throw new Error('exposure ' + response.status);
                const data = await response.json();
                if (revision !== frames.revision) return;
                exposureData = data;
                if (exposureMode) renderExposure(data);
            } catch (error) {
                if (revision === frames.revision && exposureMode) document.getElementById('exposure-summary').textContent = 'Exposure forecast unavailable. Click 2H EXPOSURE to retry; no dose is inferred.';
            } finally {
                clearTimeout(timeout);
                if (exposureRequest === controller) exposureRequest = null;
            }
        }

        function renderPlume(frame, fallback = false) {
            plumeFrame = frame;
            plumeIsFallback = fallback;
            if (Number.isFinite(Number(frame.timeMinutes))) selectedTimeMinutes = Number(frame.timeMinutes);
            frames.seed(frame);
            updateTimelineUi();
            updateMetrics(frame);
            updateUnitMarkers();
            if (!exposureMode) updateAffectedProperties(frame);
            plumeLayer?.update(frame, scenario, contextSnapshot);
            plumeLayer?.setVisible?.(!exposureMode);
            const mode = document.getElementById('plume-mode');
            if (mode) mode.textContent = fallback ? 'Simulation unavailable' : '3D simulated plume / approximate terrain flow';
        }

        async function loadBackendData() {
            try {
                const response = await fetch(API_BASE + '/api/bootstrap?latitude=40.360556&longitude=-74.6542123', { headers: { Accept: 'application/json' } });
                if (!response.ok) throw new Error('bootstrap ' + response.status);
                const data = await response.json();
                scenario = data.scenario;
                contextSnapshot = data.context;
                incidentStartedAt = Date.parse(scenario.incidentStartedAt) || Date.now();
                invalidateForecasts();
                renderPlume(data.frame);
                updateWeatherUi();
                syncReleaseControls();
                loadHazardOptions();
                startWeatherRefresh();
            } catch (error) {
                console.warn('Backend unavailable', error);
                renderPlume({ particles: [], timeMinutes: selectedTimeMinutes }, true);
                document.getElementById('weather-context').textContent = 'Weather unavailable · retrying';
                document.getElementById('wind-summary').textContent = 'Unavailable';
                showToast('Backend unavailable. No invented plume or exposure readings are shown.');
                setTimeout(loadBackendData, 30000);
            }
        }

        async function loadHazardOptions() {
            try {
                const response = await fetch(API_BASE + '/api/hazards');
                if (!response.ok) return;
                hazardLibrary = await response.json();
                const select = document.getElementById('release-hazard');
                for (const [key, hazard] of Object.entries(hazardLibrary)) {
                    const option = document.createElement('option');
                    option.value = key;
                    option.textContent = `${hazard.name}${hazard.molecularWeightGPerMol ? ` (${hazard.molecularWeightGPerMol} g/mol)` : ''}`;
                    select.append(option);
                }
            } catch { /* Current hazard remains usable offline. */ }
        }

        function syncReleaseControls() {
            if (!scenario?.release) return;
            const release = scenario.release;
            document.getElementById('release-mode').value = release.mode;
            document.getElementById('release-rate').value = release.rateKgPerSecond;
            document.getElementById('release-duration').value = release.durationMinutes;
            document.getElementById('release-impulse').value = release.impulseMassKg || 10;
            document.getElementById('release-time').value = release.impulseTimeMinutes;
        }

        async function applyRelease(event) {
            event.preventDefault();
            if (!scenario) return;
            const next = structuredClone(scenario);
            const mode = document.getElementById('release-mode').value;
            next.release = { ...next.release, mode, rateKgPerSecond: Number(document.getElementById('release-rate').value), durationMinutes: Number(document.getElementById('release-duration').value), impulseMassKg: mode === 'CONTINUOUS' ? 0 : Number(document.getElementById('release-impulse').value), impulseTimeMinutes: Number(document.getElementById('release-time').value), hasExploded: mode !== 'CONTINUOUS' };
            const hazard = hazardLibrary[document.getElementById('release-hazard').value];
            if (hazard) { next.hazard = hazard; next.gases = []; }
            const feedback = document.getElementById('release-feedback');
            if (mode !== 'CONTINUOUS' && next.release.impulseMassKg <= 0) { feedback.textContent = 'Burst mass must be greater than zero.'; return; }
            feedback.textContent = 'Applying…';
            const revision = frames.revision;
            try {
                const response = await fetch(API_BASE + '/api/scenario', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario: next }) });
                if (!response.ok) throw new Error('Scenario validation failed');
                const updated = await response.json();
                if (revision !== frames.revision) { feedback.textContent = 'Scenario changed. Apply again to use the latest weather.'; return; }
                scenario = updated;
                invalidateForecasts();
                requestTimelineFrame(selectedTimeMinutes, true);
                feedback.textContent = `Applied ${mode.replaceAll('_', ' ').toLowerCase()} / ${releaseMass(scenario.release).toLocaleString()} kg total.`;
            } catch (error) { feedback.textContent = error.message; }
        }

        async function exportForecastVideo() {
            if (!scenario || videoBusy) return;
            videoBusy = true;
            playback.stop();
            clearTimeout(timelineTimer);
            const button = document.getElementById('forecast-video');
            button.disabled = true;
            const revision = frames.revision;
            let stopRecording;
            try {
                // Preload unchanged, full-quality frames so network latency does not enter the video.
                for (let minute = 0; minute <= 120; minute += 5) {
                    button.textContent = `PREP ${Math.round(minute / 1.2)}%`;
                    await frames.get(minute);
                    if (revision !== frames.revision) throw new Error('Scenario changed; retry recording');
                }
                setExposureMode(false);
                button.textContent = 'RECORDING';
                stopRecording = recordMapVideo(map, () => `${scenario.hazard.name} / T+${selectedTimeMinutes} min / ${releaseMass(scenario.release).toFixed(2)} kg`);
                await playback.play(0);
                await new Promise(resolve => { map.once('render', resolve); map.triggerRepaint(); });
                await stopRecording();
                stopRecording = null;
                showToast('Forecast video downloaded as WebM.');
            } catch (error) { showToast(error.message || 'Video export failed'); }
            finally {
                if (stopRecording) await stopRecording().catch(() => {});
                videoBusy = false; button.disabled = false; button.textContent = 'VIDEO ↓';
            }
        }

        function startVoiceDispatch() {
            const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const input = document.getElementById('dispatch-input');
            input.classList.remove('hidden');
            document.getElementById('dispatch-examples').hidden = false;
            document.getElementById('dispatch-chat-toggle').setAttribute('aria-expanded', 'true');
            if (!Recognition) { input.focus(); return showToast('Voice recognition is unavailable here. Type your dispatch message instead.'); }
            if (voiceRecognition) { voiceRecognition.stop(); return; }
            const recognition = new Recognition();
            voiceRecognition = recognition;
            recognition.lang = 'en-US'; recognition.interimResults = false;
            recognition.onresult = event => { input.value = event.results[0][0].transcript; input.focus(); showToast('Transcript ready. Review and press Enter to dispatch.'); };
            recognition.onerror = event => showToast(`Voice unavailable (${event.error}). You can type instead.`);
            recognition.onend = () => { voiceRecognition = null; document.getElementById('ai-dispatch-orb').setAttribute('aria-pressed', 'false'); };
            document.getElementById('ai-dispatch-orb').setAttribute('aria-pressed', 'true');
            try { recognition.start(); showToast('Listening. Browser microphone permission may be required.'); }
            catch { voiceRecognition = null; showToast('Microphone unavailable; use text dispatch.'); }
        }

        function updateUnitMarkers() {
            if (!map) return;
            const units = scenario?.activeUnits || [];
            const active = new Set(units.map(unit => unit.unitId));
            for (const [id, marker] of unitMarkers) if (!active.has(id)) { marker.remove(); unitMarkers.delete(id); }
            for (const unit of units) {
                let marker = unitMarkers.get(unit.unitId);
                if (!marker) {
                    const element = document.createElement('div');
                    element.className = 'responding-unit';
                    marker = new maplibregl.Marker({ element }).setLngLat([unit.longitude, unit.latitude]).addTo(map);
                    unitMarkers.set(unit.unitId, marker);
                }
                marker.getElement().textContent = unit.label || unit.unitId;
                marker.getElement().title = `${unit.status || 'DEPLOYED'} / simulated responder position`;
                marker.setLngLat([unit.longitude, unit.latitude]);
                const details = document.createElement('div');
                details.className = 'exposure-popup';
                for (const text of [unit.label || unit.unitId, `${unit.status || 'DEPLOYED'} / ${unit.teamType || 'Response team'}`, unit.task || 'Awaiting assignment', `Equipment: ${Array.isArray(unit.equipment) ? unit.equipment.join(', ') : unit.equipment || 'Not specified'}`, `Assigned properties: ${(unit.assignedPropertyIds || []).join(', ') || 'None'}`, 'Simulated placement, not live vehicle tracking']) {
                    const line = document.createElement('div'); line.textContent = text; details.append(line);
                }
                marker.setPopup(new maplibregl.Popup({ offset: 16 }).setDOMContent(details));
            }
        }

        async function exportExposure(format) {
            if (!exposureData) return showToast('Open 2H EXPOSURE and wait for the forecast before exporting.');
            try {
                if (format === 'csv') downloadBlob(new Blob([exposureCsv(exposureData)], { type: 'text/csv;charset=utf-8' }), 'affected-properties-2h.csv');
                else await downloadMapImage(map, format, [
                    `${scenario.hazard.name} / ${releaseMass(scenario.release).toLocaleString()} kg / T+0-120 modeled exposure`,
                    `${exposureData.exposureUnit}; colors represent mean concentration (blue / yellow / red), NOT safe-dose bands`,
                    `Weather ${scenario.weather.source}; grid ${exposureData.gridResolutionMeters} m; bounded sampled coverage`
                ]);
                showToast('Export ready.');
            } catch { showToast('Image export unavailable: map tiles may still be loading or blocked. Retry after the map loads.'); }
        }

        function updateWeatherUi() {
            if (!scenario?.weather) return;
            const weather = scenario.weather;
            const speed = Number(weather.windSpeedMetersPerSecond) * 3.6;
            const from = ((Number(weather.windDirectionFromDegrees) % 360) + 360) % 360;
            const compass = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][Math.round(from / 22.5) % 16];
            const source = weatherFailed ? 'STALE / refresh failed' : contextSnapshot?.weather?.stale ? 'STALE / CACHED' : weather.source || 'UNAVAILABLE';
            const summary = compass + ' ' + speed.toFixed(1) + ' km/h';
            document.getElementById('wind-summary').textContent = summary + ' / ' + source;
            document.getElementById('wind-label').textContent = summary + ' / ' + source;
            const selectedAt = contextSnapshot?.weather?.selectedAt || weather.selectedAt;
            document.getElementById('weather-context').textContent = source + ' wind from ' + summary + ' / ' + Number(weather.temperatureCelsius).toFixed(1) + ' C' + (selectedAt ? ' / valid ' + selectedAt + ' UTC' : '');
            document.getElementById('weather-detail').textContent = 'Refresh every 5 min; forecast transport in 5-min steps. Provider cadence is not a 5-min observation.';
            updateWindBadge();
        }

        async function refreshLiveWeather() {
            if (!scenario || weatherRequest) return;
            const revision = frames.revision;
            const location = scenario.location;
            weatherRequest = new AbortController();
            const timeout = setTimeout(() => weatherRequest?.abort(), 25000);
            try {
                const response = await fetch(API_BASE + '/api/context/live?latitude=' + location.latitude + '&longitude=' + location.longitude, { signal: weatherRequest.signal, cache: 'no-store', headers: { Accept: 'application/json' } });
                if (!response.ok) throw new Error('weather ' + response.status);
                const context = await response.json();
                if (revision !== frames.revision) return;
                if (!context.weather) throw new Error('No weather returned');
                const elapsed = Math.floor((Date.now() - incidentStartedAt) / 300000) * 5;
                scenario = { ...scenario, weather: { ...scenario.weather, ...context.weather }, weatherTimeline: mergeWeatherTimeline(scenario.weatherTimeline, context.weatherTimeline, elapsed) };
                contextSnapshot = context;
                weatherFailed = false;
                invalidateForecasts();
                updateWeatherUi();
                requestTimelineFrame(selectedTimeMinutes, true);
            } catch (error) {
                weatherFailed = true;
                updateWeatherUi();
                console.warn('Live weather refresh unavailable', error);
            } finally { clearTimeout(timeout); weatherRequest = null; }
        }

        function startWeatherRefresh() {
            clearInterval(weatherRefreshTimer);
            weatherRefreshTimer = setInterval(refreshLiveWeather, WEATHER_REFRESH_MS);
        }

        function updateMetrics(frame) {
            const unit = frame?.concentrationUnit || 'ppm';
            document.getElementById('peak-concentration').textContent = formatConcentration(frame?.maxConcentration, unit);
            document.getElementById('affected-area').textContent = frame?.affectedAreaSqKm == null ? 'Unavailable' : Number(frame.affectedAreaSqKm).toFixed(3) + ' sq km';
            document.getElementById('population-at-risk').textContent = frame?.populationAtRisk == null ? 'No population data' : Number(frame.populationAtRisk).toLocaleString();
            document.getElementById('release-amount').textContent = scenario?.release ? releaseMass(scenario.release).toLocaleString(undefined, { maximumFractionDigits: 3 }) + ' kg simulated release' : 'Unavailable';
            const hazard = scenario?.hazard;
            document.getElementById('hazard-name').textContent = hazard?.name || 'Unavailable';
            document.getElementById('source-name').textContent = scenario?.location?.label || 'Princeton Middle School';
            document.getElementById('legend-red-value').textContent = hazard ? formatConcentration(hazard.idlhThreshold, unit) + '+' : 'Unavailable';
            document.getElementById('legend-yellow-value').textContent = hazard ? formatConcentration(hazard.pelThreshold, unit) + '+' : 'Unavailable';
            document.getElementById('legend-blue-value').textContent = hazard ? formatConcentration(hazard.traceThreshold, unit) + '+' : 'Unavailable';
            if (sourceMarker && scenario?.location) sourceMarker.setLngLat([scenario.location.longitude, scenario.location.latitude]);
        }

        function updateTimelineUi() {
            const slider = document.getElementById('timeline-slider');
            const label = document.getElementById('timeline-current');
            if (slider) slider.value = String(selectedTimeMinutes);
            if (label) label.textContent = `T+${selectedTimeMinutes} min${plumeIsFallback ? ' · local fallback' : ''}`;
        }

        function requestTimelineFrame(timeMinutes, settled = false) {
            playback.stop();
            selectedTimeMinutes = timelineMinute(timeMinutes);
            updateTimelineUi();
            clearTimeout(timelineTimer);
            const minute = selectedTimeMinutes;
            const cached = frames.cache.get(minute);
            if (cached) { renderPlume(cached); return; }
            document.getElementById('timeline-current').textContent = 'T+' + minute + ' min / loading';
            timelineTimer = setTimeout(async () => {
                if (!scenario) return;
                frames.cancelExcept(minute);
                try {
                    const frame = await frames.get(minute);
                    if (!frame || selectedTimeMinutes !== minute) return;
                    renderPlume(frame);
                } catch (error) {
                    if (error.name !== 'AbortError' && selectedTimeMinutes === minute) document.getElementById('timeline-current').textContent = 'T+' + minute + ' unavailable / showing T+' + (plumeFrame?.timeMinutes ?? '?');
                }
            }, settled ? 0 : TIMELINE_DEBOUNCE_MS);
        }

        function updateAffectedProperties(frame) {
            const list = document.getElementById('affected-list');
            if (!list) return;
            list.replaceChildren();
            const properties = frame?.buildingContamination || [];
            if (!properties.length) list.textContent = 'No modeled property exposure data for this frame.';
            for (const item of properties.slice(0, 5)) {
                const row = document.createElement('span');
                row.textContent = (item.band || 'UNKNOWN') + ' / ' + item.displayName + ' / ' + formatConcentration(item.concentration, frame?.concentrationUnit || 'ppm');
                list.appendChild(row);
            }
            const source = map?.getSource('affected-properties');
            if (source) source.setData({ type: 'FeatureCollection', features: properties.filter(item => Array.isArray(item.polygon) && item.polygon.length >= 3).map(item => {
                const ring = [...item.polygon];
                if (String(ring[0]) !== String(ring[ring.length - 1])) ring.push(ring[0]);
                return { type: 'Feature', properties: { color: item.affectedColor || '#43a8ff' }, geometry: { type: 'Polygon', coordinates: [ring] } };
            }) });
        }

        async function sendDispatch() {
            const input = document.getElementById('dispatch-input');
            const text = input?.value.trim();
            if (!text) return showToast('Describe an incident update first.');
            if (!scenario) return showToast('AI dispatch is using local mode; map is still available.');
            try {
                const dispatchApi = globalThis.AeroDispatch;
                const data = dispatchApi
                    ? await dispatchApi.submitDispatch(fetch, API_BASE + '/api/dispatch', text, scenario, contextSnapshot, selectedTimeMinutes)
                    : await (async () => {
                        const response = await fetch(API_BASE + '/api/dispatch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, scenario, context: contextSnapshot, timeMinutes: selectedTimeMinutes }) });
                        if (!response.ok) throw new Error('dispatch ' + response.status);
                        return response.json();
                    })();
                invalidateForecasts();
                scenario = data.scenario || scenario;
                if (data.frame && Number(data.frame.timeMinutes) === selectedTimeMinutes) renderPlume(data.frame);
                else requestTimelineFrame(selectedTimeMinutes, true);
                updateWeatherUi();
                updateUnitMarkers();
                syncReleaseControls();
                document.getElementById('dispatch-examples').hidden = false;
                document.getElementById('dispatch-response').textContent = `${data.assistantText || 'Scenario updated.'} (${data.provider || 'dispatcher'})`;
                showToast(data.assistantText || 'AI dispatch updated the scenario.');
                input.value = '';
            } catch (error) { showToast('AI service unavailable. Update was not applied; please retry.'); }
        }



        function clearSnap() {
            if (currentMarker) { currentMarker.remove(); currentMarker = null; }
            const searchInput = document.getElementById('search-input');
            if (searchInput) searchInput.value = '';
            const searchResults = document.getElementById('search-results');
            if (searchResults) searchResults.classList.add('hidden');
            if (map) map.flyTo({ center: PRINCETON_MIDDLE_SCHOOL, zoom: 14, pitch: 55, bearing: -20, duration: 1000 });
            showToast('Location snap and current marker cleared.');
        }

        function toggleSatellite() {
            const button = document.getElementById('btn-streets');
            if (button) button.setAttribute('aria-pressed', 'true');
            showToast('Satellite imagery unavailable: no imagery provider is configured. Showing street map.');
        }

        function flyToLocation(lng, lat, zoom = 14, name = "Location") {
            try {
                const numericLng = Number(lng);
                const numericLat = Number(lat);

                map.flyTo({
                    center: [numericLng, numericLat],
                    zoom: zoom,
                    pitch: 65,
                    bearing: -20,
                    duration: 2500
                });

                if (currentMarker) currentMarker.remove();

                const el = document.createElement('div');
                el.className = 'w-6 h-6 bg-blue-600 border-2 border-white rounded-full shadow-2xl flex items-center justify-center animate-bounce';
                
                currentMarker = new maplibregl.Marker({ element: el })
                    .setLngLat([numericLng, numericLat])
                    .setPopup(new maplibregl.Popup({ offset: 25 }).setHTML(`<div style="color:#000; font-weight:600; font-size:12px;">${name}</div>`))
                    .addTo(map);

                showToast("Flying to: " + name);
            } catch (err) {
                console.error("Error flying to coordinates:", err);
            }
        }

        function addManualMarker() {
            try {
                const nameInput = document.getElementById('manual-name');
                const lngInput = document.getElementById('manual-lng');
                const latInput = document.getElementById('manual-lat');

                const name = nameInput ? nameInput.value : "Custom Location";
                const lng = parseFloat(lngInput ? lngInput.value : 0);
                const lat = parseFloat(latInput ? latInput.value : 0);

                if (isNaN(lng) || isNaN(lat)) {
                    showToast("Please enter valid numeric latitude and longitude coordinates.");
                    return;
                }

                flyToLocation(lng, lat, 14, name);

                const modal = document.getElementById('loader-modal');
                if (modal) modal.classList.add('hidden');
                showToast("Added custom pin: " + name);
            } catch (err) {
                console.error("Error adding manual marker:", err);
            }
        }

        function setupSearchEngine() {
            const searchInput = document.getElementById('search-input');
            const searchResults = document.getElementById('search-results');
            if (!searchInput || !searchResults) return;

            let searchTimeout;

            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.trim();
                clearTimeout(searchTimeout);
                if (!query) {
                    searchResults.classList.add('hidden');
                    return;
                }

                searchTimeout = setTimeout(async () => {
                    try {
                        const response = await fetch('https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(query));
                        const data = await response.json();
                        searchResults.innerHTML = '';

                        if (!data || data.length === 0) {
                            searchResults.innerHTML = '<div class="p-3 text-xs text-slate-400">No real locations found</div>';
                        } else {
                            data.slice(0, 5).forEach(place => {
                                const div = document.createElement('div');
                                div.className = 'p-3 hover:bg-slate-800 cursor-pointer transition-all flex flex-col';
                                div.innerHTML = '<span class="font-semibold text-sm text-white">' + place.display_name + '</span><span class="text-xs text-slate-400">Lat: ' + place.lat + ', Lng: ' + place.lon + '</span>';
                                div.onclick = () => {
                                    const lon = parseFloat(place.lon);
                                    const lat = parseFloat(place.lat);
                                    const placeName = place.display_name.split(',')[0];
                                    
                                    flyToLocation(lon, lat, 14, placeName);

                                    searchResults.classList.add('hidden');
                                    searchInput.value = place.display_name;
                                };
                                searchResults.appendChild(div);
                            });
                        }
                        searchResults.classList.remove('hidden');
                    } catch (err) {
                        console.warn("Geocoding network error", err);
                    }
                }, 400);
            });

            document.addEventListener('click', (e) => {
                if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                    searchResults.classList.add('hidden');
                }
            });
        }

        function setupEventListeners() {
            const mapNav = document.getElementById('nav-map');
            const researchNav = document.getElementById('nav-research');
            const researchView = document.getElementById('research-view');
            const mapInterface = document.querySelector('.ui-overlay');
            const showResearch = (visible) => {
                researchView.hidden = !visible;
                mapNav.setAttribute('aria-selected', String(!visible));
                researchNav.setAttribute('aria-selected', String(visible));
                document.body.style.overflow = visible ? 'hidden' : '';
            };
            if (mapNav && researchNav && researchView) {
                mapNav.addEventListener('click', () => showResearch(false));
                researchNav.addEventListener('click', () => showResearch(true));
            }
            const streetsButton = document.getElementById('btn-streets');
            if (streetsButton) streetsButton.addEventListener('click', toggleSatellite);
            const timelineSlider = document.getElementById('timeline-slider');
            if (timelineSlider) {
                timelineSlider.addEventListener('input', (event) => requestTimelineFrame(event.target.value));
                timelineSlider.addEventListener('change', (event) => requestTimelineFrame(event.target.value, true));
            }
            document.getElementById('forecast-play').addEventListener('click', () => {
                if (playback.playing) return playback.stop();
                if (!scenario) return showToast('Wait for the incident to load.');
                clearTimeout(timelineTimer);
                setExposureMode(false);
                const start = !playbackStarted || selectedTimeMinutes >= 120 ? 0 : selectedTimeMinutes;
                playbackStarted = true;
                playback.play(start);
            });
            document.getElementById('forecast-restart').addEventListener('click', () => {
                if (!scenario) return;
                clearTimeout(timelineTimer);
                setExposureMode(false);
                playback.play(0);
            });
            document.getElementById('forecast-video').addEventListener('click', exportForecastVideo);
            document.getElementById('ai-dispatch-orb').addEventListener('click', startVoiceDispatch);
            document.getElementById('release-form').addEventListener('submit', applyRelease);
            for (const format of ['csv', 'png', 'jpg']) document.getElementById('export-' + format).addEventListener('click', () => exportExposure(format));
            document.getElementById('view-plume').addEventListener('click', () => setExposureMode(false));
            document.getElementById('view-exposure').addEventListener('click', () => setExposureMode(true));
            const affectedToggle = document.getElementById('affected-toggle');
            if (affectedToggle) affectedToggle.addEventListener('click', () => {
                const expanded = affectedToggle.getAttribute('aria-expanded') === 'true';
                affectedToggle.setAttribute('aria-expanded', String(!expanded));
                affectedToggle.textContent = expanded ? 'SHOW' : 'HIDE';
                document.getElementById('affected-list').hidden = expanded;
            });
            document.querySelectorAll('[data-command]').forEach(button => button.addEventListener('click', () => {
                const input = document.getElementById('dispatch-input');
                input.value = button.dataset.command;
                input.focus();
            }));
            const dispatchInput = document.getElementById('dispatch-input');
            const dispatchToggle = document.getElementById('dispatch-chat-toggle');
            if (dispatchToggle && dispatchInput) {
                dispatchToggle.addEventListener('click', () => {
                    const isHidden = dispatchInput.classList.toggle('hidden');
                    dispatchToggle.setAttribute('aria-expanded', String(!isHidden));
                    document.getElementById('dispatch-examples').hidden = isHidden;
                    if (!isHidden) { dispatchInput.focus(); showToast('Describe what changed, or choose an example. Press Enter to send.'); }
                });
                dispatchInput.addEventListener('keydown', (event) => { if (event.key === 'Enter') sendDispatch(); if (event.key === 'Escape') { dispatchInput.classList.add('hidden'); dispatchToggle.setAttribute('aria-expanded', 'false'); } });
            }
            const clearSnapButton = document.getElementById('btn-clear-snap');
            if (clearSnapButton) clearSnapButton.addEventListener('click', clearSnap);
            const btnOpenLoader = document.getElementById('btn-open-loader');
            const loaderModal = document.getElementById('loader-modal');
            if (btnOpenLoader && loaderModal) {
                btnOpenLoader.addEventListener('click', () => loaderModal.classList.remove('hidden'));
            }

            const btnCloseLoader = document.getElementById('btn-close-loader');
            if (btnCloseLoader && loaderModal) {
                btnCloseLoader.addEventListener('click', () => loaderModal.classList.add('hidden'));
            }

            const btnCancelLoader = document.getElementById('btn-cancel-loader');
            if (btnCancelLoader && loaderModal) {
                btnCancelLoader.addEventListener('click', () => loaderModal.classList.add('hidden'));
            }

            const btnSubmitLoader = document.getElementById('btn-submit-loader');
            if (btnSubmitLoader) {
                btnSubmitLoader.addEventListener('click', addManualMarker);
            }

            document.querySelectorAll('.landmark-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const lng = parseFloat(btn.getAttribute('data-lng'));
                    const lat = parseFloat(btn.getAttribute('data-lat'));
                    const zoom = parseInt(btn.getAttribute('data-zoom') || 14);
                    const name = btn.getAttribute('data-name');
                    flyToLocation(lng, lat, zoom, name);
                });
            });
        }

        function showToast(message) {
            const toast = document.getElementById('toast');
            const toastText = document.getElementById('toast-text');
            if (!toast || !toastText) return;

            toastText.innerText = message;
            toast.classList.remove('opacity-0');
            setTimeout(() => {
                toast.classList.add('opacity-0');
            }, 3500);
        }

        window.onload = function() {
            initMap();
        };
