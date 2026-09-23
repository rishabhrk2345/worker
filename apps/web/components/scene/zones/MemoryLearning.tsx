'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function MemoryLearningZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('MEMORY_LEARNING');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#c084fc" intensity={2} distance={18} />
      {children}
    </ZonePlatform>
  );
}
