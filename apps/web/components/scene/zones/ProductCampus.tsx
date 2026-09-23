'use client';
import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';
import { useProductStore } from '../../../lib/store/productStore';

const POD_POSITIONS = [
  [-6, 0, -6], [0, 0, -6], [6, 0, -6],
  [-6, 0, 0],  [0, 0, 0],  [6, 0, 0],
] as [number, number, number][];

const PRODUCT_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444',
];

function ProductPod({ product, position, color }: {
  product: { name: string } | undefined;
  position: [number, number, number];
  color: string;
}) {
  const meshRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = clock.getElapsedTime() * 0.3;
    }
  });

  if (!product) return null;

  return (
    <group position={position}>
      <mesh ref={meshRef} position={[0, 2, 0]}>
        <octahedronGeometry args={[1.2]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.5}
          metalness={0.4}
          roughness={0.2}
        />
      </mesh>
      <Text
        position={[0, 4, 0]}
        fontSize={0.7}
        color={color}
        anchorX="center"
        anchorY="middle"
        maxWidth={5}
      >
        {product.name}
      </Text>
      <pointLight position={[0, 2, 0]} color={color} intensity={1.5} distance={8} />
    </group>
  );
}

export function ProductCampusZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('PRODUCT_CAMPUS');
  const products = useProductStore((s) => Array.from(s.products.values()).slice(0, 5));

  return (
    <ZonePlatform config={cfg}>
      {POD_POSITIONS.slice(0, products.length).map((pos, i) => (
        <ProductPod
          key={i}
          product={products[i]}
          position={pos}
          color={PRODUCT_COLORS[i % PRODUCT_COLORS.length]}
        />
      ))}
      {children}
    </ZonePlatform>
  );
}
