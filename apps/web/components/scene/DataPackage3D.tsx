'use client';
/**
 * components/scene/DataPackage3D.tsx
 *
 * Animated glowing orb that travels between two zones/workers.
 * Path follows pre-authored splines between zone centers (ADR-003/M-3).
 * The orb spawns from a worker.task_transferred event.
 */

import { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { getZoneConfig } from './ZoneRegistry';
import { LogicalZone } from '../../lib/types/generated/enums';
import { WorkerTaskTransferredPayload } from '../../lib/types/generated/events';

interface Props {
  id: string;
  fromZone: LogicalZone;
  toZone: LogicalZone;
  label?: string;
  color?: string;
  onComplete: (id: string) => void;
}

const TRAVEL_DURATION = 2.5; // seconds

export function DataPackage3D({ id, fromZone, toZone, label, color = '#60a5fa', onComplete }: Props) {
  const groupRef = useRef<THREE.Group>(null!);
  const trailRef = useRef<THREE.Mesh[]>([]);
  const glowRef = useRef<THREE.PointLight>(null!);
  const progressRef = useRef(0);

  const from = getZoneConfig(fromZone).center;
  const to = getZoneConfig(toZone).center;

  // Quadratic bezier: arc up through the air between zones
  const curve = useMemo(() => {
    const mid = new THREE.Vector3(
      (from.x + to.x) / 2,
      Math.max(from.y, to.y) + 25, // arc height
      (from.z + to.z) / 2
    );
    return new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(from.x, from.y + 2, from.z),
      mid,
      new THREE.Vector3(to.x, to.y + 2, to.z)
    );
  }, [from, to]);

  useFrame((_, delta) => {
    progressRef.current = Math.min(progressRef.current + delta / TRAVEL_DURATION, 1);
    const t = progressRef.current;

    if (groupRef.current) {
      const pos = curve.getPoint(t);
      groupRef.current.position.copy(pos);

      // Rotate orb
      groupRef.current.rotation.y += delta * 2;
      groupRef.current.rotation.x += delta * 1.3;
    }

    if (glowRef.current) {
      glowRef.current.intensity = 2 + Math.sin(progressRef.current * Math.PI * 8) * 0.5;
    }

    if (t >= 1) {
      onComplete(id);
    }
  });

  return (
    <group ref={groupRef} position={[from.x, from.y + 2, from.z]}>
      {/* Core orb */}
      <mesh>
        <icosahedronGeometry args={[0.5, 2]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1.5}
          transparent
          opacity={0.9}
          wireframe={false}
        />
      </mesh>
      {/* Outer wireframe shell */}
      <mesh scale={1.4}>
        <icosahedronGeometry args={[0.5, 1]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.4}
          transparent
          opacity={0.3}
          wireframe
        />
      </mesh>
      {/* Dynamic glow */}
      <pointLight ref={glowRef} color={color} intensity={2} distance={12} decay={2} />

      {/* Label */}
      {label && (
        <Html center position={[0, 1.2, 0]} style={{ pointerEvents: 'none' }}>
          <div style={{
            background: 'rgba(9,9,11,0.85)',
            border: `1px solid ${color}`,
            borderRadius: 3,
            padding: '1px 5px',
            fontSize: 10,
            color,
            whiteSpace: 'nowrap',
            fontFamily: 'monospace',
          }}>
            {label}
          </div>
        </Html>
      )}
    </group>
  );
}
