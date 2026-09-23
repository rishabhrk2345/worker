'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function ResearchLabZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('RESEARCH_LAB');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#f97316" intensity={2} distance={22} />
      {children}
    </ZonePlatform>
  );
}
