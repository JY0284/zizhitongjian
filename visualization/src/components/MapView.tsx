import { referenceCoordinates } from "../utils/mapCoordinates";
import { useMemo, useEffect, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import type {
  TimelineEventUnified,
  RoleNodeUnified,
  UnifiedLocation,
} from "../types/unified";

interface MapViewProps {
  locations: UnifiedLocation[];
  eventsInRange: TimelineEventUnified[];
  selectedRole: RoleNodeUnified | null;
  selectedEvent: TimelineEventUnified | null;
  focusLocationId?: string | null;
  onFocusLocation?: (id: string | null) => void;
  onLocationClick?: (location: UnifiedLocation) => void;
}

type TrajectoryPoint = {
  id: string;
  name: string;
  lng: number;
  lat: number;
  eventId: string;
  eventName: string;
  year: number | null;
};

function ResizeMap() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() =>
      map.invalidateSize({ pan: true, animate: false }),
    );
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

// Auto-fit map bounds when locations change
function FitBounds({ locations }: { locations: UnifiedLocation[] }) {
  const map = useMap();
  const fittedRef = useRef("");

  useEffect(() => {
    const withCoords = locations.filter((loc) => loc.coordinates);
    if (withCoords.length === 0) return;
    const key = withCoords
      .map((loc) => `${loc.id}:${loc.coordinates}`)
      .join("|");
    if (fittedRef.current === key) return;

    const bounds = withCoords.map(
      (loc) => [loc.coordinates![1], loc.coordinates![0]] as [number, number],
    );
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 8, animate: false });
    fittedRef.current = key;
  }, [locations, map]);

  return null;
}

function FocusLocation({ location }: { location: UnifiedLocation | null }) {
  const map = useMap();
  useEffect(() => {
    if (!location?.coordinates) return;
    const [lng, lat] = location.coordinates;
    // Zoom in enough to make the target obvious, but not too close.
    map.setView([lat, lng], Math.max(map.getZoom(), 8), { animate: false });
  }, [location, map]);
  return null;
}

export function MapView({
  locations,
  eventsInRange,
  selectedRole,
  selectedEvent,
  focusLocationId,
  onLocationClick,
  onFocusLocation,
}: MapViewProps) {
  const mapRef = useRef<LeafletMap | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [showReferences, setShowReferences] = useState(true);
  const [selection, setSelection] = useState<{
    focusId: string | null | undefined;
    location: UnifiedLocation | null;
  }>({ focusId: undefined, location: null });

  const byName = useMemo(() => {
    const m = new Map<string, UnifiedLocation>();
    for (const loc of locations) m.set(loc.canonical_name, loc);
    return m;
  }, [locations]);

  const verifiedLocations = useMemo(
    () => locations.filter((loc) => loc.coordinates),
    [locations],
  );
  const referenceLocations = useMemo(
    () =>
      locations.flatMap((loc) => {
        const coords = referenceCoordinates(loc);
        return coords ? [{ ...loc, coordinates: coords }] : [];
      }),
    [locations],
  );
  const withCoords = useMemo(
    () => [...verifiedLocations, ...(showReferences ? referenceLocations : [])],
    [verifiedLocations, referenceLocations, showReferences],
  );

  const focusLocation = useMemo(() => {
    if (!focusLocationId) return null;
    return withCoords.find((l) => l.id === focusLocationId) ?? null;
  }, [withCoords, focusLocationId]);

  const selectedId =
    selection.focusId === focusLocationId
      ? selection.location?.id
      : focusLocation?.id;
  const selectedLocation =
    withCoords.find((loc) => loc.id === selectedId) ?? null;
  const setSelectedLocation = (location: UnifiedLocation | null) => {
    setSelection({ focusId: focusLocationId, location });
    onFocusLocation?.(location?.id ?? null);
  };

  // Compute trajectory for selected role/event
  const trajectory = useMemo((): TrajectoryPoint[] => {
    if (!selectedRole && !selectedEvent) return [];

    const candidates = selectedEvent
      ? [selectedEvent]
      : eventsInRange.filter((e) =>
          e.participants?.includes(selectedRole!.name),
        );

    const points: TrajectoryPoint[] = [];
    for (const ev of candidates) {
      if (ev.timeNumeric === null) continue;
      if (!ev.location) continue;
      const loc = byName.get(ev.location);
      if (!loc?.coordinates) continue;
      points.push({
        id: `${ev.id}:${loc.id}`,
        name: loc.canonical_name,
        lng: loc.coordinates[0],
        lat: loc.coordinates[1],
        eventId: ev.id,
        eventName: ev.name,
        year: ev.timeNumeric,
      });
    }

    points.sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
    return points;
  }, [selectedRole, selectedEvent, eventsInRange, byName]);

  const trajectoryLine = useMemo(() => {
    if (trajectory.length < 2) return null;
    return trajectory.map((p) => [p.lat, p.lng] as [number, number]);
  }, [trajectory]);

  // Compute center from all locations with coordinates
  const { center, zoom } = useMemo(() => {
    if (withCoords.length === 0) {
      // Fallback: central China
      return { center: [34.5, 108.9] as [number, number], zoom: 5 };
    }
    let sumLat = 0,
      sumLng = 0;
    for (const loc of withCoords) {
      sumLng += loc.coordinates![0];
      sumLat += loc.coordinates![1];
    }
    const avgLat = sumLat / withCoords.length;
    const avgLng = sumLng / withCoords.length;
    return { center: [avgLat, avgLng] as [number, number], zoom: 5 };
  }, [withCoords]);

  return (
    <section className="surface map-view" aria-label="历史地图">
      <div className="section-heading">
        <div>
          <p className="eyebrow">山河之间，辨认古今</p>
          <h2>历史地图</h2>
        </div>
        <div className="count-label">
          {verifiedLocations.length} 个已核验 · {referenceLocations.length}{" "}
          个现代参考 · 共 {locations.length} 个地点
        </div>
      </div>

      {referenceLocations.length > 0 && (
        <div className="map-notice">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showReferences}
              onChange={(e) => setShowReferences(e.target.checked)}
            />
            显示现代位置参考（橙色空心点）
          </label>
          <p className="mt-1 text-xs">
            高德匹配今地名的参考位置，可能是行政区中心；古今对应关系及遗址位置尚待核验。底图为现代地图。
          </p>
        </div>
      )}

      {withCoords.length === 0 && (
        <p className="mb-4 rounded bg-amber-50 p-3 text-sm text-amber-900">
          {locations.length
            ? "当前地点尚无经过核验的坐标。可在“地点”页查看原文、今地名和相关人物；地图暂不显示标记。"
            : "当前筛选没有地点数据，请调整卷数或年份。"}
        </p>
      )}

      <div className="map-controls">
        <label className="inline-select">
          定位地点
          <select
            aria-label="定位地点"
            value={selectedLocation?.id ?? ""}
            onChange={(event) =>
              setSelectedLocation(
                withCoords.find((loc) => loc.id === event.target.value) ?? null,
              )
            }
          >
            <option value="">选择一个地点</option>
            {withCoords.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.canonical_name} ·{" "}
                {loc.modern_name ||
                  loc.geocoding?.matched_address ||
                  "坐标已核验"}
              </option>
            ))}
          </select>
        </label>
        <button
          className="quiet-button"
          onClick={() => {
            setSelectedLocation(null);
            if (withCoords.length)
              mapRef.current?.fitBounds(
                withCoords.map(
                  (loc) =>
                    [loc.coordinates![1], loc.coordinates![0]] as [
                      number,
                      number,
                    ],
                ),
                { padding: [30, 30], maxZoom: 8 },
              );
          }}
        >
          查看全部位置
        </button>
      </div>
      <div className="map-layout">
        {/* Map container */}
        <div className="map-canvas">
          <MapContainer
            center={center}
            zoom={zoom}
            zoomAnimation={false}
            className="w-full h-full"
            ref={mapRef}
          >
            {/* OpenStreetMap tiles - neutral, shows rivers/mountains, no border issues */}
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <ResizeMap />
            <FitBounds locations={withCoords} />
            <FocusLocation location={focusLocation} />

            {/* Trajectory polyline */}
            {trajectoryLine && (
              <Polyline
                positions={trajectoryLine}
                pathOptions={{
                  color: "#8b4513",
                  weight: 3,
                  opacity: 0.8,
                  dashArray: "8, 4",
                }}
              />
            )}

            {/* Location markers */}
            {withCoords.map((loc) => (
              <CircleMarker
                key={loc.id}
                center={[loc.coordinates![1], loc.coordinates![0]]}
                radius={
                  hoveredId === loc.id || selectedLocation?.id === loc.id
                    ? 9
                    : 6
                }
                pathOptions={{
                  fillColor:
                    loc.geocoding?.status === "needs_review"
                      ? "#f59e0b"
                      : "#c41e3a",
                  color:
                    loc.geocoding?.status === "needs_review"
                      ? "#b45309"
                      : "#8b4513",
                  weight: selectedLocation?.id === loc.id ? 3 : 1,
                  opacity: 1,
                  fillOpacity:
                    loc.geocoding?.status === "needs_review" ? 0.18 : 0.85,
                }}
                eventHandlers={{
                  click: () => setSelectedLocation(loc),
                  mouseover: () => setHoveredId(loc.id),
                  mouseout: () => setHoveredId(null),
                }}
              >
                <Popup>
                  <div className="text-sm">
                    <div className="font-bold text-[#8b4513]">
                      {loc.canonical_name}
                    </div>
                    {loc.modern_name && (
                      <div className="text-gray-600">今：{loc.modern_name}</div>
                    )}
                    {loc.geocoding?.status === "needs_review" && (
                      <div className="text-amber-800">
                        现代参考：{loc.geocoding.matched_address}（
                        {loc.geocoding.match_level ?? "候选"}）· 古址待核验
                      </div>
                    )}
                    {loc.location_type && (
                      <div className="text-gray-500 text-xs">
                        {loc.location_type}
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            ))}

            {/* Trajectory waypoints */}
            {trajectory.map((pt, idx) => (
              <CircleMarker
                key={pt.id}
                center={[pt.lat, pt.lng]}
                radius={8}
                pathOptions={{
                  fillColor: "#8b4513",
                  color: "#2c1810",
                  weight: 2,
                  opacity: 1,
                  fillOpacity: 0.95,
                }}
              >
                <Popup>
                  <div className="text-sm">
                    <div className="font-bold text-[#8b4513]">
                      {idx + 1}. {pt.eventName}
                    </div>
                    <div className="text-gray-600">
                      {pt.year !== null
                        ? `${pt.year < 0 ? `前${Math.abs(pt.year)}` : pt.year}年`
                        : "未知年"}
                    </div>
                    <div className="text-gray-500 text-xs">@ {pt.name}</div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        {/* Detail panel for selected location */}
        {selectedLocation && (
          <div className="map-details">
            <div className="flex justify-between items-start mb-3">
              <h4 className="font-bold text-[#8b4513] text-lg">
                {selectedLocation.canonical_name}
              </h4>
              <button
                aria-label="关闭地点面板"
                onClick={() => setSelectedLocation(null)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ×
              </button>
            </div>

            {selectedLocation.modern_name && (
              <p className="text-sm text-gray-600 mb-2">
                今：{selectedLocation.modern_name}
              </p>
            )}
            {selectedLocation.geocoding?.status === "needs_review" && (
              <p className="text-xs text-amber-800 mb-2">
                高德参考位置：{selectedLocation.geocoding.matched_address}（
                {selectedLocation.geocoding.match_level ?? "候选"}
                ）。古址尚待核验。
              </p>
            )}
            {selectedLocation.location_type && (
              <p className="text-xs text-gray-500 mb-2">
                类型：{selectedLocation.location_type}
              </p>
            )}
            {selectedLocation.description && (
              <p className="text-sm text-gray-700 mb-4">
                {selectedLocation.description}
              </p>
            )}

            <div className="mt-auto">
              <button
                onClick={() => {
                  // Render-only coordinates must never become verified data in details.
                  const original = locations.find(
                    (loc) => loc.id === selectedLocation.id,
                  );
                  if (original) onLocationClick?.(original);
                }}
                className="primary-button w-full"
              >
                查看详情
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Trajectory indicator */}
      {trajectory.length >= 2 && (
        <div className="mt-3 p-2 bg-[#faf8f5] rounded text-sm text-[#8b4513] flex-shrink-0">
          <span className="font-semibold">轨迹：</span>
          {selectedRole
            ? selectedRole.name
            : selectedEvent
              ? selectedEvent.name
              : ""}{" "}
          ({trajectory.length} 个事件节点)
        </div>
      )}
    </section>
  );
}
