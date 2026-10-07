export type MissionState =
  | 'PARCEL_LOAD'
  | 'BOUNDARY_REVIEW'
  | 'BOUNDARY_APPROVED'
  | 'PLANNING'
  | 'READY'
  | 'FLYING'
  | 'CAPTURING'
  | 'QC'
  | 'PROCESSING'
  | 'COMPLETE';

export type BoundaryStatus = 'BOUNDARY_PENDING' | 'BOUNDARY_REVIEW' | 'BOUNDARY_APPROVED' | 'BOUNDARY_REJECTED';

export interface ParcelInfo {
  parcelId: string;
  villageName: string;
  cadastralAreaSqM: number;
  workingAreaSqM: number;
  boundaryStatus: BoundaryStatus;
}

export type LayerId = 
  | 'satellite' 
  | 'cadastral' 
  | 'ai_boundary' 
  | 'approved_boundary' 
  | 'grid' 
  | 'photo_points' 
  | 'actual_path' 
  | 'blocks' 
  | 'adjacent';

export interface LayerStyle {
  lineColor?: string;
  lineWidth?: number;
  opacity?: number;
  linePattern?: 'solid' | 'dashed' | 'dotted';
  fillColor?: string;
}

export interface MapLayer {
  id: LayerId;
  label: string;
  visible: boolean;
  style?: LayerStyle;
}

export type InferenceStatus = 'WAITING' | 'RUNNING' | 'READY' | 'FAILED';

export interface BoundaryInference {
  status: InferenceStatus;
  confidence: number | null;
  geometryRef: string | null;
  generatedAt: string | null;
}

export type BlockStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'NEEDS_REFLIGHT';

export interface SurveyBlock {
  id: string;
  status: BlockStatus;
  progress: number;
  photoCount: number;
  totalPhotoCount: number;
}

export interface CaptureTarget {
  blockId: string;
  pointId: string;
  distanceMeters: number | null;
  etaSeconds: number | null;
}

export type PositioningState = 'GPS_3D' | 'GPS_FLOAT' | 'NO_FIX' | 'DISCONNECTED';

export interface DroneTelemetry {
  lat: number;
  lon: number;
  altM: number | null;
  speedMps: number | null;
  headingDeg: number | null;
  batteryPercent: number | null;
  signalStrength: string | null;
  positioningState: PositioningState;
  timestamp: string;
}

export interface MissionViewState {
  state: MissionState;
  parcel: ParcelInfo | null;
  layers: MapLayer[];
  inference: BoundaryInference | null;
  blocks: SurveyBlock[];
  telemetry: DroneTelemetry | null;
  actualPath?: [number, number][];
  captureTarget: CaptureTarget | null;
  // Computed stats for right panel
  stats: {
    totalBlocks: number;
    coveragePercent: number;
    photoPoints: number;
    flightLines: number;
    estimatedTimeMin: number;
  } | null;
}
