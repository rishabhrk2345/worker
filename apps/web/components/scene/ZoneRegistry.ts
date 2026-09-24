/**
 * components/scene/ZoneRegistry.ts
 *
 * ADR-005 — The ONLY place that maps LogicalZone → 3D world coordinates.
 * Backend events carry LogicalZone enums. This file turns them into positions.
 * Redesigning the scene = change this file only. Backend never changes.
 */

import { LogicalZone } from '../../lib/types/generated/enums';
import * as THREE from 'three';

export interface ZoneConfig {
  zone: LogicalZone;
  label: string;
  /** World-space center of the zone platform */
  center: THREE.Vector3;
  /** Half-extents of the zone bounding box (for LOD and culling) */
  radius: number;
  /** Elevation above the ground plane */
  elevation: number;
  /** Station slots within the zone — indexed by logicalStation string */
  stations: Record<string, THREE.Vector3>;
  /** Visual theme color for the zone floor/accents */
  color: string;
  /** Emissive glow color */
  emissive: string;
}

/** Master zone layout — all coordinates in world units */
const ZONE_CONFIGS: ZoneConfig[] = [
  {
    zone: 'SUPERVISOR',
    label: 'Supervisor HQ',
    center: new THREE.Vector3(0, 6, 0),
    radius: 10,
    elevation: 6,
    color: '#1e40af',      // blue-800
    emissive: '#3b82f6',  // blue-500
    stations: {
      supervisor_console:   new THREE.Vector3(0,    6, 0),
      briefing_table:       new THREE.Vector3(3,    6, 0),
      mission_board:        new THREE.Vector3(-3,   6, 0),
    },
  },
  {
    zone: 'DISCOVERY_CITY',
    label: 'Discovery City',
    center: new THREE.Vector3(-60, 0, -20),
    radius: 22,
    elevation: 0,
    color: '#14532d',
    emissive: '#22c55e',
    stations: {
      social_station:         new THREE.Vector3(-55, 0, -15),
      web_station:            new THREE.Vector3(-60, 0, -15),
      search_station:         new THREE.Vector3(-65, 0, -15),
      news_station:           new THREE.Vector3(-55, 0, -25),
      forum_station:          new THREE.Vector3(-60, 0, -25),
      review_station:         new THREE.Vector3(-65, 0, -25),
      competitor_disc_station: new THREE.Vector3(-55, 0, -20),
      trend_disc_station:     new THREE.Vector3(-65, 0, -20),
    },
  },
  {
    zone: 'SOURCE_OBSERVATORY',
    label: 'Source Observatory',
    center: new THREE.Vector3(-60, 0, 20),
    radius: 18,
    elevation: 0,
    color: '#312e81',
    emissive: '#818cf8',
    stations: {
      reddit_panel:    new THREE.Vector3(-55, 0, 15),
      twitter_panel:   new THREE.Vector3(-58, 0, 15),
      linkedin_panel:  new THREE.Vector3(-61, 0, 15),
      youtube_panel:   new THREE.Vector3(-64, 0, 15),
      instagram_panel: new THREE.Vector3(-55, 0, 22),
      facebook_panel:  new THREE.Vector3(-58, 0, 22),
      threads_panel:   new THREE.Vector3(-61, 0, 22),
      tiktok_panel:    new THREE.Vector3(-64, 0, 22),
      news_panel:      new THREE.Vector3(-55, 0, 28),
      rss_panel:       new THREE.Vector3(-58, 0, 28),
      forums_panel:    new THREE.Vector3(-61, 0, 28),
      reviews_panel:   new THREE.Vector3(-64, 0, 28),
      web_panel:       new THREE.Vector3(-55, 0, 19),
      search_panel:    new THREE.Vector3(-58, 0, 19),
      podcasts_panel:  new THREE.Vector3(-61, 0, 19),
    },
  },
  {
    zone: 'RESEARCH_LAB',
    label: 'Research Lab',
    center: new THREE.Vector3(-30, 0, -40),
    radius: 18,
    elevation: 0,
    color: '#1c1917',
    emissive: '#f97316',
    stations: {
      deep_research_desk:     new THREE.Vector3(-25, 0, -35),
      conversation_desk:      new THREE.Vector3(-30, 0, -35),
      market_desk:            new THREE.Vector3(-35, 0, -35),
      customer_desk:          new THREE.Vector3(-25, 0, -42),
      evidence_desk:          new THREE.Vector3(-30, 0, -42),
      verification_desk:      new THREE.Vector3(-35, 0, -42),
    },
  },
  {
    zone: 'INTELLIGENCE_LAB',
    label: 'Intelligence Lab',
    center: new THREE.Vector3(0, 0, -50),
    radius: 20,
    elevation: 0,
    color: '#1e1b4b',
    emissive: '#a78bfa',
    stations: {
      analyzer_console:   new THREE.Vector3(-6,  0, -44),
      entity_console:     new THREE.Vector3(0,   0, -44),
      problem_console:    new THREE.Vector3(6,   0, -44),
      intent_console:     new THREE.Vector3(-6,  0, -52),
      sentiment_console:  new THREE.Vector3(0,   0, -52),
      context_console:    new THREE.Vector3(6,   0, -52),
      matcher_console:    new THREE.Vector3(-6,  0, -58),
      portfolio_console:  new THREE.Vector3(0,   0, -58),
      opportunity_console:new THREE.Vector3(6,   0, -58),
    },
  },
  {
    zone: 'PRODUCT_CAMPUS',
    label: 'Product Campus',
    center: new THREE.Vector3(50, 0, -30),
    radius: 22,
    elevation: 0,
    color: '#14532d',
    emissive: '#4ade80',
    stations: {
      product_pod_1: new THREE.Vector3(44, 0, -24),
      product_pod_2: new THREE.Vector3(52, 0, -24),
      product_pod_3: new THREE.Vector3(44, 0, -32),
      product_pod_4: new THREE.Vector3(52, 0, -32),
      product_pod_5: new THREE.Vector3(48, 0, -38),
      cross_sell_hub: new THREE.Vector3(48, 0, -28),
    },
  },
  {
    zone: 'COMPETITOR_WAR_ROOM',
    label: 'Competitor War Room',
    center: new THREE.Vector3(60, 0, 10),
    radius: 16,
    elevation: 0,
    color: '#7f1d1d',
    emissive: '#f87171',
    stations: {
      competitor_a_card: new THREE.Vector3(55, 0, 5),
      competitor_b_card: new THREE.Vector3(62, 0, 5),
      competitor_c_card: new THREE.Vector3(55, 0, 12),
      competitor_d_card: new THREE.Vector3(62, 0, 12),
      event_feed_wall:   new THREE.Vector3(58, 0, 18),
    },
  },
  {
    zone: 'ACTION_CENTER',
    label: 'Action Center',
    center: new THREE.Vector3(40, 0, 30),
    radius: 18,
    elevation: 0,
    color: '#78350f',
    emissive: '#fbbf24',
    stations: {
      lead_station:       new THREE.Vector3(35, 0, 25),
      outreach_station:   new THREE.Vector3(42, 0, 25),
      content_station:    new THREE.Vector3(35, 0, 33),
      report_station:     new THREE.Vector3(42, 0, 33),
      approval_queue:     new THREE.Vector3(38, 0, 38),
    },
  },
  {
    zone: 'KNOWLEDGE_CORE',
    label: 'Knowledge Core',
    center: new THREE.Vector3(0, 0, 40),
    radius: 16,
    elevation: 0,
    color: '#0c4a6e',
    emissive: '#38bdf8',
    stations: {
      graph_center:    new THREE.Vector3(0,   0, 40),
      entity_cluster:  new THREE.Vector3(-6,  0, 36),
      relation_ring:   new THREE.Vector3(6,   0, 36),
      fact_archive:    new THREE.Vector3(-6,  0, 44),
      claim_vault:     new THREE.Vector3(6,   0, 44),
    },
  },
  {
    zone: 'MEMORY_LEARNING',
    label: 'Memory & Learning',
    center: new THREE.Vector3(-30, 0, 40),
    radius: 14,
    elevation: 0,
    color: '#1a1a2e',
    emissive: '#c084fc',
    stations: {
      learning_terminal:  new THREE.Vector3(-26, 0, 36),
      feedback_bank:      new THREE.Vector3(-32, 0, 36),
      strategy_board:     new THREE.Vector3(-26, 0, 44),
      reliability_matrix: new THREE.Vector3(-32, 0, 44),
    },
  },
  {
    zone: 'OPERATIONS',
    label: 'Operations Center',
    center: new THREE.Vector3(30, 0, -10),
    radius: 14,
    elevation: 0,
    color: '#1c1917',
    emissive: '#94a3b8',
    stations: {
      health_dashboard: new THREE.Vector3(25, 0, -8),
      budget_tracker:   new THREE.Vector3(32, 0, -8),
      cost_monitor:     new THREE.Vector3(25, 0, -14),
      infra_panel:      new THREE.Vector3(32, 0, -14),
    },
  },
  {
    zone: 'INVESTIGATION_ROOM',
    label: 'Investigation Room',
    center: new THREE.Vector3(-30, 0, 0),
    radius: 16,
    elevation: 0,
    color: '#1e1b4b',
    emissive: '#f59e0b',
    stations: {
      case_board:       new THREE.Vector3(-24, 0, -4),
      evidence_wall:    new THREE.Vector3(-30, 0, -4),
      question_table:   new THREE.Vector3(-36, 0, -4),
      contradiction_corner: new THREE.Vector3(-24, 0, 4),
      verification_pod: new THREE.Vector3(-30, 0, 4),
    },
  },
];

/** Map from LogicalZone → ZoneConfig for O(1) lookup */
const ZONE_MAP = new Map<LogicalZone, ZoneConfig>(
  ZONE_CONFIGS.map((z) => [z.zone, z])
);

export function getZoneConfig(zone: LogicalZone): ZoneConfig {
  const cfg = ZONE_MAP.get(zone) ?? ZONE_MAP.get('SUPERVISOR');
  if (!cfg) throw new Error(`Unknown logical zone: ${zone}`);
  return cfg;
}

export function getStationPosition(
  zone: LogicalZone,
  station: string | null | undefined
): THREE.Vector3 {
  const cfg = getZoneConfig(zone);
  if (station && cfg.stations[station]) {
    return cfg.stations[station].clone();
  }
  return cfg.center.clone();
}

export function getAllZones(): ZoneConfig[] {
  return ZONE_CONFIGS;
}
