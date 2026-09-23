import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Required for Docker multi-stage build (copies .next/standalone)
  output: 'standalone',
  // Transpile Three.js packages
  transpilePackages: ['three', '@react-three/fiber', '@react-three/drei'],
  // Webpack config for GLSL shaders and Three.js
  webpack: (config) => {
    config.module.rules.push({
      test: /\.(glsl|vert|frag)$/,
      type: 'asset/source',
    });
    return config;
  },
  // Env vars exposed to client
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000',
    NEXT_PUBLIC_SIMULATION_MODE: process.env.SIMULATION_MODE ?? 'true',
  },
};

export default nextConfig;
