'use client';
/**
 * components/scene/cameras/CameraController.tsx
 *
 * Reads UIStore.cameraMode and smoothly transitions the Three.js camera
 * to the appropriate position/target.
 *
 * Modes:
 *   HQ              — wide overhead shot of the full command center
 *   WORKER_FOLLOW   — close follow on selected worker
 *   MISSION         — medium shot on Supervisor zone
 *   SOURCE          — Source Observatory close-up
 *   PRODUCT         — Product Campus angled view
 *   COMPETITOR      — Competitor War Room close-up
 *   KNOWLEDGE       — Knowledge Core close-up
 *   OPERATIONS      — Operations Center
 *   REPLAY          — same as HQ (replay controller handles actual framing)
 */

import { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

import { useUIStore } from '../../../lib/store/uiStore';
import { useWorkerStore } from '../../../lib/store/workerStore';
import { getStationPosition, getZoneConfig } from '../ZoneRegistry';

interface CameraTarget {
  position: THREE.Vector3;
  lookAt: THREE.Vector3;
  enableOrbit: boolean;
}

function getModeTarget(
  mode: ReturnType<typeof useUIStore.getState>['cameraMode'],
  selectedWorkerId: string | null,
  workers: ReturnType<typeof useWorkerStore.getState>['workers']
): CameraTarget {
  switch (mode) {
    case 'HQ':
    case 'REPLAY':
      return {
        position: new THREE.Vector3(0, 90, 110),
        lookAt: new THREE.Vector3(0, 0, 0),
        enableOrbit: true,
      };

    case 'WORKER_FOLLOW': {
      const w = selectedWorkerId ? workers.get(selectedWorkerId) : null;
      if (w) {
        const pos = getStationPosition(w.logicalZone, w.logicalStation);
        return {
          position: new THREE.Vector3(pos.x + 8, pos.y + 12, pos.z + 10),
          lookAt: new THREE.Vector3(pos.x, pos.y + 2, pos.z),
          enableOrbit: false,
        };
      }
      return getModeTarget('HQ', null, workers);
    }

    case 'MISSION': {
      const cfg = getZoneConfig('SUPERVISOR');
      return {
        position: new THREE.Vector3(cfg.center.x + 20, cfg.center.y + 25, cfg.center.z + 25),
        lookAt: cfg.center.clone(),
        enableOrbit: false,
      };
    }

    case 'SOURCE': {
      const cfg = getZoneConfig('SOURCE_OBSERVATORY');
      return {
        position: new THREE.Vector3(cfg.center.x + 15, cfg.center.y + 20, cfg.center.z + 25),
        lookAt: cfg.center.clone(),
        enableOrbit: false,
      };
    }

    case 'PRODUCT': {
      const cfg = getZoneConfig('PRODUCT_CAMPUS');
      return {
        position: new THREE.Vector3(cfg.center.x, cfg.center.y + 30, cfg.center.z + 35),
        lookAt: cfg.center.clone(),
        enableOrbit: false,
      };
    }

    case 'COMPETITOR': {
      const cfg = getZoneConfig('COMPETITOR_WAR_ROOM');
      return {
        position: new THREE.Vector3(cfg.center.x, cfg.center.y + 25, cfg.center.z + 30),
        lookAt: cfg.center.clone(),
        enableOrbit: false,
      };
    }

    case 'KNOWLEDGE': {
      const cfg = getZoneConfig('KNOWLEDGE_CORE');
      return {
        position: new THREE.Vector3(cfg.center.x + 10, cfg.center.y + 20, cfg.center.z + 22),
        lookAt: cfg.center.clone(),
        enableOrbit: false,
      };
    }

    case 'OPERATIONS': {
      const cfg = getZoneConfig('OPERATIONS');
      return {
        position: new THREE.Vector3(cfg.center.x + 10, cfg.center.y + 18, cfg.center.z + 20),
        lookAt: cfg.center.clone(),
        enableOrbit: false,
      };
    }

    default:
      return {
        position: new THREE.Vector3(0, 90, 110),
        lookAt: new THREE.Vector3(0, 0, 0),
        enableOrbit: true,
      };
  }
}

const LERP_SPEED = 1.5;

export function CameraController() {
  const { camera } = useThree();
  const cameraMode = useUIStore((s) => s.cameraMode);
  const selectedWorkerId = useUIStore((s) => s.selectedWorkerId);
  const workers = useWorkerStore((s) => s.workers);

  const currentLookAt = useRef(new THREE.Vector3(0, 0, 0));

  useFrame((_, delta) => {
    const target = getModeTarget(cameraMode, selectedWorkerId, workers);
    camera.position.lerp(target.position, delta * LERP_SPEED);
    currentLookAt.current.lerp(target.lookAt, delta * LERP_SPEED);
    camera.lookAt(currentLookAt.current);
  });

  // Orbit controls only in HQ/REPLAY mode
  const enableOrbit =
    cameraMode === 'HQ' || cameraMode === 'REPLAY';

  return enableOrbit ? (
    <OrbitControls
      target={[0, 0, 0]}
      minDistance={20}
      maxDistance={250}
      minPolarAngle={0.1}
      maxPolarAngle={Math.PI / 2.1}
      enablePan={true}
      makeDefault
    />
  ) : null;
}
