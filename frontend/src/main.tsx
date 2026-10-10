import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Cartesian3,
  Cesium3DTileset,
  Color,
  Ion,
  Math as CesiumMath,
  Terrain,
  Viewer,
  createOsmBuildingsAsync,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import './styles.css';

type Band = 'TRACE' | 'PEL' | 'IDLH';
type Scenario = {
  scenarioId: string;
  version: number;
  location: { latitude: number; longitude: number; label: string };
  hazard: { name: string; category: string };
  release: { rateKgPerSecond: number; durationMinutes: number; sourceHeightMeters: number; isPressurized: boolean; hasExploded: boolean };
  weather: { windSpeedMetersPerSecond: number; windDirectionFromDegrees: number; temperatureCelsius: number; source: string };
};
type Particle = { longitude: number; latitude: number; altitudeMeters: number; radiusMeters: number; concentration: number; band: Band; opacity: number };
type VolumeCell = { longitude: number; latitude: number; groundElevationMeters: number; heightMeters: number; radiusMeters: number; concentration: number; band: Band; opacity: number };
type PlumeFrame = { timeMinutes: number; particles: Particle[]; volumeCells: VolumeCell[]; maxConcentration: number; assumptions: string[] };

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ION_TOKEN = import.meta.env.VITE_CESIUM_ION_ACCESS_TOKEN ?? '';

const bandColor = (band: Band) => band === 'IDLH' ? Color.RED : band === 'PEL' ? Color.ORANGE : Color.CYAN;

function MapScene({ scenario, frame }: { scenario: Scenario; frame: PlumeFrame }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const particlesRef = useRef<any[]>([]);
  const volumesRef = useRef<any[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;
    if (ION_TOKEN) Ion.defaultAccessToken = ION_TOKEN;
    const viewer = new Viewer(containerRef.current, {
      terrain: ION_TOKEN ? Terrain.fromWorldTerrain() : undefined,
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      navigationHelpButton: false,
      sceneModePicker: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      requestRenderMode: true,
    });
    viewerRef.current = viewer;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(scenario.location.longitude, scenario.location.latitude, 1100),
      orientation: { heading: CesiumMath.toRadians(28), pitch: CesiumMath.toRadians(-52), roll: 0 },
      duration: 0,
    });

    if (ION_TOKEN) {
      createOsmBuildingsAsync().then((buildings) => viewer.scene.primitives.add(buildings)).catch(() => undefined);
    }

    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
  }, [scenario.location.latitude, scenario.location.longitude]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    particlesRef.current.forEach((entity) => viewer.entities.remove(entity));
    volumesRef.current.forEach((entity) => viewer.entities.remove(entity));
    particlesRef.current = frame.particles.map((particle) => viewer.entities.add({
      position: Cartesian3.fromDegrees(particle.longitude, particle.latitude, particle.altitudeMeters),
      ellipsoid: {
        radii: new Cartesian3(particle.radiusMeters, particle.radiusMeters, particle.radiusMeters * 0.7),
        material: bandColor(particle.band).withAlpha(particle.opacity),
        outline: true,
        outlineColor: bandColor(particle.band).withAlpha(0.55),
        outlineWidth: 1,
      },
    }));
    volumesRef.current = frame.volumeCells.map((cell) => viewer.entities.add({
      position: Cartesian3.fromDegrees(cell.longitude, cell.latitude, cell.groundElevationMeters + cell.heightMeters / 2),
      ellipsoid: {
        radii: new Cartesian3(cell.radiusMeters, cell.radiusMeters * 0.7, cell.heightMeters / 2),
        material: bandColor(cell.band).withAlpha(cell.opacity),
      },
    }));
    viewer.scene.requestRender();
  }, [frame]);

  return <div ref={containerRef} className="map-canvas" />;
}

function App() {
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [frame, setFrame] = useState<PlumeFrame | null>(null);
  const [timeMinutes, setTimeMinutes] = useState(30);
  const [message, setMessage] = useState('');
  const [assistant, setAssistant] = useState('Command center initializing.');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/scenario`).then((response) => response.json()),
      fetch(`${API_BASE}/api/plume?timeMinutes=30`).then((response) => response.json()),
    ]).then(([loadedScenario, loadedFrame]) => {
      setScenario(loadedScenario);
      setFrame(loadedFrame);
      setLoading(false);
    }).catch(() => {
      setAssistant('Backend offline. Start FastAPI to load the live demo scenario.');
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!scenario) return;
    fetch(`${API_BASE}/api/plume?timeMinutes=${timeMinutes}`)
      .then((response) => response.json())
      .then(setFrame)
      .catch(() => undefined);
  }, [timeMinutes, scenario]);

  const submitDispatch = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!scenario || !message.trim()) return;
    const response = await fetch(`${API_BASE}/api/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: message, scenario }),
    });
    const result = await response.json();
    setScenario(result.scenario);
    setFrame(result.frame);
    setAssistant(result.assistantText);
    setMessage('');
  };

  if (loading) return <div className="loading">Loading command center...</div>;
  if (!scenario || !frame) return <div className="loading">{assistant}</div>;

  return (
    <main className="command-center">
      <header className="topbar">
        <div>
          <p className="eyebrow">AERO-HAZARD / PLUME</p>
          <h1>Atmospheric incident command</h1>
        </div>
        <div className="status-pill"><span /> OPEN 3D FALLBACK</div>
      </header>
      <section className="workspace">
        <div className="map-panel">
          <MapScene scenario={scenario} frame={frame} />
          <div className="map-overlay">
            <div className="overlay-label">LIVE SIMULATION / FRAME {frame.timeMinutes} MIN</div>
            <div className="legend"><span className="trace" /> TRACE <span className="pel" /> PEL <span className="idlh" /> IDLH</div>
          </div>
        </div>
        <aside className="control-panel">
          <div className="panel-heading"><span className="signal">●</span><div><p className="eyebrow">ACTIVE INCIDENT</p><h2>{scenario.hazard.name}</h2></div></div>
          <div className="metrics">
            <div><span>MAX CONCENTRATION</span><strong>{frame.maxConcentration.toFixed(1)} ppm</strong></div>
            <div><span>WIND VECTOR</span><strong>{scenario.weather.windSpeedMetersPerSecond.toFixed(1)} m/s</strong><small>from {scenario.weather.windDirectionFromDegrees}°</small></div>
            <div><span>RELEASE PROFILE</span><strong>{scenario.release.rateKgPerSecond.toFixed(1)} kg/s</strong><small>{scenario.release.isPressurized ? 'PRESSURIZED' : 'UNPRESSURIZED'}</small></div>
          </div>
          <label className="control-label">SIMULATION TIME <output>{timeMinutes} MIN</output></label>
          <input className="timeline" type="range" min="0" max="120" value={timeMinutes} onChange={(event) => setTimeMinutes(Number(event.target.value))} />
          <div className="timeline-labels"><span>T+0</span><span>T+60</span><span>T+120</span></div>
          <div className="dispatcher">
            <div className="panel-heading"><div><p className="eyebrow">AI DISPATCHER</p><p className="assistant">{assistant}</p></div></div>
            <form onSubmit={submitDispatch} className="dispatch-form"><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Try: The tank exploded" /><button type="submit">SEND</button></form>
          </div>
          <div className="assumptions"><p className="eyebrow">MODEL ASSUMPTIONS</p>{frame.assumptions.map((assumption) => <p key={assumption}>+ {assumption}</p>)}</div>
        </aside>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
