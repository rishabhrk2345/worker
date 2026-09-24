'use client';
import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';
import { useSourceStore } from '../../../lib/store/sourceStore';

const PLATFORM_ICONS = [
  'youtube', 'reddit', 'x', 'linkedin',
  'instagram', 'facebook', 'threads', 'tiktok',
  'news', 'rss', 'forums', 'reviews', 'web', 'search', 'podcasts',
];

/** Individual source panel — color-coded by health */
function SourcePanel({ index, total, mode }: { index: number; total: number; mode: string }) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const angle = (index / total) * Math.PI * 2;
  const radius = 12;
  const x = Math.cos(angle) * radius;
  const z = Math.sin(angle) * radius;

  const color = mode === 'FAILED' ? '#ef4444'
    : mode === 'BACKOFF' ? '#f97316'
    : mode === 'RECOVERY' ? '#eab308'
    : '#4ade80';

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const mat = meshRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 0.3 + Math.sin(clock.getElapsedTime() * 2 + index) * 0.15;
    }
  });

  return (
    <mesh ref={meshRef} position={[x, 1.5, z]}>
      <boxGeometry args={[1.2, 2, 0.15]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.4}
        roughness={0.3}
        metalness={0.6}
      />
    </mesh>
  );
}

export function SourceObservatoryZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('SOURCE_OBSERVATORY');
  const sourcesMap = useSourceStore((s) => s.sources);
  const sources = useMemo(() => Array.from(sourcesMap.values()).slice(0, 15), [sourcesMap]);

  return (
    <ZonePlatform config={cfg}>
      {/* Render source panels arranged in circle */}
      {PLATFORM_ICONS.map((_, i) => {
        const source = sources[i];
        return (
          <SourcePanel
            key={i}
            index={i}
            total={PLATFORM_ICONS.length}
            mode={source?.mode ?? 'NORMAL'}
          />
        );
      })}
      <pointLight position={[0, 5, 0]} color="#818cf8" intensity={2} distance={25} />
      {children}
    </ZonePlatform>
  );
}
