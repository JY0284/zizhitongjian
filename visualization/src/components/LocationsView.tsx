import { hasMapPosition, referenceCoordinates } from '../utils/mapCoordinates';
import { useMemo, useState } from 'react';
import type { UnifiedLocation } from '../types/unified';

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
  const [searchQuery, setSearchQuery] = useState('');

  const { withCoords, withoutCoords } = useMemo(() => {
    const withCoords: UnifiedLocation[] = [];
    const withoutCoords: UnifiedLocation[] = [];
    for (const loc of locations) {
      if (loc.coordinates) withCoords.push(loc);
      else withoutCoords.push(loc);
    }
    return { withCoords, withoutCoords };
  }, [locations]);

  const filteredLocations = useMemo(() => {
    if (!searchQuery.trim()) return locations;
    const query = searchQuery.trim().toLowerCase();
    return locations.filter((loc) => {
      if (loc.canonical_name.toLowerCase().includes(query)) return true;
      if (loc.modern_name?.toLowerCase().includes(query)) return true;
      if (loc.all_names?.some((n) => n.toLowerCase().includes(query))) return true;
      if (loc.description?.toLowerCase().includes(query)) return true;
      return false;
    });
  }, [locations, searchQuery]);

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[#2c1810]">地点列表</h3>
        <div className="text-sm text-gray-500">
          {withCoords.length} 个已核验 · {withoutCoords.filter(loc => referenceCoordinates(loc)).length} 个现代参考 · 共 {locations.length} 个地点
        </div>
      </div>

      {/* Search input */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="搜索地点..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-2 border border-[#d4c5b5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8b4513] focus:border-transparent"
        />
        {searchQuery && (
          <div className="text-xs text-gray-500 mt-1">
            找到 {filteredLocations.length} 个结果
          </div>
        )}
      </div>

      <div className="space-y-2 max-h-[520px] overflow-y-auto">
        {filteredLocations.map((loc) => (
          <div
            key={loc.id}
            className="p-3 border border-[#d4c5b5] rounded-lg hover:bg-[#faf8f5] cursor-pointer transition-colors"
            onClick={() => onLocationClick?.(loc)}
          >
            <div className="flex justify-between items-start">
              <h4 className="font-semibold text-[#8b4513]">{loc.canonical_name}</h4>
              <div className="flex gap-1 items-center">
                {loc.location_type && (
                  <span className="text-xs px-2 py-1 bg-[#d4a574] text-white rounded">{loc.location_type}</span>
                )}
                {hasMapPosition(loc) && onNavigateToMap && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onNavigateToMap(loc);
                    }}
                    className="text-xs px-2 py-1 bg-[#faf8f5] border border-[#d4c5b5] text-[#8b4513] rounded hover:bg-white transition-colors"
                    title={loc.coordinates ? '在地图中查看' : '查看现代参考位置（古址待核验）'}
                  >
                    {loc.coordinates ? '地图' : '参考地图'}
                  </button>
                )}
              </div>
            </div>
            {loc.modern_name && <p className="text-sm text-gray-500 mt-1">今：{loc.modern_name}</p>}
            {loc.description && <p className="text-sm text-gray-700 mt-1 line-clamp-2">{loc.description}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
