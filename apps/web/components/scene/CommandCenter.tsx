'use client';
/**
 * components/scene/CommandCenter.tsx
 *
 * Root R3F canvas for the AI Marketing Intelligence OS command center.
 * Renders all 12 zones, workers (Phase 7d), data packages, and cameras.
 *
 * Performance config:
 * - shadows enabled, soft shadows
 * - antialias via MSAA
 * - pixelRatio capped at 1.5
 * - LOD handled per-worker (Phase 7d)
 */

import { Suspense, useCallback, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { AdaptiveDpr, AdaptiveEvents, Preload, Stats } from '@react-three/drei';
import * as THREE from 'three';

import { SceneEnvironment } from './Environment';
import { SupervisorZone } from './zones/Supervisor';
import { DiscoveryCityZone } from './zones/DiscoveryCity';
import { SourceObservatoryZone } from './zones/SourceObservatory';
import { ResearchLabZone } from './zones/ResearchLab';
import { IntelligenceLabZone } from './zones/IntelligenceLab';
import { ProductCampusZone } from './zones/ProductCampus';
import { CompetitorWarRoomZone } from './zones/CompetitorWarRoom';
import { ActionCenterZone } from './zones/ActionCenter';
import { KnowledgeCoreZone } from './zones/KnowledgeCore';
import { MemoryLearningZone } from './zones/MemoryLearning';
import { OperationsZone } from './zones/Operations';
import { InvestigationRoomZone } from './zones/InvestigationRoom';
import { WorkerLayer } from './WorkerLayer';
import { DataPackageLayer } from './DataPackageLayer';
import { CameraController } from './cameras/CameraController';

/** Fallback shown while the scene suspends */
function LoadingFallback() {
  return null;
}

interface Props {
  showStats?: boolean;
}

export function CommandCenter({ showStats = false }: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 1.5]}
      gl={{
        antialias: true,
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 0.8,
        outputColorSpace: THREE.SRGBColorSpace,
      }}
      camera={{
        fov: 55,
        near: 0.5,
        far: 500,
        position: [0, 80, 100],
      }}
      style={{ width: '100%', height: '100%' }}
    >
      <Suspense fallback={<LoadingFallback />}>
        {/* Performance helpers */}
        <AdaptiveDpr pixelated />
        <AdaptiveEvents />

        {/* Scene lighting and environment */}
        <SceneEnvironment />

        {/* Camera controller — driven by UIStore cameraMode */}
        <CameraController />

        {/* 12 Zone Platforms */}
        <SupervisorZone />
        <DiscoveryCityZone />
        <SourceObservatoryZone />
        <ResearchLabZone />
        <IntelligenceLabZone />
        <ProductCampusZone />
        <CompetitorWarRoomZone />
        <ActionCenterZone />
        <KnowledgeCoreZone />
        <MemoryLearningZone />
        <OperationsZone />
        <InvestigationRoomZone />

        {/* Worker instances — LOD-aware, event-driven */}
        <WorkerLayer />

        {/* Data package animations */}
        <DataPackageLayer />

        {/* Preload all assets */}
        <Preload all />

        {showStats && <Stats />}
      </Suspense>
    </Canvas>
  );
}
