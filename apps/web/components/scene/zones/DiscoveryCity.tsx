'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function DiscoveryCityZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('DISCOVERY_CITY');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#22c55e" intensity={2} distance={30} />
      {children}
    </ZonePlatform>
  );
}
