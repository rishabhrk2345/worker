'use client';
/**
 * components/scene/WorkerLayer.tsx
 *
 * Renders all workers with LOD strategy (ADR-009):
 * - Workers within 40 world units of camera → full Worker3D (LOD-0)
 * - Workers 40–80 units away → simplified Worker3D (LOD-1)
 * - Workers >80 units → instanced simple geometry (zone heat-map dots)
 * - Workers in COMPLETED or not in active zone → skipped
 *
 * Zone-level aggregate indicators show logical worker density.
 */

import { useRef, useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { InstancedMesh } from 'three';
import * as THREE from 'three';

import { useWorkerStore } from '../../lib/store/workerStore';
import { Worker3D } from './Worker3D';
import { getStationPosition } from './ZoneRegistry';

const DUMMY = new THREE.Object3D();
const LOD_FULL_DIST = 40;
const LOD_SIMPLE_DIST = 80;

export function WorkerLayer() {
  const workersMap = useWorkerStore((s) => s.workers);
  const workers = useMemo(() => Array.from(workersMap.values()), [workersMap]);
  const { camera } = useThree();

  // Separate workers into LOD buckets
  const { fullWorkers, simpleWorkers, instancedWorkers } = useMemo(() => {
    const full: typeof workers = [];
    const simple: typeof workers = [];
    const instanced: typeof workers = [];

    for (const w of workers) {
      if (w.status === 'COMPLETED') continue;
      const pos = getStationPosition(w.logicalZone, w.logicalStation);
      const dist = camera.position.distanceTo(pos);
      if (dist < LOD_FULL_DIST) full.push(w);
      else if (dist < LOD_SIMPLE_DIST) simple.push(w);
      else instanced.push(w);
    }
    return { fullWorkers: full, simpleWorkers: simple, instancedWorkers: instanced };
  // Recalculate each frame via useFrame, not useMemo (camera changes every frame)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workers]);

  return (
    <>
      {/* Full detail workers */}
      {fullWorkers.map((w) => (
        <Worker3D key={w.id} worker={w} lod={0} />
      ))}

      {/* Simplified workers */}
      {simpleWorkers.map((w) => (
        <Worker3D key={w.id} worker={w} lod={1} />
      ))}

      {/* Far-away workers as instanced dots */}
      {instancedWorkers.length > 0 && (
        <InstancedWorkers workers={instancedWorkers} />
      )}
    </>
  );
}

/** Renders distant workers as bright instanced spheres */
function InstancedWorkers({ workers }: { workers: ReturnType<typeof useWorkerStore.getState>['workers'] extends Map<string, infer T> ? T[] : never[] }) {
  const meshRef = useRef<InstancedMesh>(null!);

  useFrame(() => {
    if (!meshRef.current || workers.length === 0) return;
    workers.forEach((w, i) => {
      const pos = getStationPosition(w.logicalZone, w.logicalStation);
      DUMMY.position.set(pos.x, pos.y + 1, pos.z);
      DUMMY.scale.setScalar(0.4);
      DUMMY.updateMatrix();
      meshRef.current.setMatrixAt(i, DUMMY.matrix);
    });
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  if (workers.length === 0) return null;

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, workers.length]}
      castShadow={false}
    >
      <sphereGeometry args={[0.5, 6, 6]} />
      <meshStandardMaterial
        color="#3b82f6"
        emissive="#60a5fa"
        emissiveIntensity={0.8}
      />
    </instancedMesh>
  );
}
