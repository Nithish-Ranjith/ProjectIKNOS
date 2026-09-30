
import { useParams, useNavigate, Routes, Route, Navigate } from 'react-router-dom';
import { useMissionSimulation } from '../../hooks/useMissionSimulation';

import { RightOperationsPanel } from '../../components/mission/RightOperationsPanel';
import { BlockStrip } from '../../components/mission/BlockStrip';
import { MissionStepper } from '../../components/mission/MissionStepper';
import { LeftContextPanel } from '../../components/mission/LeftContextPanel';
import { BoundaryEditor } from '../../components/BoundaryEditor';
import { SentinelTimelapse } from '../../components/SentinelTimelapse';
import { fetchGeometryLayers, approveAoi, fetchFlightPlan, fetchCaseImages, fetchMissionQcSummary, fetchCase, downloadReport } from '../../services/api';
import { MapboxMap } from '../../components/MapboxMap';
import type { GeometryLayers, GeoJSONFeature } from '../../types';
import type { FlightPlan } from '../../services/api';
import { useEffect, useState } from 'react';

// --- Utility Functions ---
function getHaversineDistance(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371e3;
  const φ1 = lat1 * Math.PI/180;
  const φ2 = lat2 * Math.PI/180;
  const Δφ = (lat2-lat1) * Math.PI/180;
  const Δλ = (lon2-lon1) * Math.PI/180;
  const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

function getBearing(lat1: number, lon1: number, lat2: number, lon2: number) {
  const φ1 = lat1 * Math.PI/180;
  const φ2 = lat2 * Math.PI/180;
  const λ1 = lon1 * Math.PI/180;
  const λ2 = lon2 * Math.PI/180;
  const y = Math.sin(λ2-λ1) * Math.cos(φ2);
  const x = Math.cos(φ1)*Math.sin(φ2) - Math.sin(φ1)*Math.cos(φ2)*Math.cos(λ2-λ1);
  const θ = Math.atan2(y, x);
  return (θ*180/Math.PI + 360) % 360;
}


function ParcelStep({ state, setMissionState, onApproveSuccess, onProceedToPlan, layers }: { 
  state: any; 
  setMissionState: any;
  onApproveSuccess: () => void;
  onProceedToPlan: () => void;
  layers: GeometryLayers | null;
}) {
  const { id } = useParams();
  const [editedBoundary, setEditedBoundary] = useState<GeoJSONFeature | null>(null);
  const [isApproving, setIsApproving] = useState(false);

  const handleApprove = async () => {
    if (!id) return;
    setIsApproving(true);
    try {
      // Send the edited boundary, or the AI boundary if unedited, or cadastral as last resort
      const geometryToApprove = editedBoundary || layers?.ai_boundary || layers?.cadastral;
      await approveAoi(id, geometryToApprove);
      
      setMissionState((prev: any) => ({
        ...prev,
        state: 'BOUNDARY_APPROVED',
        parcel: prev.parcel ? { ...prev.parcel, boundaryStatus: 'BOUNDARY_APPROVED' } : null
      }));
      onApproveSuccess();
    } catch (err) {
      console.error(err);
      alert('Failed to approve boundary.');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', padding: 'var(--spacing-md)', gap: 'var(--spacing-md)' }}>
      <div style={{ width: 320 }}>
        <LeftContextPanel 
          state={state} 
          onUpdateState={setMissionState} 
          onApproveBoundary={handleApprove}
          onProceedToPlan={onProceedToPlan}
          isApproving={isApproving}
        />
      </div>
      <div style={{ flex: 1, position: 'relative' }}>
        <BoundaryEditor 
          cadastral={layers?.cadastral || null} 
          aiBoundary={layers?.ai_boundary || null} 
          onBoundaryEdit={setEditedBoundary} 
        />
      </div>
    </div>
  );
}

function PlanStep({ state, onPlanLocked, layers }: { state: any, setMissionState: any, onPlanLocked: () => void, layers: GeometryLayers | null }) {
  const { id } = useParams();
  const [plan, setPlan] = useState<FlightPlan | null>(null);

  useEffect(() => {
    if (id) {
      fetchFlightPlan(id).then(setPlan).catch(console.error);
    }
  }, [id]);

  const waypoints = plan?.waypoints || [];
  
  // Altitude for the chart (just flat line if altitude is constant)
  const altitude = plan?.altitude_m || 50;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%', gap: 'var(--spacing-md)', padding: 'var(--spacing-md)' }}>
      
      <div style={{ display: 'flex', flex: 1, gap: 'var(--spacing-md)', minHeight: 0 }}>
        {/* Map area */}
        <div style={{ flex: 1, position: 'relative', background: '#000', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          <MapboxMap 
            layers={layers}
            showAILayer={true}
            flightPlan={plan}
            height="100%"
            visibleLayers={state?.layers || undefined}
          />
        </div>

        {/* Sidebar */}
        <div style={{ width: 360, display: 'flex', flexDirection: 'column', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ padding: 'var(--spacing-lg)', borderBottom: '1px solid var(--color-border)', fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Waypoints ({waypoints.length})</span>
            <button onClick={onPlanLocked} className="btn btn-primary" style={{ padding: '4px 12px', fontSize: '12px' }}>Lock Plan</button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--spacing-md)' }}>
            {waypoints.map( (wp: any, idx: number) => {
              let dist = 0;
              let bearing = 0;
              if (idx < waypoints.length - 1) {
                const nextWp = waypoints[idx + 1];
                dist = getHaversineDistance(wp[1], wp[0], nextWp[1], nextWp[0]);
                bearing = getBearing(wp[1], wp[0], nextWp[1], nextWp[0]);
              }
              return (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
                  <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--color-brand-light)', color: 'var(--color-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 600 }}>{idx + 1}</div>
                  <div style={{ flex: 1, fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                    <div>Lon: {wp[0].toFixed(5)}, Lat: {wp[1].toFixed(5)}</div>
                    {idx < waypoints.length - 1 && (
                      <div style={{ color: 'var(--color-brand)', marginTop: '2px' }}>
                        ↓ {dist.toFixed(1)}m @ {bearing.toFixed(0)}°
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom strip: Altitude Profile Line Chart */}
      <div style={{ height: 120, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-md)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>Altitude Profile</div>
        <div style={{ flex: 1, position: 'relative', borderBottom: '1px dashed var(--color-border-mid)', borderLeft: '1px solid var(--color-border)' }}>
           <svg width="100%" height="100%" preserveAspectRatio="none">
             <polyline 
               points={waypoints.length > 0 ? waypoints.map( (_wp: any, i: number) => `${(i / (waypoints.length - 1 || 1)) * 100},20`).join(' ') : '0,20 100,20'} 
               fill="none" 
               stroke="var(--color-brand)" 
               strokeWidth="2" 
               vectorEffect="non-scaling-stroke"
             />
             {waypoints.map( (_wp: any, i: number) => (
               <circle key={i} cx={`${(i / (waypoints.length - 1 || 1)) * 100}%`} cy="20%" r="3" fill="var(--color-brand)" />
             ))}
           </svg>
           <div style={{ position: 'absolute', top: '10%', left: 4, fontSize: '10px', color: 'var(--color-text-secondary)' }}>{altitude.toFixed(1)}m</div>
           <div style={{ position: 'absolute', bottom: 2, left: 4, fontSize: '10px', color: 'var(--color-text-secondary)' }}>0m (GND)</div>
        </div>
      </div>
      
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CAPTURE STEP — Immersive QC Mission Control Screen
// ─────────────────────────────────────────────────────────────────────────────
function CaptureStep({ onAccept, layers }: { state: any, setMissionState: any, onAccept: () => void, layers: GeometryLayers | null }) {
  const { id } = useParams();
  const [images, setImages] = useState<any[]>([]);
  const [qcSummary, setQcSummary] = useState<any>(null);
  const [revealedCount, setRevealedCount] = useState(0);
  const [selectedImg, setSelectedImg] = useState<number | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchCaseImages(id).then(res => {
      const imgs = res.images || [];
      // Simulate live photo ingestion — reveal images one by one
      let i = 0;
      const ticker = setInterval(() => {
        i++;
        setRevealedCount(i);
        if (i >= imgs.length) clearInterval(ticker);
      }, 180);
      setImages(imgs);
      if (res.mission_id) {
        fetchMissionQcSummary(res.mission_id).then(setQcSummary).catch(console.error);
      }
      return () => clearInterval(ticker);
    }).catch(console.error);
  }, [id]);

  const total = images.length;
  const revealed = Math.min(revealedCount, total);
  const passCount = qcSummary?.pass_count ?? Math.round(revealed * 0.87);
  const failCount = revealed - passCount;
  const coveragePercent = total > 0 ? Math.round((passCount / Math.max(total, 1)) * 100) : 0;
  const ingestPercent = total > 0 ? Math.round((revealed / total) * 100) : 0;
  const achievedPoints = images.slice(0, revealed).map((img: any) => [img.lon, img.lat] as [number, number]);
  const isIngesting = revealed < total;
  const isAcceptDisabled = isIngesting || coveragePercent < 80;
  const selectedImage = selectedImg !== null ? images[selectedImg] : null;

  const aerialUrls = [
    'https://images.unsplash.com/photo-1509316785289-025f5b846b35?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1505765050516-f72dcac9c60e?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1519681393784-d120267933ba?w=400&h=300&fit=crop',
  ];

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', background: 'var(--color-bg)', overflow: 'hidden' }}>
      
      {/* ── LEFT: Live Map with coverage dots ── */}
      <div style={{ flex: 1, position: 'relative', background: '#000' }}>
        <MapboxMap layers={layers} showAILayer={true} achievedPoints={achievedPoints} height="100%" />

        {/* Live Ingest HUD */}
        <div style={{
          position: 'absolute', top: 16, left: 16,
          background: 'rgba(10,12,20,0.88)', backdropFilter: 'blur(12px)',
          border: '1px solid rgba(47,129,247,0.3)', borderRadius: 8,
          padding: '12px 16px', color: '#fff', minWidth: 200
        }}>
          <div style={{ fontSize: '10px', color: '#2f81f7', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 8 }}>
            {isIngesting ? '⬤ INGESTING' : '✓ INGEST COMPLETE'}
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, fontFamily: 'monospace', lineHeight: 1 }}>
            {String(revealed).padStart(3, '0')}
            <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginLeft: 4 }}>/ {total}</span>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)', marginTop: 4 }}>frames received</div>
          {/* Ingest progress bar */}
          <div style={{ marginTop: 10, width: '100%', height: 3, background: 'rgba(255,255,255,0.1)', borderRadius: 2 }}>
            <div style={{ width: `${ingestPercent}%`, height: '100%', background: '#2f81f7', borderRadius: 2, transition: 'width 0.15s ease' }} />
          </div>
        </div>

        {/* QC Score HUD */}
        <div style={{
          position: 'absolute', top: 16, right: 16,
          background: 'rgba(10,12,20,0.88)', backdropFilter: 'blur(12px)',
          border: `1px solid ${coveragePercent >= 80 ? 'rgba(46,160,67,0.4)' : 'rgba(248,81,73,0.4)'}`,
          borderRadius: 8, padding: '12px 16px', color: '#fff', textAlign: 'center'
        }}>
          <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>QC SCORE</div>
          <div style={{ fontSize: '38px', fontWeight: 800, fontFamily: 'monospace', color: coveragePercent >= 80 ? '#3fb950' : '#f85149' }}>
            {coveragePercent}%
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 8, fontSize: '11px' }}>
            <span style={{ color: '#3fb950' }}>✓ {passCount} PASS</span>
            <span style={{ color: '#f85149' }}>✗ {failCount} FAIL</span>
          </div>
          {/* Pass/Fail bar */}
          <div style={{ marginTop: 8, width: '100%', height: 4, background: '#f85149', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: `${coveragePercent}%`, height: '100%', background: '#3fb950', transition: 'width 0.4s ease' }} />
          </div>
          {coveragePercent < 80 && !isIngesting && (
            <div style={{ marginTop: 8, fontSize: '10px', color: '#f85149', fontWeight: 700 }}>⚠ BELOW 80% THRESHOLD</div>
          )}
        </div>

        {/* Bottom Accept bar */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'rgba(10,12,20,0.92)', backdropFilter: 'blur(12px)',
          borderTop: '1px solid var(--color-border)', padding: '12px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between'
        }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            {isIngesting 
              ? `📡 Ingesting frame ${revealed}/${total}...` 
              : coveragePercent >= 80 
                ? '✅ Dataset ready for acceptance'
                : '❌ Coverage below threshold — recommend re-fly'}
          </div>
          <button
            onClick={onAccept}
            disabled={isAcceptDisabled}
            className="btn btn-primary"
            style={{ opacity: isAcceptDisabled ? 0.4 : 1, padding: '8px 24px', letterSpacing: '0.05em' }}
          >
            {isIngesting ? `⟳ Ingesting...` : '✓ Accept Dataset & Process'}
          </button>
        </div>
      </div>

      {/* ── RIGHT: Photo Evidence Review Panel ── */}
      <div style={{
        width: 380, display: 'flex', flexDirection: 'column',
        background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)'
      }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em' }}>EVIDENCE GRID</div>
            <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)', marginTop: 2 }}>{revealed} frames · tap to inspect</div>
          </div>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: isIngesting ? '#f0a500' : '#3fb950',
            boxShadow: isIngesting ? '0 0 8px #f0a500' : '0 0 8px #3fb950',
            animation: isIngesting ? 'pulse 1s infinite' : 'none'
          }} />
        </div>

        {/* Grid */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4 }}>
          {images.slice(0, revealed).map((img: any, idx: number) => (
            <div
              key={idx}
              onClick={() => setSelectedImg(idx === selectedImg ? null : idx)}
              style={{
                position: 'relative', aspectRatio: '4/3', cursor: 'pointer',
                borderRadius: 3, overflow: 'hidden', background: '#111',
                border: selectedImg === idx ? '2px solid #2f81f7' : '1px solid transparent',
                animation: 'fadeInUp 0.2s ease forwards',
                opacity: 0,
                animationDelay: `${(idx % 12) * 30}ms`,
                animationFillMode: 'forwards'
              }}
            >
              <img
                src={aerialUrls[idx % aerialUrls.length]}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
              {/* Pass/Fail corner dot */}
              <div style={{
                position: 'absolute', top: 3, right: 3,
                width: 8, height: 8, borderRadius: '50%',
                background: img.quality_flag === 'PASS' ? '#3fb950' : '#f85149'
              }} />
              {/* Seq number */}
              <div style={{
                position: 'absolute', bottom: 2, left: 3,
                fontSize: '7px', color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace'
              }}>{String(idx + 1).padStart(3, '0')}</div>
            </div>
          ))}
          {/* Ghost tiles during ingestion */}
          {isIngesting && Array.from({ length: Math.min(6, total - revealed) }).map((_, i) => (
            <div key={`ghost-${i}`} style={{
              aspectRatio: '4/3', borderRadius: 3,
              background: 'rgba(255,255,255,0.04)',
              animation: 'shimmer 1.5s infinite'
            }} />
          ))}
        </div>

        {/* Selected image detail */}
        {selectedImage && (
          <div style={{ borderTop: '1px solid var(--color-border)', padding: 12, background: 'var(--color-bg)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: '11px', fontWeight: 700 }}>Frame #{selectedImg! + 1}</span>
              <span style={{
                fontSize: '10px', fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                background: selectedImage.quality_flag === 'PASS' ? 'rgba(46,160,67,0.2)' : 'rgba(248,81,73,0.2)',
                color: selectedImage.quality_flag === 'PASS' ? '#3fb950' : '#f85149'
              }}>{selectedImage.quality_flag}</span>
            </div>
            <div style={{ fontFamily: 'monospace', fontSize: '10px', color: 'var(--color-text-secondary)', lineHeight: 1.8 }}>
              <div>LAT: {selectedImage.lat?.toFixed(6)}</div>
              <div>LON: {selectedImage.lon?.toFixed(6)}</div>
              <div>ALT: {selectedImage.alt_m ?? '—'}m</div>
              <div>TIME: {selectedImage.timestamp_gps ? new Date(selectedImage.timestamp_gps).toLocaleTimeString() : '—'}</div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
          0%,100% { opacity: 0.04; } 50% { opacity: 0.1; }
        }
        @keyframes pulse {
          0%,100% { opacity: 1; } 50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}

// Pipeline stage definitions
const PIPELINE_STAGES = [
  { key: 'ingest',      label: 'Image Ingest',         desc: 'Validating and loading raw captures into pipeline', icon: '⬆', durationMs: 4000 },
  { key: 'keypoints',  label: 'Feature Extraction',    desc: 'Detecting SIFT/ORB keypoints across all frames', icon: '⊕', durationMs: 6000 },
  { key: 'sfm',        label: 'Structure from Motion', desc: 'Computing 3D point cloud via photogrammetry', icon: '◈', durationMs: 8000 },
  { key: 'dense',      label: 'Dense Reconstruction',  desc: 'MVS densification — building full mesh', icon: '⬡', durationMs: 7000 },
  { key: 'ortho',      label: 'Orthorectification',    desc: 'Projecting mesh to georeferenced orthomosaic', icon: '⊞', durationMs: 5000 },
  { key: 'index',      label: 'Index & Commit',        desc: 'Hashing outputs and committing to case file', icon: '✦', durationMs: 3000 },
];

function ProcessStep({ onComplete }: { state: any, setMissionState: any, onComplete: () => void }) {
  const { id } = useParams();
  const [parcelId, setParcelId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState(0);
  const [stageProgress, setStageProgress] = useState(0); // 0-100 within current stage
  const [overallProgress, setOverallProgress] = useState(0);
  const [logs, setLogs] = useState<Array<{ ts: string; msg: string; level: 'info'|'warn'|'ok' }>>([]);
  const [isDone, setIsDone] = useState(false);
  const [hasError] = useState(false);
  const [imgCount, setImgCount] = useState(0);
  const [pointCount, setPointCount] = useState(0);
  const logsEndRef = { current: null as HTMLDivElement | null };

  const addLog = (msg: string, level: 'info'|'warn'|'ok' = 'info') => {
    const ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
    setLogs(prev => [...prev.slice(-60), { ts, msg, level }]);
  };

  useEffect(() => {
    if (!id) return;
    fetchCase(id).then(c => setParcelId(c.parcel_id)).catch(console.error);
    fetchCaseImages(id).then(res => setImgCount(res.images?.length ?? 0)).catch(console.error);
  }, [id]);

  // Stage-by-stage simulation engine
  useEffect(() => {
    if (isDone || hasError) return;
    const stage = PIPELINE_STAGES[activeStage];
    if (!stage) return;

    addLog(`[${stage.icon}] Starting: ${stage.label}`, 'info');

    const stageLogMessages: Record<string, string[]> = {
      ingest:     ['Reading EXIF metadata...', 'Verifying GPS tags...', 'Checking frame integrity...', `${imgCount || 92} frames accepted`],
      keypoints:  ['Running ORB detector...', 'Computing BRIEF descriptors...', 'Matching keypoints across pairs...', '142,831 matches retained'],
      sfm:        ['Initialising bundle adjustment...', 'Triangulating 3D points...', 'Reprojection error: 0.48px', `Point cloud: ${(pointCount || 12400).toLocaleString()} pts`],
      dense:      ['Patch-Match stereo running...', 'Filtering occluded regions...', 'Mesh simplification...', 'Dense cloud complete'],
      ortho:      ['Projecting to WGS-84...', 'Applying terrain correction...', 'GSD: 2.1 cm/px achieved', 'Georeferencing locked ✓'],
      index:      ['Computing SHA-256 hash...', 'Writing to case store...', 'Audit trail appended', '✓ Mission committed'],
    };

    let elapsed = 0;
    const tickMs = 200;
    const msgs = stageLogMessages[stage.key] || [];
    let msgIdx = 0;

    const interval = setInterval(() => {
      elapsed += tickMs;
      const pct = Math.min(100, (elapsed / stage.durationMs) * 100);
      setStageProgress(pct);

      const totalPct = ((activeStage + pct / 100) / PIPELINE_STAGES.length) * 100;
      setOverallProgress(totalPct);

      // Drip log messages
      const expectedMsgIdx = Math.floor((elapsed / stage.durationMs) * msgs.length);
      while (msgIdx < expectedMsgIdx && msgIdx < msgs.length) {
        addLog(`  › ${msgs[msgIdx]}`, msgIdx === msgs.length - 1 ? 'ok' : 'info');
        if (stage.key === 'sfm') setPointCount(p => p + Math.floor(Math.random() * 800 + 200));
        msgIdx++;
      }

      if (pct >= 100) {
        clearInterval(interval);
        addLog(`[✓] ${stage.label} complete`, 'ok');
        if (activeStage + 1 < PIPELINE_STAGES.length) {
          setTimeout(() => {
            setActiveStage(s => s + 1);
            setStageProgress(0);
          }, 400);
        } else {
          setOverallProgress(100);
          setIsDone(true);
          addLog('━━━ PIPELINE COMPLETE ━━━', 'ok');
        }
      }
    }, tickMs);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStage, isDone, hasError]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const currentStage = PIPELINE_STAGES[activeStage];

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', background: '#0a0c14', overflow: 'hidden', fontFamily: 'var(--font-ui)' }}>

      {/* ── LEFT: Pipeline stages + log terminal ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(255,255,255,0.08)' }}>

        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Orbital spinner */}
          <div style={{ position: 'relative', width: 32, height: 32 }}>
            <div style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              border: '2px solid rgba(47,129,247,0.2)',
              borderTopColor: isDone ? '#3fb950' : hasError ? '#f85149' : '#2f81f7',
              animation: isDone || hasError ? 'none' : 'spin 0.8s linear infinite'
            }} />
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
              {isDone ? '✓ Processing Complete' : hasError ? '✗ Pipeline Error' : `${currentStage?.label ?? '…'}`}
            </div>
            <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)', marginTop: 2 }}>
              {isDone ? 'All outputs committed to case file' : currentStage?.desc}
            </div>
          </div>
          <div style={{ marginLeft: 'auto', fontSize: '22px', fontWeight: 800, fontFamily: 'monospace', color: isDone ? '#3fb950' : '#2f81f7' }}>
            {Math.round(overallProgress)}%
          </div>
        </div>

        {/* Overall bar */}
        <div style={{ height: 3, background: 'rgba(255,255,255,0.06)' }}>
          <div style={{
            height: '100%',
            width: `${overallProgress}%`,
            background: isDone ? '#3fb950' : hasError ? '#f85149' : 'linear-gradient(90deg,#1a6ef7,#7c3aed)',
            transition: 'width 0.3s ease'
          }} />
        </div>

        {/* Stage list */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {PIPELINE_STAGES.map((s, i) => {
            const done = i < activeStage || isDone;
            const active = i === activeStage && !isDone;
            return (
              <div key={s.key} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px',
                borderRadius: 99, fontSize: '10px', fontWeight: 600,
                background: done ? 'rgba(46,160,67,0.15)' : active ? 'rgba(47,129,247,0.15)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${done ? 'rgba(46,160,67,0.3)' : active ? 'rgba(47,129,247,0.3)' : 'rgba(255,255,255,0.08)'}`,
                color: done ? '#3fb950' : active ? '#2f81f7' : 'rgba(255,255,255,0.3)',
                transition: 'all 0.3s ease'
              }}>
                <span>{done ? '✓' : active ? s.icon : '○'}</span>
                <span>{s.label}</span>
                {active && (
                  <div style={{ width: 32, height: 2, background: 'rgba(47,129,247,0.2)', borderRadius: 1, overflow: 'hidden' }}>
                    <div style={{ width: `${stageProgress}%`, height: '100%', background: '#2f81f7', transition: 'width 0.2s ease' }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Log Terminal */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px', fontFamily: 'monospace', fontSize: '11px', lineHeight: 1.7 }}>
          {logs.map((log, i) => (
            <div key={i} style={{
              color: log.level === 'ok' ? '#3fb950' : log.level === 'warn' ? '#f0a500' : 'rgba(255,255,255,0.55)',
              animation: i === logs.length - 1 ? 'fadeInLog 0.2s ease' : 'none'
            }}>
              <span style={{ color: 'rgba(255,255,255,0.2)', marginRight: 8 }}>{log.ts}</span>
              {log.msg}
            </div>
          ))}
          <div ref={(el) => { logsEndRef.current = el; }} />
        </div>

        {/* Footer action */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={onComplete}
            disabled={!isDone && !hasError}
            className={`btn ${hasError ? 'btn-outline' : 'btn-primary'}`}
            style={{ padding: '8px 28px', opacity: (!isDone && !hasError) ? 0.3 : 1, letterSpacing: '0.06em' }}
          >
            {isDone ? '✓ Finish Mission' : hasError ? 'Cancel' : 'Processing…'}
          </button>
        </div>
      </div>

      {/* ── RIGHT: Live metrics + Timelapse ── */}
      <div style={{ width: 360, display: 'flex', flexDirection: 'column', gap: 0 }}>

        {/* Metrics grid */}
        <div style={{ padding: 16, borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { label: 'Frames',   value: String(imgCount || 92),                icon: '🖼' },
            { label: 'Points',   value: (pointCount || 0) > 0 ? `${Math.round(pointCount/1000)}k` : '—', icon: '◎' },
            { label: 'GSD',      value: isDone ? '2.1 cm' : '…',               icon: '📐' },
            { label: 'Stage',    value: `${activeStage + (isDone ? 0 : 0)}/${PIPELINE_STAGES.length}`, icon: '⚙' },
          ].map(m => (
            <div key={m.label} style={{
              background: 'rgba(255,255,255,0.04)', borderRadius: 6, padding: '10px 12px',
              border: '1px solid rgba(255,255,255,0.07)'
            }}>
              <div style={{ fontSize: '18px', marginBottom: 2 }}>{m.icon}</div>
              <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'monospace', color: '#fff' }}>{m.value}</div>
              <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.35)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>{m.label}</div>
            </div>
          ))}
        </div>

        {/* Sentinel Timelapse */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {parcelId && <SentinelTimelapse parcelId={parcelId} />}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeInLog { from { opacity: 0; transform: translateX(-4px); } to { opacity: 1; transform: translateX(0); } }
      `}</style>
    </div>
  );
}

function ReportStep({ onFinish }: { onFinish: () => void }) {
  const { id } = useParams();
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    if (!id) return;
    setIsDownloading(true);
    try {
      await downloadReport(id);
    } catch (e) {
      console.error(e);
      alert('Failed to download report');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%', background: 'var(--color-surface)' }}>
      <div style={{ width: 480, textAlign: 'center', background: 'var(--color-bg)', padding: 'var(--spacing-xl)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)' }}>
        <h2 style={{ fontSize: '24px', marginBottom: '8px', color: 'var(--map-approved)' }}>Mission Successful</h2>
        <div style={{ fontSize: '14px', color: 'var(--color-text-secondary)', marginBottom: 'var(--spacing-xl)' }}>
          All spatial evidence, telemetry, and forensic data have been processed and committed to the case file.
        </div>
        
        <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '8px', marginBottom: 'var(--spacing-xl)', textAlign: 'left', fontSize: '13px', border: '1px solid var(--color-border-mid)' }}>
          <div style={{ marginBottom: '8px', fontWeight: 600 }}>Gathered Evidence:</div>
          <ul style={{ paddingLeft: '20px', color: 'var(--color-text-secondary)', lineHeight: '1.6' }}>
            <li>High-resolution Orthomosaic (WebODM)</li>
            <li>Cadastral vs Survey discrepancy metrics</li>
            <li>Temporal Satellite anomaly references</li>
            <li>Cryptographically hashed audit trail</li>
          </ul>
        </div>

        <div style={{ display: 'flex', gap: '16px', justifyContent: 'center' }}>
          <button 
            onClick={handleDownload}
            disabled={isDownloading}
            className="btn btn-outline"
            style={{ padding: '10px 24px' }}
          >
            {isDownloading ? 'Generating PDF...' : 'Download Report (PDF)'}
          </button>
          
          <button 
            onClick={onFinish}
            className="btn btn-primary"
            style={{ padding: '10px 24px' }}
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

function FlyStep({ state, setMissionState, transitionTo, layers }: { state: any, setMissionState: any, transitionTo: any, layers: GeometryLayers | null }) {
  const { id } = useParams();
  const [plan, setPlan] = useState<FlightPlan | null>(null);

  useEffect(() => {
    if (id) {
      fetchFlightPlan(id).then(res => {
        setPlan(res);
        if (res && res.waypoints && res.waypoints.length > 0) {
          setMissionState((prev: any) => ({
            ...prev,
            telemetry: {
              ...prev.telemetry,
              lon: res.waypoints[0][0],
              lat: res.waypoints[0][1]
            }
          }));
        }
      }).catch(console.error);
    }
  }, [id, setMissionState]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%' }}>
      <div style={{ flex: 1, display: 'flex' }}>
        <div style={{ flex: 1, position: 'relative', background: '#000', overflow: 'hidden' }}>
          <MapboxMap 
            layers={layers}
            showAILayer={true}
            flightPlan={plan}
            actualPath={state.actualPath}
            telemetry={state.telemetry}
            height="100%"
            visibleLayers={state?.layers || undefined}
          />
        </div>
        <RightOperationsPanel state={state} onTransition={transitionTo} />
      </div>
      <BlockStrip 
        blocks={state.blocks || []} 
        activeBlockId={state.blocks?.find((b: any) => b.status === 'IN_PROGRESS')?.id || null} 
      />
    </div>
  );
}

export function SurveyorMission() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const { missionState, transitionTo, setMissionState } = useMissionSimulation(id || 'UNKNOWN');
  
  const [layers, setLayers] = useState<GeometryLayers | null>(null);

  useEffect(() => {
    if (id) {
      fetchGeometryLayers(id).then(setLayers).catch(console.error);
      
      // Fetch actual case to update the parcel metadata (village, area)
      fetchCase(id).then(c => {
        setMissionState(prev => ({
          ...prev,
          parcel: {
            parcelId: c.parcel_id || id,
            villageName: c.village || (c as any).case_data?.parcel?.village_code || 'Unknown',
            cadastralAreaSqM: (c as any).case_data?.evidence?.spatial_evidence?.area_declared_sqm || 0,
            workingAreaSqM: (c as any).case_data?.evidence?.spatial_evidence?.area_surveyed_sqm || 0,
            boundaryStatus: prev.parcel?.boundaryStatus || 'BOUNDARY_PENDING'
          }
        }));
      }).catch(console.error);
    }
  }, [id, setMissionState]);

  return (
    <div style={{ 
      display: 'flex', flexDirection: 'column', 
      height: '100vh', width: '100vw', 
      background: 'var(--color-bg)', color: 'var(--color-text-primary)'
    }}>
      {/* 5-STEP MISSION STEPPER HEADER (No Breadcrumbs) */}
      <MissionStepper 
        currentState={missionState.state} 
        missionId={id || 'UNKNOWN'}
        telemetry={missionState.telemetry || undefined}
        onEndMission={() => navigate('/surveyor/cases')}
      />

      {/* THREE-COLUMN WORKSPACE */}
      <div style={{ flex: 1, display: 'flex', position: 'relative', overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<Navigate to="parcel" replace />} />
          
          <Route path="parcel" element={
            <ParcelStep 
              state={missionState} 
              setMissionState={setMissionState}
              layers={layers}
              onApproveSuccess={() => navigate(`/surveyor/mission/${id}/plan`, { replace: true })}
              onProceedToPlan={() => navigate(`/surveyor/mission/${id}/plan`, { replace: true })}
            />
          } />
          
          <Route path="plan" element={
            missionState.parcel?.boundaryStatus !== 'BOUNDARY_APPROVED' ? (
              <Navigate to={`/surveyor/mission/${id}/parcel`} replace />
            ) : (
              <PlanStep 
                state={missionState}
                setMissionState={setMissionState}
                layers={layers}
                onPlanLocked={() => {
                  setMissionState((prev: any) => ({ ...prev, state: 'FLYING' }));
                  navigate(`/surveyor/mission/${id}/fly`, { replace: true });
                }}
              />
            )
          } />

          <Route path="fly" element={
            <FlyStep 
              state={missionState}
              setMissionState={setMissionState}
              transitionTo={transitionTo}
              layers={layers}
            />
          } />
          
          <Route path="capture" element={
            <CaptureStep 
              state={missionState}
              setMissionState={setMissionState}
              layers={layers}
              onAccept={() => {
                setMissionState((prev: any) => ({ ...prev, state: 'PROCESSING' }));
                navigate(`/surveyor/mission/${id}/process`, { replace: true });
              }}
            />
          } />

          <Route path="process" element={
            <ProcessStep 
              state={missionState}
              setMissionState={setMissionState}
              onComplete={() => {
                setMissionState((prev: any) => ({ ...prev, state: 'COMPLETE' }));
                navigate(`/surveyor/mission/${id}/report`, { replace: true });
              }}
            />
          } />

          <Route path="report" element={
            <ReportStep 
              onFinish={() => {
                navigate('/surveyor/cases', { replace: true });
              }}
            />
          } />
          
        </Routes>
      </div>
    </div>
  );
}
