import type { KeyboardEvent } from 'react';

interface FilterControlsProps {
  juanRange: [number, number];
  onJuanRangeChange: (range: [number, number]) => void;
  onJuanRangeCommit: (range: [number, number]) => void;
  maxJuan: number;
  timeRange: [number | null, number | null];
  onTimeRangeChange: (range: [number | null, number | null]) => void;
  onTimeRangeCommit: (range: [number | null, number | null]) => void;

  syncJuanYear: boolean;
  syncAvailable: boolean;
  onSyncJuanYearChange: (enabled: boolean) => void;
  onPreset: (juans: [number, number], years: [number | null, number | null]) => void;
}

export function FilterControls({
  juanRange,
  onJuanRangeChange,
  onJuanRangeCommit,
  maxJuan,
  timeRange,
  onTimeRangeChange,
  onTimeRangeCommit,
  syncJuanYear,
  syncAvailable,
  onSyncJuanYearChange,
  onPreset,
}: FilterControlsProps) {
  const commitJuanOnEnter = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onJuanRangeCommit(juanRange);
    }
  };

  const commitTimeOnEnter = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onTimeRangeCommit(timeRange);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h3 className="text-lg font-bold text-[#2c1810] mb-4">筛选控制</h3>

      {/* Sync policy */}
      <div className="mb-6">
        <label className="flex items-center gap-2 text-sm text-[#2c1810]">
          <input
            type="checkbox"
            checked={syncJuanYear}
            disabled={!syncAvailable}
            onChange={(e) => onSyncJuanYearChange(e.target.checked)}
            className="accent-[#8b4513]"
          />
          <span className={!syncAvailable ? 'text-gray-400' : undefined}>卷↔年份联动</span>
        </label>
        {!syncAvailable && (
          <p className="text-xs text-gray-400 mt-1">缺少 /data/juan_year_index.json，联动不可用</p>
        )}
      </div>

      {/* Juan Range */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-[#8b4513] mb-2">
          卷范围
        </label>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="text-xs text-gray-500">起始卷</label>
            <input
              type="number"
              min={1}
              max={maxJuan}
              value={juanRange[0]}
              onChange={(e) =>
                onJuanRangeChange([parseInt(e.target.value) || 1, juanRange[1]])
              }
              onBlur={() => onJuanRangeCommit(juanRange)}
              onKeyDown={commitJuanOnEnter}
              className="w-full mt-1 px-3 py-2 border border-[#d4c5b5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8b4513]"
            />
          </div>
          <span className="text-gray-400 mt-6">—</span>
          <div className="flex-1">
            <label className="text-xs text-gray-500">结束卷</label>
            <input
              type="number"
              min={1}
              max={maxJuan}
              value={juanRange[1]}
              onChange={(e) =>
                onJuanRangeChange([juanRange[0], parseInt(e.target.value) || maxJuan])
              }
              onBlur={() => onJuanRangeCommit(juanRange)}
              onKeyDown={commitJuanOnEnter}
              className="w-full mt-1 px-3 py-2 border border-[#d4c5b5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8b4513]"
            />
          </div>
        </div>
        <input
          type="range"
          min={1}
          max={maxJuan}
          value={juanRange[1]}
          onChange={(e) =>
            onJuanRangeChange([juanRange[0], parseInt(e.target.value)])
          }
          onMouseUp={() => onJuanRangeCommit(juanRange)}
          onTouchEnd={() => onJuanRangeCommit(juanRange)}
          className="w-full mt-2 accent-[#8b4513]"
        />
      </div>

      {/* Time Range */}
      <div>
        <label className="block text-sm font-semibold text-[#8b4513] mb-2">
          时间范围（年，BCE 为负）
        </label>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="text-xs text-gray-500">起始年（如：-403 或 116）</label>
            <input
              type="number"
              placeholder="不限"
              value={timeRange[0] !== null ? timeRange[0] : ''}
              onChange={(e) => {
                const val = e.target.value ? parseInt(e.target.value) : null;
                onTimeRangeChange([val, timeRange[1]]);
              }}
              onBlur={() => onTimeRangeCommit(timeRange)}
              onKeyDown={commitTimeOnEnter}
              className="w-full mt-1 px-3 py-2 border border-[#d4c5b5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8b4513]"
            />
          </div>
          <span className="text-gray-400 mt-6">—</span>
          <div className="flex-1">
            <label className="text-xs text-gray-500">结束年（如：-368 或 125）</label>
            <input
              type="number"
              placeholder="不限"
              value={timeRange[1] !== null ? timeRange[1] : ''}
              onChange={(e) => {
                const val = e.target.value ? parseInt(e.target.value) : null;
                onTimeRangeChange([timeRange[0], val]);
              }}
              onBlur={() => onTimeRangeCommit(timeRange)}
              onKeyDown={commitTimeOnEnter}
              className="w-full mt-1 px-3 py-2 border border-[#d4c5b5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8b4513]"
            />
          </div>
        </div>
      </div>

      {/* Quick filters */}
      <div className="mt-4">
        <label className="block text-sm font-semibold text-[#8b4513] mb-2">
          快速筛选
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              onPreset([1, 1], [null, null]);
            }}
            className="px-3 py-1 text-sm border border-[#8b4513] text-[#8b4513] rounded-full hover:bg-[#8b4513] hover:text-white transition-colors"
          >
            第一卷
          </button>
          <button
            onClick={() => onPreset([1, 5], [null, null])}
            className="px-3 py-1 text-sm border border-[#8b4513] text-[#8b4513] rounded-full hover:bg-[#8b4513] hover:text-white transition-colors"
          >
            前五卷
          </button>
          <button
            onClick={() => {
              onPreset([1, maxJuan], [-500, -400]);
            }}
            className="px-3 py-1 text-sm border border-[#8b4513] text-[#8b4513] rounded-full hover:bg-[#8b4513] hover:text-white transition-colors"
          >
            战国初期
          </button>
          <button
            onClick={() => {
              onPreset([1, maxJuan], [null, null]);
            }}
            className="px-3 py-1 text-sm border border-[#8b4513] text-[#8b4513] rounded-full hover:bg-[#8b4513] hover:text-white transition-colors"
          >
            重置
          </button>
        </div>
      </div>
    </div>
  );
}
