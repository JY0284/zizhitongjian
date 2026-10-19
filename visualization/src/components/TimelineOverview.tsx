import { useEffect, useRef, useState } from "react";
import type { TimelineEventUnified } from "../types/unified";
import {
  clampYearWindow,
  formatYear,
  timelineBuckets,
} from "../utils/exploration";

interface Props {
  years: [number, TimelineEventUnified[]][];
  selectedYear?: number;
  onSelect: (year: number) => void;
}

/** The overview changes only its viewport; the readable year list stays complete. */
export function TimelineOverview({ years, selectedYear, onSelect }: Props) {
  const min = years[0][0],
    max = years[years.length - 1][0] + 1;
  const [window, setWindow] = useState<[number, number]>([min, max]);
  const [width, setWidth] = useState(600);
  const host = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    x: number;
    start: number;
    span: number;
    moved: boolean;
  } | null>(null);
  const [start, end] = clampYearWindow(
    window[0],
    window[1] - window[0],
    min,
    max,
  );
  const span = end - start;
  const buckets = timelineBuckets(years, start, end, Math.floor(width / 24));
  const total = buckets.reduce((sum, bucket) => sum + bucket.count, 0);
  const peak = Math.max(1, ...buckets.map((bucket) => bucket.count));
  const x = (year: number) => 12 + ((year - start) / span) * (width - 24);
  const zoom = (factor: number) =>
    setWindow(
      clampYearWindow(
        start + (span - span * factor) / 2,
        span * factor,
        min,
        max,
      ),
    );
  const pan = (direction: number) =>
    setWindow(
      clampYearWindow(
        start + direction * Math.max(1, span / 3),
        span,
        min,
        max,
      ),
    );
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(200, entry.contentRect.width)),
    );
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, []);

  return (
    <details className="timeline-overview" open>
      <summary>
        时间全景 <span>按密度聚合，点击柱形展开年份</span>
      </summary>
      <div className="overview-controls">
        <button disabled={span <= 1} onClick={() => zoom(0.5)}>
          放大时间轴
        </button>
        <button disabled={span >= max - min} onClick={() => zoom(2)}>
          缩小时间轴
        </button>
        <button disabled={start <= min} onClick={() => pan(-1)}>
          ← 更早
        </button>
        <button disabled={end >= max} onClick={() => pan(1)}>
          更晚 →
        </button>
        <button onClick={() => setWindow([min, max])}>查看全程</button>
      </div>
      <p className="overview-range" aria-live="polite">
        {formatYear(start)} — {formatYear(end - 1)} · {total} 件事
      </p>
      <div ref={host}>
        <svg
          className="overview-chart"
          width="100%"
          height="130"
          viewBox={`0 0 ${width} 130`}
          aria-label="事件密度概览，可拖动平移时间范围"
          onPointerDown={(event) => {
            if (event.button !== 0) return;
            drag.current = { x: event.clientX, start, span, moved: false };
          }}
          onPointerMove={(event) => {
            const state = drag.current;
            if (!state || !event.buttons) return;
            const distance = event.clientX - state.x;
            if (Math.abs(distance) < 6 && !state.moved) return;
            state.moved = true;
            event.currentTarget.setPointerCapture(event.pointerId);
            setWindow(
              clampYearWindow(
                state.start - (distance / (width - 24)) * state.span,
                state.span,
                min,
                max,
              ),
            );
          }}
          onPointerUp={() => {
            if (drag.current) drag.current.x = NaN;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
        >
          <line
            x1={12}
            x2={width - 12}
            y1={100}
            y2={100}
            stroke="var(--line)"
          />
          {buckets.map((bucket) => {
            const label =
              bucket.years.length === 1
                ? formatYear(bucket.years[0])
                : `${formatYear(bucket.start)}至${formatYear(bucket.end - 1)}`;
            const choose = () => {
              if (drag.current?.moved) {
                drag.current = null;
                return;
              }
              if (bucket.years.length > 1)
                setWindow([bucket.start, bucket.end]);
              onSelect(bucket.years[0]);
            };
            const barHeight = Math.max(5, (bucket.count / peak) * 75);
            return (
              <g
                key={bucket.start}
                role="button"
                tabIndex={0}
                aria-label={`${label}，${bucket.count}件事${bucket.years.length > 1 ? "，放大查看" : "，查看事件"}`}
                onClick={choose}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    drag.current = null;
                    choose();
                  }
                }}
              >
                <title>
                  {label} · {bucket.count} 件事
                </title>
                <rect
                  x={x(bucket.start)}
                  y={15}
                  width={Math.max(2, x(bucket.end) - x(bucket.start) - 2)}
                  height={85}
                  fill="transparent"
                />
                <rect
                  className={
                    selectedYear !== undefined &&
                    bucket.years.includes(selectedYear)
                      ? "selected-bucket"
                      : ""
                  }
                  x={x(bucket.start)}
                  y={100 - barHeight}
                  width={Math.max(2, x(bucket.end) - x(bucket.start) - 2)}
                  height={barHeight}
                  rx={3}
                  fill="var(--teal)"
                  opacity={0.7}
                />
              </g>
            );
          })}
          <text x={12} y={122}>
            {formatYear(start)}
          </text>
          <text x={width - 12} y={122} textAnchor="end">
            {formatYear(end - 1)}
          </text>
          {!buckets.length && (
            <text x={width / 2} y={60} textAnchor="middle">
              此区间暂无记载，可平移或查看全程
            </text>
          )}
        </svg>
      </div>
      <div
        className="overview-context"
        aria-label={`当前视窗占全程的${Math.round((span / (max - min)) * 100)}%`}
      >
        <span
          style={{
            left: `${((start - min) / (max - min)) * 100}%`,
            width: `${(span / (max - min)) * 100}%`,
          }}
        />
      </div>
      <p className="overview-help">
        柱高表示事件数量 · 拖动平移，或用按钮操作 · 搜索同步概览；年份待考另列
      </p>
    </details>
  );
}
