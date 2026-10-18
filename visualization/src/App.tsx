import { lazy, Suspense, useEffect, useMemo, useCallback, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useUnifiedKnowledgeBase, useUnifiedVisualizationData } from './hooks/useUnifiedData';
import { useJuanYearIndex } from './hooks/useJuanYearIndex';
import {
  Timeline,
  NetworkGraph,
  PowerChart,
  FilterControls,
  EventDetail,
  RoleDetail,
  LocationsView,
  LocationDetail,
  RelationDetail,
  GitHubRepoBadge,
} from './components';
import type { TimelineEventUnified, RoleNodeUnified, UnifiedLocation, RoleLinkUnified } from './types/unified';
import { parseUrlGlobalContext, writeUrlGlobalContext } from './state';
import { juanYearRange, juansOverlappingYears } from './utils/yearRanges';
import { roleNavigation, resolveRoleId } from './utils/roleNavigation';
import { hasMapPosition } from './utils/mapCoordinates';

type TabType = 'timeline' | 'network' | 'power' | 'locations' | 'map';
const MapView = lazy(() => import('./components/MapView').then(module => ({ default: module.MapView })));

// Interface for showing all relations between two nodes
interface SelectedRelationPair {
  sourceId: string;
  targetId: string;
  sourceName: string;
  targetName: string;
  relations: RoleLinkUnified[];
}

function App() {
  // Use the unified knowledge base hook
  const { kb, loading, error } = useUnifiedKnowledgeBase();
  const { juanYearIndex, loading: yearsLoading, error: yearsError } = useJuanYearIndex();

  const [searchParams, setSearchParams] = useSearchParams();
  const [initialCtx] = useState(() => parseUrlGlobalContext(searchParams, 294));
  
  const [juanRange, setJuanRange] = useState<[number, number]>(initialCtx.juanRange);
  const [timeRange, setTimeRange] = useState<[number | null, number | null]>(initialCtx.yearRange);
  const [activeTab, setActiveTab] = useState<TabType>(initialCtx.tab);
  const [syncJuanYear, setSyncJuanYear] = useState(true);
  
  const [selectedEvent, setSelectedEvent] = useState<TimelineEventUnified | null>(null);
  const [selectedRole, setSelectedRole] = useState<RoleNodeUnified | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<UnifiedLocation | null>(null);
  const [selectedRelationPair, setSelectedRelationPair] = useState<SelectedRelationPair | null>(null);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);

  // Get processed visualization data from unified KB
  const { 
    nodes: roles, 
    links: roleLinks, 
    timelineEvents, 
    locations, 
  } = useUnifiedVisualizationData(kb, juanRange, timeRange);

  const normalizeJuanRange = useCallback((range: [number, number], maxJuan: number): [number, number] => {
    let [start, end] = range;
    start = Math.max(1, Math.min(maxJuan, start));
    end = Math.max(1, Math.min(maxJuan, end));
    if (start > end) [start, end] = [end, start];
    return [start, end];
  }, []);

  const normalizeYearRange = useCallback((range: [number | null, number | null]): [number | null, number | null] => {
    const [a, b] = range;
    if (a === null || b === null) return [a, b];
    return a <= b ? [a, b] : [b, a];
  }, []);

  const deriveYearRangeFromJuanRange = useCallback(
    (range: [number, number]): [number | null, number | null] | null => {
      return juanYearIndex ? juanYearRange(juanYearIndex, range) : null;
    },
    [juanYearIndex]
  );

  const deriveJuanRangeFromYearRange = useCallback(
    (range: [number | null, number | null], maxJuan: number): [number, number] | null => {
      if (!juanYearIndex) return null;
      const result = juansOverlappingYears(juanYearIndex, normalizeYearRange(range));
      return result ? normalizeJuanRange(result, maxJuan) : null;
    },
    [juanYearIndex, normalizeYearRange, normalizeJuanRange]
  );

  // Keep latest derived arrays in refs so URL-sync effect doesn't depend on them
  // (avoids rerender loops if hooks return new array identities each render).
  const rolesRef = useRef<RoleNodeUnified[]>([]);
  const roleLinksRef = useRef<RoleLinkUnified[]>([]);
  useEffect(() => {
    rolesRef.current = roles;
  }, [roles]);
  useEffect(() => {
    roleLinksRef.current = roleLinks;
  }, [roleLinks]);

  // Keep local state in sync when the user navigates Back/Forward.
  useEffect(() => {
    const ctx = parseUrlGlobalContext(searchParams, 294);
    // Browser Back/Forward is an external navigation event; restore the local view.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveTab(ctx.tab);
    
    // PERFORMANCE CRITICAL: Only update juanRange/timeRange if values actually changed.
    // 
    // Problem this solves:
    // - parseUrlGlobalContext() always returns NEW array references (e.g., [1, 3])
    // - Even if values are identical, React treats new arrays as "changed" state
    // - This triggers useUnifiedVisualizationData() to recompute with "new" juanRange
    // - Which creates new roles/roleLinks arrays, causing NetworkGraph to rebuild D3 simulation
    // - Result: clicking a node would reset all graph node positions!
    //
    // Solution: Use functional setState to compare values, keeping the same reference if unchanged.
    // DO NOT simplify to `setJuanRange(ctx.juanRange)` - it will break graph interactions!
    setJuanRange(prev => 
      prev[0] === ctx.juanRange[0] && prev[1] === ctx.juanRange[1] 
        ? prev 
        : ctx.juanRange
    );
    setTimeRange(prev => 
      prev[0] === ctx.yearRange[0] && prev[1] === ctx.yearRange[1] 
        ? prev 
        : ctx.yearRange
    );
    setFocusNodeId(ctx.focusRoleId ?? null);

    // Restore selection when possible.
    const selection = ctx.selection;
    if (!kb || !selection) {
      setSelectedEvent(null);
      setSelectedRole(null);
      setSelectedLocation(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === 'event') {
      const ev = kb.events?.[selection.id];
      if (ev) {
        setSelectedEvent({
          id: ev.id,
          name: ev.name,
          time: ev.time,
          timeNumeric: ev.time_start ?? null,
          location: ev.location,
          participants: Array.from(ev.participants || []),
          description: ev.description,
          juan_index: ev.source_juans?.[0] || 0,
          type: 'event',
          significance: ev.significance,
          background: ev.background,
        });
      }
      setSelectedRole(null);
      setSelectedLocation(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === 'role') {
      const role = kb.roles?.[resolveRoleId(kb, selection.id) ?? selection.id];
      if (role) {
        setSelectedRole({
          id: role.id,
          name: role.canonical_name,
          power: role.primary_power,
          description: role.description,
          appearances: role.total_mentions,
          juans: role.juans_appeared,
          aliases: Array.from(role.all_names || []).filter(n => n !== role.canonical_name),
          relatedEntities: Array.from(role.related_entities || []),
        });
      }
      setSelectedEvent(null);
      setSelectedLocation(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === 'location') {
      const loc = kb.locations?.[selection.id] ?? kb.locations?.[kb.name_to_location_id?.[selection.id]];
      setSelectedLocation(loc ?? null);
      setSelectedEvent(null);
      setSelectedRole(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === 'relationPair') {
      // Reconstruct the selected relation pair from the currently loaded link list.
      const currentLinks = roleLinksRef.current;
      const currentRoles = rolesRef.current;
      const relations = currentLinks.filter(link => {
        const linkSourceId = link.source;
        const linkTargetId = link.target;
        return (
          (linkSourceId === selection.sourceId && linkTargetId === selection.targetId) ||
          (linkSourceId === selection.targetId && linkTargetId === selection.sourceId)
        );
      });
      const sourceNode = currentRoles.find(n => n.id === selection.sourceId);
      const targetNode = currentRoles.find(n => n.id === selection.targetId);
      setSelectedRelationPair({
        sourceId: selection.sourceId,
        targetId: selection.targetId,
        sourceName: sourceNode?.name || selection.sourceId,
        targetName: targetNode?.name || selection.targetId,
        relations,
      });
      setSelectedEvent(null);
      setSelectedRole(null);
      setSelectedLocation(null);
    }
  }, [searchParams, kb]);

  const selectionForUrl = useMemo(() => {
    if (selectedEvent) return { type: 'event' as const, id: selectedEvent.id };
    if (selectedRole) return { type: 'role' as const, id: selectedRole.id };
    if (selectedLocation) return { type: 'location' as const, id: selectedLocation.id };
    if (selectedRelationPair)
      return {
        type: 'relationPair' as const,
        sourceId: selectedRelationPair.sourceId,
        targetId: selectedRelationPair.targetId,
      };
    return undefined;
  }, [selectedEvent, selectedRole, selectedLocation, selectedRelationPair]);

  const updateUrlContext = useCallback(
    (
      next: Partial<{
        tab: TabType;
        juanRange: [number, number];
        yearRange: [number | null, number | null];
        focusRoleId: string | undefined;
      }>,
      opts: { replace: boolean }
    ) => {
      const params = writeUrlGlobalContext(searchParams, {
        tab: next.tab ?? activeTab,
        juanRange: next.juanRange ?? juanRange,
        yearRange: next.yearRange ?? timeRange,
        focusRoleId: (next.focusRoleId ?? focusNodeId ?? undefined) as string | undefined,
        selection: selectionForUrl,
      });
      setSearchParams(params, { replace: opts.replace });
    },
    [searchParams, setSearchParams, activeTab, juanRange, timeRange, focusNodeId, selectionForUrl]
  );

  const mapFocusLocationId = useMemo(() => searchParams.get('mapLoc') ?? null, [searchParams]);

  // Handler for focusing on a node in the graph (from detail panels)
  const handleFocusNode = useCallback((entityName: string) => {
    const target = roleNavigation(kb, entityName, juanRange, timeRange, new Set(roles.map(r => r.id)));
    if (!target) return;
    // A single history entry restores the location and its filters on Back.
    const next = writeUrlGlobalContext(searchParams, {
      tab: 'network',
      juanRange: target.juanRange,
      yearRange: target.yearRange,
      focusRoleId: target.id,
      selection: { type: 'role', id: target.id },
    });
    setSearchParams(next, { replace: false });
  }, [kb, roles, searchParams, setSearchParams, juanRange, timeRange]);

  // Handler for navigating to map (optionally focusing a specific location)
  const handleNavigateToMap = useCallback((focusLocationId?: string) => {
    // Ensure we don't carry an open modal selection into the map view.
    setSelectedEvent(null);
    setSelectedRole(null);
    setSelectedLocation(null);
    setSelectedRelationPair(null);
    setActiveTab('map');
    const next = writeUrlGlobalContext(searchParams, {
      tab: 'map',
      juanRange,
      yearRange: timeRange,
      focusRoleId: focusNodeId ?? undefined,
      selection: undefined,
    });
    if (focusLocationId) next.set('mapLoc', focusLocationId);
    else next.delete('mapLoc');
    setSearchParams(next, { replace: false });
  }, [searchParams, setSearchParams, juanRange, timeRange, focusNodeId]);

  // Handler for link click - find all relations between two nodes
  const handleLinkClick = useCallback((sourceId: string, targetId: string) => {
    // Find all relations between these two nodes (in both directions)
    const relations = roleLinks.filter(link => {
      const linkSourceId = link.source;
      const linkTargetId = link.target;
      return (linkSourceId === sourceId && linkTargetId === targetId) ||
             (linkSourceId === targetId && linkTargetId === sourceId);
    });
    
    const sourceNode = roles.find(n => n.id === sourceId);
    const targetNode = roles.find(n => n.id === targetId);
    
    setSelectedRelationPair({
      sourceId,
      targetId,
      sourceName: sourceNode?.name || sourceId,
      targetName: targetNode?.name || targetId,
      relations,
    });

    const next = writeUrlGlobalContext(searchParams, {
      tab: 'network',
      juanRange,
      yearRange: timeRange,
      focusRoleId: focusNodeId ?? undefined,
      selection: { type: 'relationPair', sourceId, targetId },
    });
    setSearchParams(next, { replace: false });
  }, [roleLinks, roles, searchParams, setSearchParams, juanRange, timeRange, focusNodeId]);

  // Filter events by time range if needed
  const filteredEvents = useMemo(() => {
    if (timeRange[0] === null && timeRange[1] === null) return timelineEvents;
    
    return timelineEvents.filter(event => {
      if (event.timeNumeric === null) return true;
      const afterStart = timeRange[0] === null || event.timeNumeric >= timeRange[0];
      const beforeEnd = timeRange[1] === null || event.timeNumeric <= timeRange[1];
      return afterStart && beforeEnd;
    });
  }, [timelineEvents, timeRange]);

  const filteredLocations = locations;

  // Handler for clicking a location name (from detail panels) - opens location detail
  const handleLocationNameClick = useCallback((locationName: string) => {
    // Find the location by name
    const loc = filteredLocations.find(
      (l) => l.canonical_name === locationName || l.all_names?.includes(locationName)
    );
    if (loc) {
      setSelectedLocation(loc);
      // Also update URL so the selection persists and doesn't get cleared by URL sync effect
      const next = writeUrlGlobalContext(searchParams, {
        tab: activeTab,
        juanRange,
        yearRange: timeRange,
        focusRoleId: focusNodeId ?? undefined,
        selection: { type: 'location', id: loc.id },
      });
      setSearchParams(next, { replace: false });
    }
  }, [filteredLocations, searchParams, setSearchParams, activeTab, juanRange, timeRange, focusNodeId]);

  // Handler for clicking an event (from RoleDetail/RelationDetail) - opens event detail
  const handleEventDetailClick = useCallback((event: TimelineEventUnified) => {
    setSelectedEvent(event);
    const next = writeUrlGlobalContext(searchParams, {
      tab: activeTab,
      juanRange,
      yearRange: timeRange,
      focusRoleId: focusNodeId ?? undefined,
      selection: { type: 'event', id: event.id },
    });
    setSearchParams(next, { replace: false });
  }, [searchParams, setSearchParams, activeTab, juanRange, timeRange, focusNodeId]);

  const availableRoleIds = useMemo(() => new Set(roles.map((r) => r.id)), [roles]);

  const powerDistributionInRange = useMemo(() => {
    // Keep Power tab consistent with current Global Context by using in-range network nodes.
    const byPower = new Map<string, { count: number; roles: string[] }>();
    for (const role of roles) {
      if (!role.power) continue;
      const entry = byPower.get(role.power) ?? { count: 0, roles: [] };
      entry.count += 1;
      entry.roles.push(role.id);
      byPower.set(role.power, entry);
    }
    return Array.from(byPower.entries())
      .map(([power, v]) => ({ power, count: v.count, roles: v.roles }))
      .sort((a, b) => b.count - a.count);
  }, [roles]);

  if (loading || yearsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#faf8f5]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-[#8b4513] border-t-transparent mx-auto mb-4"></div>
          <p className="text-[#2c1810]">正在加载统一知识库...</p>
          <p className="text-sm text-gray-500 mt-2">正在解析实体关系网络</p>
        </div>
      </div>
    );
  }

  if (error || yearsError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#faf8f5]">
        <div className="text-center text-red-600">
          <p className="text-xl mb-2">加载失败</p>
          <p className="text-sm">{error || yearsError}</p>
          <p className="text-sm mt-4 text-gray-500">
            运行时数据尚未准备好，请按项目 README 的本地启动步骤生成数据后刷新。
          </p>
        </div>
      </div>
    );
  }

  const tabs: { id: TabType; label: string; icon: string }[] = [
    { id: 'timeline', label: '时间轴', icon: '📅' },
    { id: 'network', label: '关系网络', icon: '🔗' },
    { id: 'power', label: '势力分布', icon: '📊' },
    { id: 'locations', label: '地点', icon: '📍' },
    { id: 'map', label: '地图', icon: '🗺️' },
  ];

  return (
    <div className="min-h-screen bg-[#faf8f5]">
      {/* Header */}
      <header className="bg-gradient-to-r from-[#8b4513] to-[#5d2e0c] text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">资治通鉴可视化系统</h1>
            <p className="text-[#d4a574] mt-1">{kb?.data_mode === 'demo' ? '样例预览' : '基于统一知识库'}</p>
            {!!kb?.extraction_models?.length && <p className="text-xs mt-1 text-amber-100">抽取模型：{kb.extraction_models.join(' · ')}</p>}
            {kb?.data_notice && <p className="text-sm mt-2 max-w-3xl">{kb.data_notice}</p>}
            {kb?.data_coverage && <p className="text-sm mt-2 text-amber-100">
              {kb.data_coverage.map(item => `卷${item.juan}：${item.processed}/${item.total}${item.complete ? ' ✓' : ''}`).join(' · ')}
            </p>}
          </div>

          <div className="pt-1">
            <GitHubRepoBadge
              repoFullName="JY0284/zizhitongjian"
              repoUrl="https://github.com/JY0284/zizhitongjian"
            />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar with filters */}
          <div className="lg:col-span-1">
            <FilterControls
              onPreset={(juans, years) => {
                setJuanRange(juans);
                setTimeRange(years);
                updateUrlContext({ juanRange: juans, yearRange: years }, { replace: false });
              }}
              juanRange={juanRange}
              onJuanRangeChange={(range) => {
                const nextJuanRange = normalizeJuanRange(range, 294);
                setJuanRange(nextJuanRange);

                if (syncJuanYear) {
                  const derived = deriveYearRangeFromJuanRange(nextJuanRange);
                  if (derived) {
                    setTimeRange(derived);
                    updateUrlContext({ juanRange: nextJuanRange, yearRange: derived }, { replace: true });
                    return;
                  }
                }

                updateUrlContext({ juanRange: nextJuanRange }, { replace: true });
              }}
              onJuanRangeCommit={(range) => {
                const nextJuanRange = normalizeJuanRange(range, 294);
                if (syncJuanYear) {
                  const derived = deriveYearRangeFromJuanRange(nextJuanRange);
                  if (derived) {
                    setTimeRange(derived);
                    updateUrlContext({ juanRange: nextJuanRange, yearRange: derived }, { replace: false });
                    return;
                  }
                }
                updateUrlContext({ juanRange: nextJuanRange }, { replace: false });
              }}
              maxJuan={294}
              timeRange={timeRange}
              onTimeRangeChange={(range) => {
                const nextYearRange = normalizeYearRange(range);
                setTimeRange(nextYearRange);

                if (syncJuanYear) {
                  const derivedJuanRange = deriveJuanRangeFromYearRange(nextYearRange, 294);
                  if (derivedJuanRange) {
                    setJuanRange(derivedJuanRange);
                    updateUrlContext({ juanRange: derivedJuanRange, yearRange: nextYearRange }, { replace: true });
                    return;
                  }
                }

                updateUrlContext({ yearRange: nextYearRange }, { replace: true });
              }}
              onTimeRangeCommit={(range) => {
                const nextYearRange = normalizeYearRange(range);
                if (syncJuanYear) {
                  const derivedJuanRange = deriveJuanRangeFromYearRange(nextYearRange, 294);
                  if (derivedJuanRange) {
                    setJuanRange(derivedJuanRange);
                    updateUrlContext({ juanRange: derivedJuanRange, yearRange: nextYearRange }, { replace: false });
                    return;
                  }
                }
                updateUrlContext({ yearRange: nextYearRange }, { replace: false });
              }}
              syncJuanYear={syncJuanYear}
              syncAvailable={Boolean(juanYearIndex?.juan_start_year)}
              onSyncJuanYearChange={(enabled) => {
                setSyncJuanYear(enabled);
                if (!enabled) return;
                const derived = deriveYearRangeFromJuanRange(juanRange);
                if (derived) {
                  setTimeRange(derived);
                  updateUrlContext({ yearRange: derived }, { replace: true });
                }
              }}
            />

            {/* Stats */}
            <div className="bg-white rounded-lg shadow-md p-4 mt-4">
              <h3 className="text-lg font-bold text-[#2c1810] mb-3">当前筛选</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">关系网人物：</span>
                  <span className="font-semibold">{roles.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">事件数量：</span>
                  <span className="font-semibold">{filteredEvents.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">地点数量：</span>
                  <span className="font-semibold">{filteredLocations.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">人物间关系：</span>
                  <span className="font-semibold">{roleLinks.length}</span>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-3">关系网仅显示人物之间的关系及相连人物。国家、组织和未连线人物不计入此处。</p>
            </div>
          </div>

          {/* Main content */}
          <div className="lg:col-span-3">
            {/* Tabs */}
            <div className="bg-white rounded-lg shadow-md mb-4">
              <div className="flex border-b border-[#d4c5b5]">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setActiveTab(tab.id);
                      const next = writeUrlGlobalContext(searchParams, {
                        tab: tab.id,
                        juanRange,
                        yearRange: timeRange,
                        focusRoleId: focusNodeId ?? undefined,
                        selection: undefined,
                      });
                      // Clear map focus on generic tab switches.
                      next.delete('mapLoc');
                      setSearchParams(next, { replace: false });
                    }}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'text-[#8b4513] border-b-2 border-[#8b4513] bg-[#faf8f5]'
                        : 'text-gray-500 hover:text-[#8b4513] hover:bg-[#faf8f5]'
                    }`}
                  >
                    <span className="mr-2">{tab.icon}</span>
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab content */}
            <div className="space-y-4">
              {activeTab === 'timeline' && (
                <Timeline
                  events={filteredEvents}
                  onEventClick={(ev) => {
                    setSelectedEvent(ev);
                    const next = writeUrlGlobalContext(searchParams, {
                      tab: 'timeline',
                      juanRange,
                      yearRange: timeRange,
                      focusRoleId: focusNodeId ?? undefined,
                      selection: { type: 'event', id: ev.id },
                    });
                    setSearchParams(next, { replace: false });
                  }}
                />
              )}

              {activeTab === 'network' && (
                <NetworkGraph
                  nodes={roles}
                  links={roleLinks}
                  onNodeClick={(role) => {
                    setSelectedRole(role);
                    const next = writeUrlGlobalContext(searchParams, {
                      tab: 'network',
                      juanRange,
                      yearRange: timeRange,
                      focusRoleId: focusNodeId ?? undefined,
                      selection: { type: 'role', id: role.id },
                    });
                    setSearchParams(next, { replace: false });
                  }}
                  onLinkClick={handleLinkClick}
                  focusNodeId={focusNodeId}
                  onFocusNodeHandled={() => setFocusNodeId(null)}
                />
              )}

              {activeTab === 'power' && (
                <PowerChart data={powerDistributionInRange} />
              )}

              {activeTab === 'locations' && (
                <LocationsView
                  locations={filteredLocations}
                  onLocationClick={(loc) => {
                    setSelectedLocation(loc);
                    const next = writeUrlGlobalContext(searchParams, {
                      tab: 'locations',
                      juanRange,
                      yearRange: timeRange,
                      focusRoleId: focusNodeId ?? undefined,
                      selection: { type: 'location', id: loc.id },
                    });
                    setSearchParams(next, { replace: false });
                  }}
                  onNavigateToMap={(loc) => handleNavigateToMap(loc.id)}
                />
              )}

              {activeTab === 'map' && (
                <Suspense fallback={<p className="p-6 text-gray-500">正在加载地图…</p>}>
                <MapView
                  locations={filteredLocations}
                  eventsInRange={filteredEvents}
                  selectedRole={selectedRole}
                  selectedEvent={selectedEvent}
                  focusLocationId={mapFocusLocationId}
                  onLocationClick={(loc) => {
                    setSelectedLocation(loc);
                  }}
                />
                </Suspense>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-[#2c1810] text-[#d4a574] py-4 mt-8">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          资治通鉴历史数据可视化系统 © 2026
        </div>
      </footer>

      {/* Detail modals */}
      <EventDetail 
        event={selectedEvent} 
        onClose={() => {
          setSelectedEvent(null);
          const next = writeUrlGlobalContext(searchParams, {
            tab: activeTab,
            juanRange,
            yearRange: timeRange,
            focusRoleId: focusNodeId ?? undefined,
            selection: undefined,
          });
          setSearchParams(next, { replace: false });
        }}
        onEntityClick={handleFocusNode}
        onLocationClick={handleLocationNameClick}
        kb={kb}
        availableRoleIds={availableRoleIds}
      />
      <RoleDetail 
        role={selectedRole} 
        onClose={() => {
          setSelectedRole(null);
          const next = writeUrlGlobalContext(searchParams, {
            tab: activeTab,
            juanRange,
            yearRange: timeRange,
            focusRoleId: focusNodeId ?? undefined,
            selection: undefined,
          });
          setSearchParams(next, { replace: false });
        }}
        onEntityClick={handleFocusNode}
        onEventClick={handleEventDetailClick}
        relatedEvents={selectedRole ? filteredEvents.filter(e => e.participants.some(p => p === selectedRole.name || selectedRole.aliases?.includes(p))) : []}
        kb={kb}
        availableRoleIds={availableRoleIds}
      />
      {selectedLocation && (
        <LocationDetail
          location={selectedLocation}
          relatedEvents={filteredEvents.filter(e => e.location === selectedLocation.canonical_name)}
          relatedRoles={selectedLocation.associated_entities || []}
          relatedActions={[]} // Actions not directly linked to location in unified view yet
          onClose={() => {
            setSelectedLocation(null);
            const next = writeUrlGlobalContext(searchParams, {
              tab: activeTab,
              juanRange,
              yearRange: timeRange,
              focusRoleId: focusNodeId ?? undefined,
              selection: undefined,
            });
            setSearchParams(next, { replace: false });
          }}
          onEntityClick={handleFocusNode}
          onNavigateToMap={hasMapPosition(selectedLocation) ? () => handleNavigateToMap(selectedLocation.id) : undefined}
          kb={kb}
          availableRoleIds={availableRoleIds}
        />
      )}
      {selectedRelationPair && (
        <RelationDetail
          relations={selectedRelationPair.relations}
          sourceName={selectedRelationPair.sourceName}
          targetName={selectedRelationPair.targetName}
          onClose={() => {
            setSelectedRelationPair(null);
            const next = writeUrlGlobalContext(searchParams, {
              tab: activeTab,
              juanRange,
              yearRange: timeRange,
              focusRoleId: focusNodeId ?? undefined,
              selection: undefined,
            });
            setSearchParams(next, { replace: false });
          }}
          onEntityClick={handleFocusNode}
          onEventClick={handleEventDetailClick}
          relatedEvents={(() => {
            // Get all names (canonical + aliases) for both entities
            const sourceRole = kb?.roles?.[selectedRelationPair.sourceId];
            const targetRole = kb?.roles?.[selectedRelationPair.targetId];
            const sourceNames = new Set<string>([
              selectedRelationPair.sourceName,
              ...(sourceRole?.all_names || []),
            ]);
            const targetNames = new Set<string>([
              selectedRelationPair.targetName,
              ...(targetRole?.all_names || []),
            ]);
            // Find events where both entities participate (checking all aliases)
            return filteredEvents.filter(e =>
              e.participants.some(p => sourceNames.has(p)) &&
              e.participants.some(p => targetNames.has(p))
            );
          })()}
          kb={kb}
          availableRoleIds={availableRoleIds}
        />
      )}
    </div>
  );
}

export default App;
