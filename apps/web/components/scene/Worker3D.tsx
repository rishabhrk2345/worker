'use client';
/**
 * components/scene/Worker3D.tsx
 *
 * Procedural humanoid robot rendered in Three.js geometry.
 * No external GLTF — all shapes are primitive box/cylinder/sphere combos.
 *
 * Structure:
 *   head (sphere) + neck (cylinder)
 *   torso (box)
 *   left arm + right arm (cylinders)
 *   left leg + right leg (cylinders)
 *   status light (sphere, emissive by state)
 *   workstation console (flat box in front)
 *
 * Animations driven by XState context.animationKey:
 *   - idle_workstation:     slow bob
 *   - holographic_graph:    head rotate + arm raise
 *   - browser_interaction:  arm forward oscillate
 *   - data_package_transfer:lean forward
 *   - approval_pending_light: pulse glow
 *   - error_state / warning_red: tremble
 *   - success_state:        jump
 */

import { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { useMachine } from '@xstate/react';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

import { workerMachine, WorkerContext } from './WorkerStateMachine';
import { WorkerSnapshot } from '../../lib/store/workerStore';
import { useUIStore } from '../../lib/store/uiStore';
import { getStationPosition } from './ZoneRegistry';
import { WorkerState, LogicalZone } from '../../lib/types/generated/enums';

interface Props {
  worker: WorkerSnapshot;
  /** LOD level: 0=full, 1=simplified, 2=hidden (handled by WorkerLayer) */
  lod?: 0 | 1;
}

const BODY_SCALE = 0.7;

export function Worker3D({ worker, lod = 0 }: Props) {
  const groupRef = useRef<THREE.Group>(null!);
  const headRef = useRef<THREE.Mesh>(null!);
  const torsoRef = useRef<THREE.Group>(null!);
  const leftArmRef = useRef<THREE.Mesh>(null!);
  const rightArmRef = useRef<THREE.Mesh>(null!);
  const statusLightRef = useRef<THREE.Mesh>(null!);
  const glowRef = useRef<THREE.PointLight>(null!);

  const selectedWorkerId = useUIStore((s) => s.selectedWorkerId);
  const selectWorker = useUIStore((s) => s.selectWorker);
  const isSelected = selectedWorkerId === worker.id;

  const initialContext: WorkerContext = useMemo(() => ({
    workerId: worker.id,
    currentState: worker.status,
    animationKey: 'idle_workstation',
    logicalZone: worker.logicalZone,
    logicalStation: worker.logicalStation,
    currentUrl: worker.currentUrl ?? null,
    glowIntensity: 0.6,
    statusColor: '#64748b',
  }), [worker.id]);

  const [state, send] = useMachine(workerMachine, { input: initialContext });
  const ctx = state.context;

  // Sync store state → XState machine
  useEffect(() => {
    send({
      type: 'STATE_CHANGED',
      newState: worker.status,
      logicalZone: worker.logicalZone as LogicalZone,
      logicalStation: worker.logicalStation,
      currentUrl: worker.currentUrl ?? null,
    });
  }, [worker.status, worker.logicalZone, worker.logicalStation, worker.currentUrl, send]);

  // Sync selection state
  useEffect(() => {
    send({ type: isSelected ? 'SELECTED' : 'DESELECTED' });
  }, [isSelected, send]);

  // Target world position from zone/station
  const targetPos = useMemo(
    () => getStationPosition(ctx.logicalZone, ctx.logicalStation),
    [ctx.logicalZone, ctx.logicalStation]
  );

  const animTime = useRef(0);

  useFrame(({ clock }, delta) => {
    animTime.current += delta;
    const t = animTime.current;
    const key = ctx.animationKey;

    // Smooth-lerp position toward target
    if (groupRef.current) {
      groupRef.current.position.lerp(
        new THREE.Vector3(targetPos.x, targetPos.y, targetPos.z),
        delta * 1.5
      );
    }

    // Update status light color and glow
    if (statusLightRef.current) {
      const mat = statusLightRef.current.material as THREE.MeshStandardMaterial;
      mat.emissive.set(ctx.statusColor);
      mat.emissiveIntensity = 0.8 + Math.sin(t * 3) * 0.3;
    }
    if (glowRef.current) {
      glowRef.current.color.set(ctx.statusColor);
      glowRef.current.intensity = ctx.glowIntensity + Math.sin(t * 2) * 0.2;
    }

    if (lod !== 0) return; // skip detailed animation for LOD-1

    // Animation routines per key
    if (headRef.current) {
      switch (key) {
        case 'planning_hologram':
        case 'holographic_graph':
          headRef.current.rotation.y = Math.sin(t * 1.5) * 0.6;
          break;
        case 'error_state':
        case 'warning_red':
          headRef.current.rotation.z = Math.sin(t * 15) * 0.05; // tremble
          break;
        case 'success_state':
          headRef.current.position.y = 3.1 + Math.abs(Math.sin(t * 4)) * 0.4;
          break;
        default:
          headRef.current.rotation.y = Math.sin(t * 0.5) * 0.1;
          headRef.current.position.y = 3.1;
      }
    }

    if (torsoRef.current) {
      switch (key) {
        case 'idle_workstation':
          torsoRef.current.position.y = Math.sin(t * 0.8) * 0.04;
          break;
        case 'data_package_transfer':
          torsoRef.current.rotation.z = Math.sin(t * 2) * 0.05;
          break;
        default:
          torsoRef.current.position.y = 0;
      }
    }

    if (leftArmRef.current && rightArmRef.current) {
      switch (key) {
        case 'browser_interaction':
        case 'query_console':
        case 'writing_interface':
          leftArmRef.current.rotation.x = Math.sin(t * 3) * 0.4 - 0.5;
          rightArmRef.current.rotation.x = Math.sin(t * 3 + Math.PI) * 0.4 - 0.5;
          break;
        case 'evidence_comparison':
        case 'multi_document_float':
          leftArmRef.current.rotation.x = -0.6 + Math.sin(t * 1.5) * 0.15;
          rightArmRef.current.rotation.x = -0.6 + Math.sin(t * 1.5 + 1) * 0.15;
          break;
        default:
          leftArmRef.current.rotation.x = Math.sin(t * 0.5) * 0.05;
          rightArmRef.current.rotation.x = Math.sin(t * 0.5 + Math.PI) * 0.05;
      }
    }
  });

  const color = ctx.statusColor;
  const s = BODY_SCALE;

  if (lod === 1) {
    // Simplified LOD-1: just a colored capsule + status light
    return (
      <group ref={groupRef} position={[targetPos.x, targetPos.y, targetPos.z]}>
        <mesh>
          <capsuleGeometry args={[0.4 * s, 1.5 * s, 4, 8]} />
          <meshStandardMaterial color={color} roughness={0.5} />
        </mesh>
        <mesh ref={statusLightRef} position={[0, 1.4 * s, 0]}>
          <sphereGeometry args={[0.15 * s, 6, 6]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.8}
          />
        </mesh>
        <pointLight ref={glowRef} color={color} intensity={ctx.glowIntensity} distance={5} />
      </group>
    );
  }

  return (
    <group
      ref={groupRef}
      position={[targetPos.x, targetPos.y, targetPos.z]}
      onClick={(e) => { e.stopPropagation(); selectWorker(isSelected ? null : worker.id); }}
    >
      {/* Torso group (body + arms) */}
      <group ref={torsoRef}>
        {/* Torso */}
        <mesh position={[0, 1.4 * s, 0]} castShadow>
          <boxGeometry args={[0.7 * s, 0.9 * s, 0.45 * s]} />
          <meshStandardMaterial color="#1e293b" roughness={0.4} metalness={0.6} />
        </mesh>
        {/* Chest accent panel */}
        <mesh position={[0, 1.45 * s, 0.23 * s]}>
          <boxGeometry args={[0.4 * s, 0.4 * s, 0.02]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.6}
            roughness={0.2}
          />
        </mesh>
        {/* Left arm */}
        <mesh ref={leftArmRef} position={[-0.55 * s, 1.3 * s, 0]}>
          <capsuleGeometry args={[0.12 * s, 0.6 * s, 4, 8]} />
          <meshStandardMaterial color="#0f172a" roughness={0.5} metalness={0.5} />
        </mesh>
        {/* Right arm */}
        <mesh ref={rightArmRef} position={[0.55 * s, 1.3 * s, 0]}>
          <capsuleGeometry args={[0.12 * s, 0.6 * s, 4, 8]} />
          <meshStandardMaterial color="#0f172a" roughness={0.5} metalness={0.5} />
        </mesh>
      </group>

      {/* Neck */}
      <mesh position={[0, 2.0 * s, 0]}>
        <cylinderGeometry args={[0.1 * s, 0.1 * s, 0.25 * s, 8]} />
        <meshStandardMaterial color="#0f172a" roughness={0.4} metalness={0.7} />
      </mesh>

      {/* Head */}
      <mesh ref={headRef} position={[0, 2.4 * s, 0]} castShadow>
        <boxGeometry args={[0.45 * s, 0.45 * s, 0.45 * s]} />
        <meshStandardMaterial color="#1e293b" roughness={0.3} metalness={0.7} />
      </mesh>
      {/* Visor */}
      <mesh position={[0, 2.42 * s, 0.23 * s]}>
        <boxGeometry args={[0.3 * s, 0.12 * s, 0.02]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1.2}
          transparent
          opacity={0.85}
        />
      </mesh>

      {/* Status light on top of head */}
      <mesh ref={statusLightRef} position={[0, 2.72 * s, 0]}>
        <sphereGeometry args={[0.1 * s, 8, 8]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.9}
        />
      </mesh>

      {/* Left leg */}
      <mesh position={[-0.2 * s, 0.55 * s, 0]}>
        <capsuleGeometry args={[0.14 * s, 0.7 * s, 4, 8]} />
        <meshStandardMaterial color="#0f172a" roughness={0.5} metalness={0.5} />
      </mesh>
      {/* Right leg */}
      <mesh position={[0.2 * s, 0.55 * s, 0]}>
        <capsuleGeometry args={[0.14 * s, 0.7 * s, 4, 8]} />
        <meshStandardMaterial color="#0f172a" roughness={0.5} metalness={0.5} />
      </mesh>

      {/* Workstation console in front */}
      <mesh position={[0, 1.0 * s, 0.55 * s]}>
        <boxGeometry args={[0.5 * s, 0.3 * s, 0.05]} />
        <meshStandardMaterial
          color="#0ea5e9"
          emissive="#0ea5e9"
          emissiveIntensity={0.4}
          transparent
          opacity={0.7}
        />
      </mesh>

      {/* Dynamic point light */}
      <pointLight
        ref={glowRef}
        color={color}
        intensity={ctx.glowIntensity}
        distance={8}
        decay={2}
      />

      {/* Hover label for selected worker */}
      {isSelected && (
        <Html
          position={[0, 3.2 * s, 0]}
          center
          style={{ pointerEvents: 'none' }}
        >
          <div style={{
            background: 'rgba(9,9,11,0.9)',
            border: `1px solid ${color}`,
            borderRadius: 4,
            padding: '2px 6px',
            fontSize: 11,
            color: color,
            whiteSpace: 'nowrap',
            fontFamily: 'monospace',
          }}>
            {worker.name} · {worker.status}
          </div>
        </Html>
      )}
    </group>
  );
}
