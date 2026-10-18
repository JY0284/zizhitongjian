import { useState, useMemo } from 'react';
import type { TimelineEventUnified } from '../types/unified';

interface TimelineProps {
  events: TimelineEventUnified[];
  onEventClick?: (event: TimelineEventUnified) => void;
}

interface TimePoint {
  year: number;
  yearLabel: string;
  events: TimelineEventUnified[];
}

export function Timeline({ events, onEventClick }: TimelineProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  // Filter events by search query
  const filteredEvents = useMemo(() => {
    if (!searchQuery) return events;
    const query = searchQuery.toLowerCase();
    return events.filter(e => 
      e.name.toLowerCase().includes(query) ||
      e.description?.toLowerCase().includes(query) ||
      e.participants?.some(p => p.toLowerCase().includes(query))
    );
  }, [events, searchQuery]);

  // Group events by year into time points
  const timePoints = useMemo((): TimePoint[] => {
    const byYear = new Map<number, TimelineEventUnified[]>();
    
    for (const event of filteredEvents) {
      if (event.timeNumeric === null) continue;
      const year = event.timeNumeric;
      if (!byYear.has(year)) {
        byYear.set(year, []);
      }
      byYear.get(year)!.push(event);
    }

    return Array.from(byYear.entries())
      .map(([year, evts]) => ({
        year,
        yearLabel: year < 0 ? `前${Math.abs(year)}年` : `${year}年`,
        events: evts,
      }))
      .sort((a, b) => a.year - b.year);
  }, [filteredEvents]);

  const selectedTimePoint = timePoints.find(point => point.year === selectedYear) ?? null;

  // Events without time info
  const eventsWithoutTime = useMemo(() => {
    return filteredEvents.filter(e => e.timeNumeric === null);
  }, [filteredEvents]);

  return (
    <div className="w-full bg-white rounded-lg shadow-md p-4">
      <p className="mb-3 text-xs text-gray-500">时间轴展示已抽取的明确事件；无法确定年份的引用旧事单列，其他人物互动可在关系网络中查看。</p>
      {/* Search bar */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索事件名称、描述或参与者..."
            className="w-full px-4 py-2 pl-10 border border-[#d4c5b5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8b4513] focus:border-transparent"
          />
          <span className="absolute left-3 top-2.5 text-gray-400">搜索</span>
        </div>
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="px-3 py-2 text-sm text-[#8b4513] hover:bg-[#faf8f5] rounded-lg transition-colors"
          >
            清除
          </button>
        )}
        <div className="text-sm text-gray-500">
          {filteredEvents.length} / {events.length} 事件
        </div>
      </div>

      {/* Main layout: timeline on left, detail panel on right */}
      <div className="flex gap-4" style={{ minHeight: '500px' }}>
        {/* Timeline */}
        <div className="flex-1 overflow-y-auto max-h-[600px] pr-2">
          {timePoints.length === 0 && eventsWithoutTime.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              {searchQuery ? '没有匹配的事件' : '暂无事件数据'}
            </div>
          ) : (
            <div className="relative">
              {/* Vertical timeline line */}
              <div className="absolute left-[60px] top-0 bottom-0 w-0.5 bg-[#d4c5b5]" />

              {/* Time points */}
              {timePoints.map((tp) => (
                <div
                  key={tp.year}
                  className={`relative flex items-start mb-3 cursor-pointer group ${
                    selectedTimePoint?.year === tp.year ? 'bg-[#faf8f5] rounded-lg -mx-2 px-2 py-1' : ''
                  }`}
                  onClick={() => setSelectedYear(selectedTimePoint?.year === tp.year ? null : tp.year)}
                >
                  {/* Year label */}
                  <div className="w-[55px] flex-shrink-0 text-right pr-3">
                    <span className={`text-sm font-medium ${
                      selectedTimePoint?.year === tp.year ? 'text-[#8b4513]' : 'text-gray-600'
                    }`}>
                      {tp.yearLabel}
                    </span>
                  </div>

                  {/* Timeline dot */}
                  <div className={`relative z-10 w-4 h-4 rounded-full flex-shrink-0 mt-0.5 transition-all ${
                    selectedTimePoint?.year === tp.year 
                      ? 'bg-[#8b4513] scale-125' 
                      : 'bg-[#c41e3a] group-hover:scale-110'
                  }`}>
                    {tp.events.length > 1 && (
                      <span className="absolute -top-1 -right-1 bg-[#8b4513] text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center font-bold">
                        {tp.events.length}
                      </span>
                    )}
                  </div>

                  {/* Event preview */}
                  <div className="ml-4 flex-1 min-w-0">
                    <div className={`text-sm font-medium truncate ${
                      selectedTimePoint?.year === tp.year ? 'text-[#8b4513]' : 'text-[#2c1810]'
                    }`}>
                      {tp.events.length === 1 
                        ? tp.events[0].name 
                        : `${tp.events[0].name} 等 ${tp.events.length} 个事件`
                      }
                    </div>
                    {tp.events.length === 1 && tp.events[0].location && (
                      <div className="text-xs text-gray-500 truncate">
                        地点：{tp.events[0].location}
                      </div>
                    )}
                  </div>

                  {/* Expand indicator */}
                  <div className={`text-gray-400 transition-transform ${
                    selectedTimePoint?.year === tp.year ? 'rotate-90' : ''
                  }`}>
                    ›
                  </div>
                </div>
              ))}

              {/* Events without time */}
              {eventsWithoutTime.length > 0 && (
                <div className="mt-6 pt-4 border-t border-[#d4c5b5]">
                  <div className="text-sm text-gray-500 mb-2">年份待核验 ({eventsWithoutTime.length})</div>
                  {eventsWithoutTime.map((event) => (
                    <div
                      key={event.id}
                      className="ml-[75px] mb-2 p-2 bg-gray-50 rounded cursor-pointer hover:bg-[#faf8f5] transition-colors"
                      onClick={() => onEventClick?.(event)}
                    >
                      <div className="text-sm font-medium text-[#2c1810]">{event.name}</div>
                      {event.time && <div className="text-xs text-gray-500">抽取时间：{event.time}</div>}
                      {event.location && (
                        <div className="text-xs text-gray-500">地点：{event.location}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Detail panel - shows events at selected time point */}
        <div className="w-80 flex-shrink-0 border-l border-[#d4c5b5] pl-4">
          {selectedTimePoint ? (
            <div className="h-full flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-bold text-[#8b4513]">
                  {selectedTimePoint.yearLabel}
                </h3>
                <button
                  onClick={() => setSelectedYear(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>
              <div className="text-sm text-gray-500 mb-3">
                {selectedTimePoint.events.length} 个事件
              </div>
              <div className="flex-1 overflow-y-auto space-y-3 max-h-[520px] pr-1">
                {selectedTimePoint.events.map((event) => (
                  <div
                    key={event.id}
                    className="p-3 bg-[#faf8f5] border border-[#d4c5b5] rounded-lg cursor-pointer hover:border-[#8b4513] transition-colors"
                    onClick={() => onEventClick?.(event)}
                  >
                    <div className="font-medium text-[#2c1810] mb-1">{event.name}</div>
                    {event.location && (
                      <div className="text-xs text-gray-600 mb-1">地点：{event.location}</div>
                    )}
                    {event.participants && event.participants.length > 0 && (
                      <div className="text-xs text-gray-500 mb-2">
                        参与者：{event.participants.slice(0, 3).join('、')}
                        {event.participants.length > 3 && ` 等${event.participants.length}人`}
                      </div>
                    )}
                    {event.description && (
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {event.description}
                      </p>
                    )}
                    <div className="mt-2 text-xs text-[#8b4513]">
                      点击查看详情 →
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-500 text-sm bg-[#faf8f5] rounded-lg border border-[#d4c5b5]">
              点击左侧时间点查看事件
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="mt-4 pt-3 border-t border-[#d4c5b5] flex items-center gap-6 text-sm text-gray-500">
        <div>
          <span className="font-medium text-[#2c1810]">{timePoints.length}</span> 个时间点
        </div>
        <div>
          <span className="font-medium text-[#2c1810]">{filteredEvents.filter(e => e.timeNumeric !== null).length}</span> 个有时间的事件
        </div>
        {eventsWithoutTime.length > 0 && (
          <div>
            <span className="font-medium text-gray-600">{eventsWithoutTime.length}</span> 个时间不详
          </div>
        )}
      </div>
    </div>
  );
}
