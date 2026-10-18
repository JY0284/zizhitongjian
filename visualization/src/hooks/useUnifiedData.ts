import { useState, useEffect, useMemo } from 'react';
import type { UnifiedKnowledgeBase } from '../types/unified';
import { fetchRuntimeData } from '../utils/runtimeData';
import {
  unifiedEventsToTimeline,
  unifiedLocationsToList,
  calculateUnifiedPowerDistribution,
  unifiedNetworkGraphData,
} from '../utils/unifiedDataProcessing';

/**
 * Hook to load the unified knowledge base
 */
export function useUnifiedKnowledgeBase() {
  const [kb, setKb] = useState<UnifiedKnowledgeBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadData() {
      try {
        const data = await fetchRuntimeData<UnifiedKnowledgeBase>(
          `${import.meta.env.BASE_URL}data/unified_knowledge.json`, controller.signal);
        for (const key of ['roles', 'locations', 'events', 'relations', 'name_to_role_id', 'name_to_location_id'] as const) {
          if (!data[key] || typeof data[key] !== 'object' || Array.isArray(data[key])) {
            throw new Error(`统一知识库字段 ${key} 无效，请重新构建数据。`);
          }
        }
        if (controller.signal.aborted) return;
        setKb(data);
        setLoading(false);
      } catch (err) {
        if (controller.signal.aborted) return;
        console.error('Error loading unified knowledge base:', err);
        setError(err instanceof Error ? err.message : 'Unknown error loading data');
        setLoading(false);
      }
    }

    loadData();
    return () => controller.abort();
  }, []);

  return { kb, loading, error };
}

/**
 * Hook to get processed visualization data from unified knowledge base
 */
export function useUnifiedVisualizationData(
  kb: UnifiedKnowledgeBase | null,
  juanRange?: [number, number],
  yearRange?: [number | null, number | null]
) {
  const { nodes, links } = useMemo(() => {
    if (!kb) return { nodes: [], links: [] };
    return unifiedNetworkGraphData(kb, juanRange, yearRange ?? [null, null]);
  }, [kb, juanRange, yearRange]);

  const timelineEvents = useMemo(() => {
    if (!kb) return [];
    return unifiedEventsToTimeline(kb, juanRange);
  }, [kb, juanRange]);

  const locations = useMemo(() => {
    if (!kb) return [];
    return unifiedLocationsToList(kb, juanRange, yearRange);
  }, [kb, juanRange, yearRange]);

  const powerDistribution = useMemo(() => {
    if (!kb) return [];
    return calculateUnifiedPowerDistribution(kb);
  }, [kb]);

  return {
    nodes,
    links,
    timelineEvents,
    locations,
    powerDistribution,
  };
}

/**
 * Hook to search the unified knowledge base
 */
export function useUnifiedSearch(
  kb: UnifiedKnowledgeBase | null,
  query: string,
  limit: number = 20
) {
  const results = useMemo(() => {
    if (!kb || !query.trim()) return [];
    
    const queryLower = query.toLowerCase();
    const results: Array<{
      type: 'role' | 'location' | 'event';
      id: string;
      name: string;
      description: string;
      score: number;
    }> = [];

    // Search roles
    for (const role of Object.values(kb.roles)) {
      let score = 0;
      const nameLower = role.canonical_name.toLowerCase();
      
      if (nameLower === queryLower) score += 100;
      else if (nameLower.includes(queryLower)) score += 50;
      
      for (const alias of role.all_names) {
        if (alias === query) score += 80;
        else if (alias.includes(query)) score += 30;
      }
      
      if (role.description.includes(query)) score += 10;
      
      if (score > 0) {
        results.push({
          type: 'role',
          id: role.id,
          name: role.canonical_name,
          description: role.description,
          score,
        });
      }
    }

    // Search locations
    for (const location of Object.values(kb.locations)) {
      let score = 0;
      
      if (location.canonical_name === query) score += 100;
      else if (location.canonical_name.includes(query)) score += 50;
      
      for (const alias of location.all_names) {
        if (alias === query) score += 80;
        else if (alias.includes(query)) score += 30;
      }
      
      if (location.description.includes(query)) score += 10;
      if (location.modern_name.includes(query)) score += 20;
      
      if (score > 0) {
        results.push({
          type: 'location',
          id: location.id,
          name: location.canonical_name,
          description: location.description,
          score,
        });
      }
    }

    // Search events
    for (const event of Object.values(kb.events)) {
      let score = 0;
      
      if (event.name === query) score += 100;
      else if (event.name.includes(query)) score += 50;
      
      if (event.description.includes(query)) score += 10;
      
      if (score > 0) {
        results.push({
          type: 'event',
          id: event.id,
          name: event.name,
          description: event.description,
          score,
        });
      }
    }

    return results.sort((a, b) => b.score - a.score).slice(0, limit);
  }, [kb, query, limit]);

  return results;
}
