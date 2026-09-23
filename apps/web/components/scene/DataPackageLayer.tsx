'use client';
/**
 * components/scene/DataPackageLayer.tsx
 *
 * Listens to the event store for worker.task_transferred events.
 * Spawns a DataPackage3D for each, removes when animation completes.
 * Driven purely by events — no timers.
 */

import { useEffect, useState, useCallback } from 'react';
import { useEventStore } from '../../lib/store/eventStore';
import { DataPackage3D } from './DataPackage3D';
import { LogicalZone } from '../../lib/types/generated/enums';
import { WorkerTaskTransferredPayload } from '../../lib/types/generated/events';

interface ActivePackage {
  id: string;
  fromZone: LogicalZone;
  toZone: LogicalZone;
  label: string;
  color: string;
}

const TYPE_COLORS: Record<string, string> = {
  CRAWL:    '#22c55e',
  ANALYZE:  '#a78bfa',
  RESEARCH: '#f97316',
  ACTION:   '#fbbf24',
};

export function DataPackageLayer() {
  const [packages, setPackages] = useState<ActivePackage[]>([]);
  const events = useEventStore((s) => s.events);

  useEffect(() => {
    const recent = events
      .filter((e) => e.eventType === 'worker.task_transferred')
      .slice(-10); // last 10 transfers

    for (const ev of recent) {
      const payload = ev.payload as WorkerTaskTransferredPayload;
      const pkgId = ev.eventId;

      setPackages((prev) => {
        if (prev.some((p) => p.id === pkgId)) return prev;
        if (!payload.fromZone || !payload.toZone) return prev;

        return [
          ...prev,
          {
            id: pkgId,
            fromZone: payload.fromZone as LogicalZone,
            toZone: payload.toZone as LogicalZone,
            label: payload.taskType ?? 'task',
            color: TYPE_COLORS[payload.taskType?.toUpperCase() ?? ''] ?? '#60a5fa',
          },
        ];
      });
    }
  }, [events]);

  const handleComplete = useCallback((id: string) => {
    setPackages((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return (
    <>
      {packages.map((pkg) => (
        <DataPackage3D
          key={pkg.id}
          id={pkg.id}
          fromZone={pkg.fromZone}
          toZone={pkg.toZone}
          label={pkg.label}
          color={pkg.color}
          onComplete={handleComplete}
        />
      ))}
    </>
  );
}
