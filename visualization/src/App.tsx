import { eventsInYears, roleSearchNames } from "./utils/exploration";
import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useCallback,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";
import {
  useUnifiedKnowledgeBase,
  useUnifiedVisualizationData,
} from "./hooks/useUnifiedData";
import { useJuanYearIndex } from "./hooks/useJuanYearIndex";
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
} from "./components";
import type {
  TimelineEventUnified,
  RoleNodeUnified,
  UnifiedLocation,
  RoleLinkUnified,
} from "./types/unified";
import { parseUrlGlobalContext, writeUrlGlobalContext } from "./state";
import { juanYearRange, juansOverlappingYears } from "./utils/yearRanges";
import { roleNavigation, resolveRoleId } from "./utils/roleNavigation";
import { hasMapPosition } from "./utils/mapCoordinates";

type TabType = "timeline" | "network" | "power" | "locations" | "map";
const MapView = lazy(() =>
  import("./components/MapView").then((module) => ({
    default: module.MapView,
  })),
);

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
  const {
    juanYearIndex,
    loading: yearsLoading,
    error: yearsError,
  } = useJuanYearIndex();

  const [searchParams, setSearchParams] = useSearchParams();
  const [initialCtx] = useState(() => parseUrlGlobalContext(searchParams, 294));

  const [juanRange, setJuanRange] = useState<[number, number]>(
    initialCtx.juanRange,
  );
  const [timeRange, setTimeRange] = useState<[number | null, number | null]>(
    initialCtx.yearRange,
  );
  const [activeTab, setActiveTab] = useState<TabType>(initialCtx.tab);
  const [syncJuanYear, setSyncJuanYear] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [selectedEvent, setSelectedEvent] =
    useState<TimelineEventUnified | null>(null);
  const [selectedRole, setSelectedRole] = useState<RoleNodeUnified | null>(
    null,
  );
  const [selectedLocation, setSelectedLocation] =
    useState<UnifiedLocation | null>(null);
  const [selectedRelationPair, setSelectedRelationPair] =
    useState<SelectedRelationPair | null>(null);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);

  // Get processed visualization data from unified KB
  const {
    nodes: roles,
    links: roleLinks,
    timelineEvents,
    locations,
  } = useUnifiedVisualizationData(kb, juanRange, timeRange);

  const normalizeJuanRange = useCallback(
    (range: [number, number], maxJuan: number): [number, number] => {
      let [start, end] = range;
      start = Math.max(1, Math.min(maxJuan, start));
      end = Math.max(1, Math.min(maxJuan, end));
      if (start > end) [start, end] = [end, start];
      return [start, end];
    },
    [],
  );

  const normalizeYearRange = useCallback(
    (range: [number | null, number | null]): [number | null, number | null] => {
      const [a, b] = range;
      if (a === null || b === null) return [a, b];
      return a <= b ? [a, b] : [b, a];
    },
    [],
  );

  const deriveYearRangeFromJuanRange = useCallback(
    (range: [number, number]): [number | null, number | null] | null => {
      return juanYearIndex ? juanYearRange(juanYearIndex, range) : null;
    },
    [juanYearIndex],
  );

  const deriveJuanRangeFromYearRange = useCallback(
    (
      range: [number | null, number | null],
      maxJuan: number,
    ): [number, number] | null => {
      if (!juanYearIndex) return null;
      const result = juansOverlappingYears(
        juanYearIndex,
        normalizeYearRange(range),
      );
      return result ? normalizeJuanRange(result, maxJuan) : null;
    },
    [juanYearIndex, normalizeYearRange, normalizeJuanRange],
  );

  const roleAliasGroups = useMemo(
    () =>
      Object.values(kb?.roles ?? {}).map((role) =>
        roleSearchNames(role.canonical_name, role.all_names ?? []),
      ),
    [kb],
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
    setJuanRange((prev) =>
      prev[0] === ctx.juanRange[0] && prev[1] === ctx.juanRange[1]
        ? prev
        : ctx.juanRange,
    );
    setTimeRange((prev) =>
      prev[0] === ctx.yearRange[0] && prev[1] === ctx.yearRange[1]
        ? prev
        : ctx.yearRange,
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

    if (selection.type === "event") {
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
          type: "event",
          significance: ev.significance,
          background: ev.background,
        });
      } else setSelectedEvent(null);
      setSelectedRole(null);
      setSelectedLocation(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === "role") {
      const role = kb.roles?.[resolveRoleId(kb, selection.id) ?? selection.id];
      if (role) {
        setSelectedRole({
          id: role.id,
          name: role.canonical_name,
          power: role.primary_power,
          description: role.description,
          appearances: role.total_mentions,
          juans: role.juans_appeared,
          aliases: Array.from(role.all_names || []).filter(
            (n) => n !== role.canonical_name,
          ),
          relatedEntities: Array.from(role.related_entities || []),
        });
      } else setSelectedRole(null);
      setSelectedEvent(null);
      setSelectedLocation(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === "location") {
      const loc =
        kb.locations?.[selection.id] ??
        kb.locations?.[kb.name_to_location_id?.[selection.id]];
      setSelectedLocation(loc ?? null);
      setSelectedEvent(null);
      setSelectedRole(null);
      setSelectedRelationPair(null);
      return;
    }

    if (selection.type === "relationPair") {
      // Reconstruct the selected relation pair from the currently loaded link list.
      const currentLinks = roleLinksRef.current;
      const currentRoles = rolesRef.current;
      const relations = currentLinks.filter((link) => {
        const linkSourceId = link.source;
        const linkTargetId = link.target;
        return (
          (linkSourceId === selection.sourceId &&
            linkTargetId === selection.targetId) ||
          (linkSourceId === selection.targetId &&
            linkTargetId === selection.sourceId)
        );
      });
      const sourceNode = currentRoles.find((n) => n.id === selection.sourceId);
      const targetNode = currentRoles.find((n) => n.id === selection.targetId);
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

  const applyRange = (
    juans: [number, number],
    years: [number | null, number | null],
  ) => {
    const next = writeUrlGlobalContext(searchParams, {
      tab: activeTab,
      juanRange: juans,
      yearRange: years,
    });
    next.delete("mapLoc");
    setSearchParams(next, { replace: false });
    setFiltersOpen(false);
  };

  const mapFocusLocationId = useMemo(
    () => searchParams.get("mapLoc") ?? null,
    [searchParams],
  );

  // Handler for focusing on a node in the graph (from detail panels)
  const handleFocusNode = useCallback(
    (entityName: string) => {
      const target = roleNavigation(
        kb,
        entityName,
        juanRange,
        timeRange,
        new Set(roles.map((r) => r.id)),
      );
      if (!target) return;
      // A single history entry restores the location and its filters on Back.
      const next = writeUrlGlobalContext(searchParams, {
        tab: "network",
        juanRange: target.juanRange,
        yearRange: target.yearRange,
        focusRoleId: target.id,
        selection: { type: "role", id: target.id },
      });
      setSearchParams(next, { replace: false });
    },
    [kb, roles, searchParams, setSearchParams, juanRange, timeRange],
  );

  // Handler for navigating to map (optionally focusing a specific location)
  const handleNavigateToMap = useCallback(
    (focusLocationId?: string) => {
      // Ensure we don't carry an open modal selection into the map view.
      setSelectedEvent(null);
      setSelectedRole(null);
      setSelectedLocation(null);
      setSelectedRelationPair(null);
      setActiveTab("map");
      const next = writeUrlGlobalContext(searchParams, {
        tab: "map",
        juanRange,
        yearRange: timeRange,
        focusRoleId: focusNodeId ?? undefined,
        selection: undefined,
      });
      if (focusLocationId) next.set("mapLoc", focusLocationId);
      else next.delete("mapLoc");
      setSearchParams(next, { replace: false });
    },
    [searchParams, setSearchParams, juanRange, timeRange, focusNodeId],
  );

  // Handler for link click - find all relations between two nodes
  const handleLinkClick = useCallback(
    (sourceId: string, targetId: string) => {
      // Find all relations between these two nodes (in both directions)
      const relations = roleLinks.filter((link) => {
        const linkSourceId = link.source;
        const linkTargetId = link.target;
        return (
          (linkSourceId === sourceId && linkTargetId === targetId) ||
          (linkSourceId === targetId && linkTargetId === sourceId)
        );
      });

      const sourceNode = roles.find((n) => n.id === sourceId);
      const targetNode = roles.find((n) => n.id === targetId);

      setSelectedRelationPair({
        sourceId,
        targetId,
        sourceName: sourceNode?.name || sourceId,
        targetName: targetNode?.name || targetId,
        relations,
      });

      const next = writeUrlGlobalContext(searchParams, {
        tab: "network",
        juanRange,
        yearRange: timeRange,
        focusRoleId: focusNodeId ?? undefined,
        selection: { type: "relationPair", sourceId, targetId },
      });
      setSearchParams(next, { replace: false });
    },
    [
      roleLinks,
      roles,
      searchParams,
      setSearchParams,
      juanRange,
      timeRange,
      focusNodeId,
    ],
  );

  // Filter events by time range if needed
  const filteredEvents = useMemo(
    () => eventsInYears(timelineEvents, timeRange),
    [timelineEvents, timeRange],
  );

  const filteredLocations = locations;

  // Handler for clicking a location name (from detail panels) - opens location detail
  const handleLocationNameClick = useCallback(
    (locationName: string) => {
      // Find the location by name
      const loc = Object.values(kb?.locations ?? {}).find(
        (l) =>
          l.canonical_name === locationName ||
          l.all_names?.includes(locationName),
      );
      if (loc) {
        setSelectedLocation(loc);
        // Also update URL so the selection persists and doesn't get cleared by URL sync effect
        const next = writeUrlGlobalContext(searchParams, {
          tab: activeTab,
          juanRange,
          yearRange: timeRange,
          focusRoleId: focusNodeId ?? undefined,
          selection: { type: "location", id: loc.id },
        });
        setSearchParams(next, { replace: false });
      }
    },
    [
      kb,
      searchParams,
      setSearchParams,
      activeTab,
      juanRange,
      timeRange,
      focusNodeId,
    ],
  );

  // Handler for clicking an event (from RoleDetail/RelationDetail) - opens event detail
  const handleEventDetailClick = useCallback(
    (event: TimelineEventUnified) => {
      setSelectedEvent(event);
      const next = writeUrlGlobalContext(searchParams, {
        tab: activeTab,
        juanRange,
        yearRange: timeRange,
        focusRoleId: focusNodeId ?? undefined,
        selection: { type: "event", id: event.id },
      });
      setSearchParams(next, { replace: false });
    },
    [
      searchParams,
      setSearchParams,
      activeTab,
      juanRange,
      timeRange,
      focusNodeId,
    ],
  );

  const availableRoleIds = useMemo(
    () => new Set(roles.map((r) => r.id)),
    [roles],
  );

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
    { id: "timeline", label: "时间轴", icon: "◷" },
    { id: "network", label: "关系网络", icon: "⌘" },
    { id: "power", label: "势力人物", icon: "◫" },
    { id: "locations", label: "地点", icon: "⌖" },
    { id: "map", label: "地图", icon: "◇" },
  ];

  return (
    <div className="min-h-screen bg-[#faf8f5]">
      <a href="#explore-content" className="skip-link">
        跳到阅读内容
      </a>
      <header className="site-header">
        <div className="site-heading">
          <div>
            <p className="eyebrow">史事 · 人物 · 山河</p>
            <h1>
              资治通鉴<span>交互阅读</span>
            </h1>
          </div>
          <div className="header-links">
            <a href="https://jy0284.github.io/zizhitongjian/">文白对照 ↗</a>
            <GitHubRepoBadge
              repoFullName="JY0284/zizhitongjian"
              repoUrl="https://github.com/JY0284/zizhitongjian"
            />
          </div>
        </div>
        <div className="site-intro">
          <p>沿时间读史，循人物看关系。</p>
          <span className="data-badge">
            {kb?.data_mode === "demo" ? "样例预览" : "前五卷已收录"} ·{" "}
            {kb?.data_coverage?.reduce(
              (sum, item) => sum + item.processed,
              0,
            ) ?? 0}{" "}
            段记载
          </span>
          <details className="data-notes">
            <summary>数据说明</summary>
            <div>
              <p>抽取模型：{kb?.extraction_models?.join(" · ")}</p>
              <p>{kb?.data_notice}</p>
              <p>
                {kb?.data_coverage
                  ?.map(
                    (item) => `卷${item.juan} ${item.processed}/${item.total}`,
                  )
                  .join(" · ")}
              </p>
            </div>
          </details>
        </div>
      </header>

      <main className="site-main">
        <button
          className="mobile-filter-button"
          aria-expanded={filtersOpen}
          aria-controls="reading-filters"
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          阅读范围 · 卷 {juanRange[0]}–{juanRange[1]}{" "}
          <span>{filtersOpen ? "收起 −" : "筛选 +"}</span>
        </button>
        <div className="explore-layout">
          <aside
            id="reading-filters"
            className={`reading-sidebar ${filtersOpen ? "is-open" : ""}`}
          >
            <FilterControls
              key={`${juanRange.join(":")}|${timeRange.join(":")}`}
              juanRange={juanRange}
              timeRange={timeRange}
              maxJuan={294}
              onPreset={applyRange}
              onApply={(juans, years) => {
                let nextJuans = juans;
                let nextYears = years;
                const juansChanged = juans.some(
                  (value, i) => value !== juanRange[i],
                );
                const yearsChanged = years.some(
                  (value, i) => value !== timeRange[i],
                );
                if (syncJuanYear && juansChanged && !yearsChanged)
                  nextYears = deriveYearRangeFromJuanRange(juans) ?? years;
                if (syncJuanYear && yearsChanged && !juansChanged)
                  nextJuans = deriveJuanRangeFromYearRange(years, 294) ?? juans;
                applyRange(nextJuans, nextYears);
              }}
              syncJuanYear={syncJuanYear}
              syncAvailable={Boolean(juanYearIndex?.juan_start_year)}
              onSyncJuanYearChange={setSyncJuanYear}
            />

            {/* Stats */}
            <div className="surface scope-stats">
              <h3 className="text-sm font-bold text-[#2c1810] mb-3">
                这段范围内
              </h3>
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
                  <span className="font-semibold">
                    {filteredLocations.length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">人物间关系：</span>
                  <span className="font-semibold">{roleLinks.length}</span>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                关系网仅显示人物之间的关系及相连人物。国家、组织和未连线人物不计入此处。
              </p>
            </div>
          </aside>

          {/* Main content */}
          <div id="explore-content" className="explore-content">
            {/* Tabs */}
            <div className="view-navigation">
              <div className="view-tabs" role="tablist" aria-label="探索方式">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    role="tab"
                    aria-selected={activeTab === tab.id}
                    aria-controls="explore-panel"
                    tabIndex={activeTab === tab.id ? 0 : -1}
                    onKeyDown={(event) => {
                      const elements = Array.from(
                        event.currentTarget.parentElement!.querySelectorAll<HTMLButtonElement>(
                          '[role="tab"]',
                        ),
                      );
                      const current = elements.indexOf(event.currentTarget);
                      const index =
                        event.key === "ArrowRight"
                          ? (current + 1) % elements.length
                          : event.key === "ArrowLeft"
                            ? (current + elements.length - 1) % elements.length
                            : event.key === "Home"
                              ? 0
                              : event.key === "End"
                                ? elements.length - 1
                                : -1;
                      if (index >= 0) {
                        event.preventDefault();
                        elements[index].focus();
                        elements[index].click();
                      }
                    }}
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
                      next.delete("mapLoc");
                      setSearchParams(next, { replace: false });
                    }}
                    className={
                      activeTab === tab.id ? "view-tab is-active" : "view-tab"
                    }
                  >
                    <span aria-hidden="true">{tab.icon}</span>
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab content */}
            <div
              id="explore-panel"
              role="tabpanel"
              aria-label={tabs.find((tab) => tab.id === activeTab)?.label}
              className="space-y-4"
            >
              {juanRange[1] > 5 && (
                <div className="coverage-note">
                  当前结构化数据仅覆盖前五卷，卷六及以后可在文白对照中阅读。
                  <button onClick={() => applyRange([1, 5], [null, null])}>
                    返回前五卷
                  </button>
                </div>
              )}
              {activeTab === "timeline" && (
                <Timeline
                  events={filteredEvents}
                  aliasGroups={roleAliasGroups}
                  onEventClick={(ev) => {
                    setSelectedEvent(ev);
                    const next = writeUrlGlobalContext(searchParams, {
                      tab: "timeline",
                      juanRange,
                      yearRange: timeRange,
                      focusRoleId: focusNodeId ?? undefined,
                      selection: { type: "event", id: ev.id },
                    });
                    setSearchParams(next, { replace: false });
                  }}
                />
              )}

              {activeTab === "network" && (
                <NetworkGraph
                  nodes={roles}
                  links={roleLinks}
                  onNodeClick={(role) => {
                    setSelectedRole(role);
                    const next = writeUrlGlobalContext(searchParams, {
                      tab: "network",
                      juanRange,
                      yearRange: timeRange,
                      focusRoleId: focusNodeId ?? undefined,
                      selection: { type: "role", id: role.id },
                    });
                    setSearchParams(next, { replace: false });
                  }}
                  onLinkClick={handleLinkClick}
                  focusNodeId={focusNodeId}
                  onFocusNodeHandled={() => setFocusNodeId(null)}
                />
              )}

              {activeTab === "power" && (
                <PowerChart
                  data={powerDistributionInRange}
                  roles={roles}
                  onRoleClick={(id) =>
                    setSearchParams(
                      writeUrlGlobalContext(searchParams, {
                        tab: "power",
                        juanRange,
                        yearRange: timeRange,
                        selection: { type: "role", id },
                      }),
                      { replace: false },
                    )
                  }
                />
              )}

              {activeTab === "locations" && (
                <LocationsView
                  locations={filteredLocations}
                  onLocationClick={(loc) => {
                    setSelectedLocation(loc);
                    const next = writeUrlGlobalContext(searchParams, {
                      tab: "locations",
                      juanRange,
                      yearRange: timeRange,
                      focusRoleId: focusNodeId ?? undefined,
                      selection: { type: "location", id: loc.id },
                    });
                    setSearchParams(next, { replace: false });
                  }}
                  onNavigateToMap={(loc) => handleNavigateToMap(loc.id)}
                />
              )}

              {activeTab === "map" && (
                <Suspense
                  fallback={<p className="p-6 text-gray-500">正在加载地图…</p>}
                >
                  <MapView
                    locations={filteredLocations}
                    eventsInRange={filteredEvents}
                    selectedRole={selectedRole}
                    selectedEvent={selectedEvent}
                    focusLocationId={mapFocusLocationId}
                    onLocationClick={(loc) => {
                      setSearchParams(
                        writeUrlGlobalContext(searchParams, {
                          tab: "map",
                          juanRange,
                          yearRange: timeRange,
                          selection: { type: "location", id: loc.id },
                        }),
                        { replace: false },
                      );
                    }}
                    onFocusLocation={(id) => {
                      const next = new URLSearchParams(searchParams);
                      if (id) next.set("mapLoc", id);
                      else next.delete("mapLoc");
                      setSearchParams(next, { replace: false });
                    }}
                  />
                </Suspense>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="site-footer">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          资治通鉴 · 以原文为据，理解历史的不同侧面
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
        relatedEvents={
          selectedRole
            ? filteredEvents.filter((e) =>
                e.participants.some(
                  (p) =>
                    p === selectedRole.name ||
                    selectedRole.aliases?.includes(p),
                ),
              )
            : []
        }
        kb={kb}
        availableRoleIds={availableRoleIds}
      />
      {selectedLocation && (
        <LocationDetail
          location={selectedLocation}
          relatedEvents={filteredEvents.filter(
            (e) => e.location === selectedLocation.canonical_name,
          )}
          relatedRoles={selectedLocation.associated_entities || []}
          onEventClick={handleEventDetailClick}
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
          onNavigateToMap={
            hasMapPosition(selectedLocation)
              ? () => handleNavigateToMap(selectedLocation.id)
              : undefined
          }
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
            return filteredEvents.filter(
              (e) =>
                e.participants.some((p) => sourceNames.has(p)) &&
                e.participants.some((p) => targetNames.has(p)),
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
