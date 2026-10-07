import { useState, useEffect, useCallback } from 'react';
import type { MissionViewState, MissionState, DroneTelemetry } from '../types/mission';

// Helper to simulate drone movement along a simple path
const simulateMovement = (telemetry: DroneTelemetry): DroneTelemetry => {
  // Simple rectangular path simulation around the mock parcel
  let { lat, lon, headingDeg } = telemetry;
  const speed = 0.00002; // Roughly a few meters per tick

  if (headingDeg === 90) lon += speed;
  else if (headingDeg === 180) lat -= speed;
  else if (headingDeg === 270) lon -= speed;
  else if (headingDeg === 0) lat += speed;

  // Turn corners roughly to simulate lawnmower
  if (lon > 79.9875 && headingDeg === 90) headingDeg = 180;
  if (lat < 16.3055 && headingDeg === 180) headingDeg = 270;
  if (lon < 79.9860 && headingDeg === 270) headingDeg = 0;
  if (lat > 16.3065 && headingDeg === 0) headingDeg = 90;

  // Add jitter for realism (Task 6)
  const latJitter = (Math.random() - 0.5) * 0.000002;
  const lonJitter = (Math.random() - 0.5) * 0.000002;
  const headingFlutter = (Math.random() - 0.5) * 4; // +/- 2 degrees flutter

  return {
    ...telemetry,
    lat: lat + latJitter,
    lon: lon + lonJitter,
    headingDeg: ((headingDeg || 0) + headingFlutter + 360) % 360,
    batteryPercent: Math.max(0, (telemetry.batteryPercent || 100) - 0.05), // Drain battery
    signalStrength: Math.random() > 0.95 ? 'Weak' : 'Strong', // Occasionally drop signal
    timestamp: new Date().toISOString()
  };
};

const createInitialState = (missionId: string): MissionViewState => ({
  state: 'BOUNDARY_REVIEW',
  parcel: {
    parcelId: missionId,
    villageName: 'Rangapur',
    cadastralAreaSqM: 40500,
    workingAreaSqM: 41200,
    boundaryStatus: 'BOUNDARY_PENDING'
  },
  layers: [
    { id: 'satellite', label: 'Satellite Imagery', visible: true },
    { id: 'cadastral', label: 'Cadastral Map (Old)', visible: true },
    { id: 'ai_boundary', label: 'Adjusted Boundary (U-Net)', visible: true },
    { id: 'grid', label: 'Grid Plan (Lawnmower)', visible: true },
    { id: 'photo_points', label: 'Photo Points (Planned)', visible: true },
    { id: 'actual_path', label: 'Flight Path (Actual)', visible: true },
    { id: 'blocks', label: 'Parcel Split Blocks', visible: true },
    { id: 'adjacent', label: 'Adjacent Parcels', visible: false }
  ],
  inference: {
    status: 'READY',
    confidence: 0.87,
    geometryRef: 'geojson-ref',
    generatedAt: new Date().toISOString()
  },
  blocks: [
    { id: 'B1', status: 'COMPLETED', progress: 100, photoCount: 12, totalPhotoCount: 12 },
    { id: 'B2', status: 'COMPLETED', progress: 100, photoCount: 14, totalPhotoCount: 14 },
    { id: 'B3', status: 'IN_PROGRESS', progress: 60, photoCount: 6, totalPhotoCount: 10 },
    { id: 'B4', status: 'PENDING', progress: 0, photoCount: 0, totalPhotoCount: 8 },
    { id: 'B5', status: 'PENDING', progress: 0, photoCount: 0, totalPhotoCount: 10 }
  ],
  telemetry: {
    lat: 16.306521,
    lon: 79.986732,
    altM: 62.3,
    speedMps: 4.8,
    headingDeg: 90,
    batteryPercent: 78,
    signalStrength: 'Strong',
    positioningState: 'GPS_3D',
    timestamp: new Date().toISOString()
  },
  captureTarget: {
    blockId: 'B3',
    pointId: 'B3-3',
    distanceMeters: 18,
    etaSeconds: 6
  },
  stats: {
    totalBlocks: 9,
    coveragePercent: 98,
    photoPoints: 54,
    flightLines: 6,
    estimatedTimeMin: 12
  }
});

export function useMissionSimulation(missionId: string) {
  const [missionState, setMissionState] = useState<MissionViewState>(() => createInitialState(missionId));

  // Expose a transition function so the UI can trigger state changes (e.g. User clicks "Start Mission")
  const transitionTo = useCallback((newState: MissionState) => {
    setMissionState(prev => ({ ...prev, state: newState }));
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    if (missionState.state === 'FLYING' || missionState.state === 'CAPTURING') {
      interval = setInterval(() => {
        setMissionState(prev => {
          if (!prev.telemetry) return prev;

          const updatedTelemetry = simulateMovement(prev.telemetry);
          
          const newActualPath = [...(prev.actualPath || []), [updatedTelemetry.lon, updatedTelemetry.lat] as [number, number]];
          
          // Simulate block progress
          let newBlocks = [...(prev.blocks || [])];
          let newStats = prev.stats;
          let newCaptureTarget = prev.captureTarget;

          // Find current in-progress block
          const activeBlockIdx = newBlocks.findIndex(b => b.status === 'IN_PROGRESS');
          if (activeBlockIdx !== -1) {
            const block = { ...newBlocks[activeBlockIdx] };
            block.progress += 2; // +2% per tick
            
            if (block.progress >= 100) {
              block.progress = 100;
              block.status = 'COMPLETED';
              block.photoCount = block.totalPhotoCount;
              
              // Start next block if available
              if (activeBlockIdx + 1 < newBlocks.length) {
                newBlocks[activeBlockIdx + 1] = { 
                  ...newBlocks[activeBlockIdx + 1], 
                  status: 'IN_PROGRESS' 
                };
                
                // Update capture target
                if (newCaptureTarget) {
                  newCaptureTarget = {
                    ...newCaptureTarget,
                    blockId: newBlocks[activeBlockIdx + 1].id,
                    pointId: `${newBlocks[activeBlockIdx + 1].id}-1`,
                    distanceMeters: 45,
                    etaSeconds: 15
                  };
                }
              } else {
                // If all blocks done, automatically transition to QC / PROCESSING
                setTimeout(() => transitionTo('QC'), 1000);
              }
            } else {
               // Update distance/eta randomly
               if (newCaptureTarget) {
                 newCaptureTarget = {
                   ...newCaptureTarget,
                   distanceMeters: Math.max(0, (newCaptureTarget.distanceMeters || 0) - 0.5),
                   etaSeconds: Math.max(0, (newCaptureTarget.etaSeconds || 0) - 0.2)
                 };
               }
            }
            newBlocks[activeBlockIdx] = block;

            // Update stats
            if (newStats) {
              const completedCount = newBlocks.filter(b => b.status === 'COMPLETED').length;
              newStats = {
                ...newStats,
                coveragePercent: Math.min(100, Math.floor((completedCount / newBlocks.length) * 100) + Math.floor(block.progress / newBlocks.length))
              };
            }
          }

          return {
            ...prev,
            telemetry: updatedTelemetry,
            actualPath: newActualPath,
            blocks: newBlocks,
            stats: newStats,
            captureTarget: newCaptureTarget
          };
        });
      }, 1000); // Tick every 1 second
    } else if (missionState.state === 'QC') {
      // Fast forward QC to PROCESSING
      const timeout = setTimeout(() => transitionTo('PROCESSING'), 3000);
      return () => clearTimeout(timeout);
    } else if (missionState.state === 'PROCESSING') {
      // Fast forward PROCESSING to COMPLETE
      const timeout = setTimeout(() => transitionTo('COMPLETE'), 5000);
      return () => clearTimeout(timeout);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [missionState.state, transitionTo]);

  return { missionState, transitionTo, setMissionState };
}
