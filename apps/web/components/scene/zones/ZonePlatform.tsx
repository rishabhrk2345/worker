'use client';
/**
 * components/scene/zones/ZonePlatform.tsx
 *
 * Shared zone platform primitive used by all 12 zones.
 * Renders: raised floor slab + glowing perimeter edge + label.
 */

import { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text, Billboard } from '@react-three/drei';
import * as THREE from 'three';
import { ZoneConfig } from '../ZoneRegistry';
import { LogicalZone } from '../../../lib/types/generated/enums';
import { useUIStore } from '../../../lib/store/uiStore';

interface Props {
  config: ZoneConfig;
  children?: React.ReactNode;
}

export function ZonePlatform({ config, children }: Props) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const edgeRef = useRef<THREE.Mesh>(null!);
  const [hovered, setHovered] = useState(false);
  const selectZone = useUIStore((s) => s.selectZone);
  const selectedZone = useUIStore((s) => s.selectedZone);
  const isSelected = selectedZone === config.zone;

  const r = config.radius;
  const h = 0.3; // platform height
  const baseY = config.elevation;

  useFrame(({ clock }) => {
    if (edgeRef.current) {
      // Pulsing edge glow
      const mat = edgeRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 0.3 + Math.sin(clock.getElapsedTime() * 1.5) * 0.15;
      if (isSelected) mat.emissiveIntensity += 0.4;
    }
  });

  return (
    <group position={[config.center.x, baseY, config.center.z]}>
      {/* Platform slab */}
      <mesh
        ref={meshRef}
        position={[0, -h / 2, 0]}
        receiveShadow
        onClick={() => selectZone(isSelected ? null : config.zone as LogicalZone)}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <cylinderGeometry args={[r, r * 1.05, h, 32]} />
        <meshStandardMaterial
          color={config.color}
          roughness={0.6}
          metalness={0.3}
          emissive={config.emissive}
          emissiveIntensity={isSelected || hovered ? 0.12 : 0.05}
        />
      </mesh>

      {/* Perimeter glow ring */}
      <mesh
        ref={edgeRef}
        position={[0, 0.02, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <ringGeometry args={[r - 0.5, r, 64]} />
        <meshStandardMaterial
          color={config.emissive}
          emissive={config.emissive}
          emissiveIntensity={0.3}
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Zone label — always faces camera */}
      <Billboard position={[0, r * 0.4 + 4, 0]}>
        <Text
          fontSize={2.2}
          color={config.emissive}
          anchorX="center"
          anchorY="middle"
          material-toneMapped={false}
        >
          {config.label}
        </Text>
      </Billboard>

      {/* Children (workers, props, etc.) rendered at zone origin */}
      {children}
    </group>
  );
}
