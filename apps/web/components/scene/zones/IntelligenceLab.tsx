'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function IntelligenceLabZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('INTELLIGENCE_LAB');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#a78bfa" intensity={2} distance={24} />
      {children}
    </ZonePlatform>
  );
}
