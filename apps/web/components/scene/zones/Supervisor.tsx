'use client';
/**
 * Supervisor HQ — Elevated central platform, holographic mission board.
 */
import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function SupervisorZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('SUPERVISOR');
  const holoRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    if (holoRef.current) {
      holoRef.current.rotation.y = clock.getElapsedTime() * 0.4;
      const mat = holoRef.current.material as THREE.MeshStandardMaterial;
      mat.opacity = 0.4 + Math.sin(clock.getElapsedTime()) * 0.1;
    }
  });

  return (
    <ZonePlatform config={cfg}>
      {/* Holographic mission orb */}
      <mesh ref={holoRef} position={[0, 3, 0]}>
        <icosahedronGeometry args={[2.5, 1]} />
        <meshStandardMaterial
          color="#3b82f6"
          emissive="#60a5fa"
          emissiveIntensity={0.8}
          transparent
          opacity={0.45}
          wireframe
        />
      </mesh>
      {/* Central glow point */}
      <pointLight position={[0, 4, 0]} color="#3b82f6" intensity={3} distance={20} />
      {children}
    </ZonePlatform>
  );
}
