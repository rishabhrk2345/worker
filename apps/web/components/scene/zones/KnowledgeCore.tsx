'use client';
import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

/** Orbital node for the knowledge graph preview */
function OrbitNode({ radius, speed, offset, color }: {
  radius: number; speed: number; offset: number; color: string;
}) {
  const ref = useRef<THREE.Mesh>(null!);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * speed + offset;
    if (ref.current) {
      ref.current.position.x = Math.cos(t) * radius;
      ref.current.position.z = Math.sin(t) * radius;
    }
  });
  return (
    <mesh ref={ref} position={[radius, 2, 0]}>
      <sphereGeometry args={[0.4, 8, 8]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.8} />
    </mesh>
  );
}

export function KnowledgeCoreZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('KNOWLEDGE_CORE');

  return (
    <ZonePlatform config={cfg}>
      {/* Central core sphere */}
      <mesh position={[0, 2.5, 0]}>
        <sphereGeometry args={[2, 16, 16]} />
        <meshStandardMaterial
          color="#0ea5e9"
          emissive="#38bdf8"
          emissiveIntensity={0.4}
          wireframe
          transparent
          opacity={0.5}
        />
      </mesh>
      {/* Orbiting knowledge nodes */}
      <OrbitNode radius={5} speed={0.4} offset={0} color="#38bdf8" />
      <OrbitNode radius={5} speed={0.4} offset={2.1} color="#818cf8" />
      <OrbitNode radius={5} speed={0.4} offset={4.2} color="#34d399" />
      <OrbitNode radius={8} speed={0.25} offset={1} color="#f472b6" />
      <OrbitNode radius={8} speed={0.25} offset={3.5} color="#fbbf24" />
      <pointLight position={[0, 3, 0]} color="#38bdf8" intensity={3} distance={20} />
      {children}
    </ZonePlatform>
  );
}
