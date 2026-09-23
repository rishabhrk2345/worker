'use client';
import { ZonePlatform } from './ZonePlatform';
import { getZoneConfig } from '../ZoneRegistry';

export function InvestigationRoomZone({ children }: { children?: React.ReactNode }) {
  const cfg = getZoneConfig('INVESTIGATION_ROOM');
  return (
    <ZonePlatform config={cfg}>
      <pointLight position={[0, 5, 0]} color="#f59e0b" intensity={2} distance={20} />
      {children}
    </ZonePlatform>
  );
}
