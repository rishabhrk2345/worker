'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function ActionCenterZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('ACTION_CENTER');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#fbbf24" intensity={2} distance={22} />
      {children}
    </ZonePlatform>
  );
}
