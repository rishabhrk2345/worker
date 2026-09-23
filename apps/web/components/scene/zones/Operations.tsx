'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function OperationsZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('OPERATIONS');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#94a3b8" intensity={1.5} distance={18} />
      {children}
    </ZonePlatform>
  );
}
