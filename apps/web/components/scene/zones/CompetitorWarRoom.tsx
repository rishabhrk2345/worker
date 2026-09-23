'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function CompetitorWarRoomZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('COMPETITOR_WAR_ROOM');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#f87171" intensity={2.5} distance={20} />
      {children}
    </ZonePlatform>
  );
}
