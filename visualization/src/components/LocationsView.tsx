import { useMemo, useState } from "react";
import { hasMapPosition, referenceCoordinates } from "../utils/mapCoordinates";
import type { UnifiedLocation } from "../types/unified";
interface LocationsViewProps {
  locations: UnifiedLocation[];
  onLocationClick?: (location: UnifiedLocation) => void;
  onNavigateToMap?: (location: UnifiedLocation) => void;
}
export function LocationsView({
  locations,
  onLocationClick,
  onNavigateToMap,
}: LocationsViewProps) {
  const [query, setQuery] = useState("");
  const [mappedOnly, setMappedOnly] = useState(false);
  const [limit, setLimit] = useState(24);
  const mappedCount = locations.filter(hasMapPosition).length;
  const filtered = useMemo(
    () =>
      locations.filter(
        (loc) =>
          (!mappedOnly || hasMapPosition(loc)) &&
          [
            loc.canonical_name,
            loc.modern_name,
            loc.description,
            ...(loc.all_names || []),
          ].some((value) => value?.includes(query.trim())),
      ),
    [locations, query, mappedOnly],
  );
  return (
    <section className="surface locations-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">辨古今，寻地名</p>
          <h2>历史地点</h2>
        </div>
        <span className="count-label">{filtered.length} 个地点</span>
      </div>
      <label className="search-field">
        <span>查找地点</span>
        <input
          type="search"
          value={query}
          placeholder="古地名、今地名或别称"
          onChange={(e) => {
            setQuery(e.target.value);
            setLimit(24);
          }}
        />
      </label>
      <div className="segmented">
        <button
          aria-pressed={!mappedOnly}
          onClick={() => {
            setMappedOnly(false);
            setLimit(24);
          }}
        >
          全部地点 · {locations.length}
        </button>
        <button
          aria-pressed={mappedOnly}
          onClick={() => {
            setMappedOnly(true);
            setLimit(24);
          }}
        >
          可看地图 · {mappedCount}
        </button>
      </div>
      <p className="context-note">
        地点描述综合已收录记载。现代参考位置可能是行政区中心，不等同于古代遗址。
      </p>
      {!filtered.length && (
        <div className="empty-state">
          <h3>没有匹配的地点</h3>
          <p>试试地名的其他写法，或调整阅读范围。</p>
          <button
            className="quiet-button"
            onClick={() => {
              setQuery("");
              setMappedOnly(false);
            }}
          >
            清除地点筛选
          </button>
        </div>
      )}
      <div className="location-grid">
        {filtered.slice(0, limit).map((loc) => (
          <article className="location-card" key={loc.id}>
            <button
              className="location-main"
              onClick={() => onLocationClick?.(loc)}
            >
              <span className="location-card-title">
                <strong>{loc.canonical_name}</strong>
                <span>{loc.location_type || "地点"}</span>
              </span>
              {loc.modern_name && (
                <span className="modern-name">今 · {loc.modern_name}</span>
              )}
              <p>{loc.description || "打开详情查看相关记载。"}</p>
              <span className="location-volume">
                卷 {loc.juans_appeared.join("、")} · 阅读记载 ↗
              </span>
            </button>
            {hasMapPosition(loc) && onNavigateToMap && (
              <button
                className="location-map-button"
                onClick={() => onNavigateToMap(loc)}
                aria-label={`在地图查看${loc.canonical_name}`}
              >
                {referenceCoordinates(loc) ? "现代参考位置" : "已核验位置"} →
              </button>
            )}
          </article>
        ))}
      </div>
      {filtered.length > limit && (
        <button
          className="quiet-button load-more"
          onClick={() => setLimit((value) => value + 24)}
        >
          显示更多地点 · 还有 {filtered.length - limit} 个
        </button>
      )}
    </section>
  );
}
