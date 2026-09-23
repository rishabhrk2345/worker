'use client';
/**
 * components/scene/Environment.tsx
 *
 * The dark corporate command center environment:
 * - Infinite grid floor with subtle glow lines
 * - Ambient + directional lighting
 * - Fog for depth
 * - Atmospheric particles
 */

import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Grid, Sparkles, Environment as DreiEnvironment } from '@react-three/drei';
import * as THREE from 'three';

export function SceneEnvironment() {
  const particlesRef = useRef<THREE.Points>(null!);

  useFrame(({ clock }) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y = clock.getElapsedTime() * 0.005;
    }
  });

  return (
    <>
      {/* Fog for atmospheric depth */}
      <fog attach="fog" args={['#050508', 80, 280]} />

      {/* Ambient light — low, dark atmosphere */}
      <ambientLight intensity={0.15} color="#1a2040" />

      {/* Main directional light — cool blue-white from above */}
      <directionalLight
        position={[20, 50, 20]}
        intensity={0.8}
        color="#c8d8ff"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-far={200}
        shadow-camera-left={-80}
        shadow-camera-right={80}
        shadow-camera-top={80}
        shadow-camera-bottom={-80}
      />

      {/* Secondary fill light from opposite side */}
      <directionalLight
        position={[-20, 30, -20]}
        intensity={0.3}
        color="#4060a0"
      />

      {/* Ground plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[400, 400]} />
        <meshStandardMaterial
          color="#080810"
          roughness={0.9}
          metalness={0.1}
        />
      </mesh>

      {/* Grid overlay */}
      <Grid
        args={[400, 400]}
        cellSize={5}
        cellThickness={0.3}
        cellColor="#1a2040"
        sectionSize={20}
        sectionThickness={0.6}
        sectionColor="#1e3a6e"
        fadeDistance={200}
        fadeStrength={3}
        followCamera={false}
        position={[0, 0.02, 0]}
      />

      {/* Atmospheric floating particles */}
      <Sparkles
        count={300}
        scale={[200, 40, 200]}
        size={0.8}
        speed={0.2}
        opacity={0.15}
        color="#4080ff"
        position={[0, 20, 0]}
      />

      {/* Preset environment for reflections */}
      <DreiEnvironment preset="night" />
    </>
  );
}
