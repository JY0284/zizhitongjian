import { useMemo, useState } from "react";
import type { TimelineEventUnified } from "../types/unified";
import { formatYear, timelineGroups } from "../utils/exploration";

interface TimelineProps {
  events: TimelineEventUnified[];
  aliasGroups: string[][];
  onEventClick?: (event: TimelineEventUnified) => void;
}

export function Timeline({ events, aliasGroups, onEventClick }: TimelineProps) {
  const [query, setQuery] = useState("");
  const [year, setYear] = useState<number | null>(null);
  const [lane, setLane] = useState<"dated" | "undated">("dated");
  const [visibleCount, setVisibleCount] = useState(20);
  const { matches, years, undated } = useMemo(
    () => timelineGroups(events, query, aliasGroups),
    [events, query, aliasGroups],
  );
  const activeLane =
    lane === "dated" && !years.length && undated.length
      ? "undated"
      : lane === "undated" && !undated.length && years.length
        ? "dated"
        : lane;
  const selected = years.find(([value]) => value === year) ?? years[0];
  const shown = activeLane === "undated" ? undated : (selected?.[1] ?? []);

  return (
    <section className="surface timeline-view" aria-label="历史时间轴">
      <div className="section-heading">
        <div>
          <p className="eyebrow">顺着时间读历史</p>
          <h2>历史时间轴</h2>
        </div>
        <span className="count-label">{matches.length} 件事</span>
      </div>
      <label className="search-field">
        <span>查找事件</span>
        <input
          type="search"
          value={query}
          placeholder="人物、事件或地点，如商鞅、邯郸"
          onChange={(e) => {
            setQuery(e.target.value);
            setVisibleCount(20);
          }}
        />
      </label>
      <div className="segmented" aria-label="事件年代分类">
        <button
          aria-pressed={activeLane === "dated"}
          onClick={() => {
            setLane("dated");
            setVisibleCount(20);
          }}
        >
          按年份 · {matches.length - undated.length}
        </button>
        <button
          aria-pressed={activeLane === "undated"}
          onClick={() => {
            setLane("undated");
            setVisibleCount(20);
          }}
        >
          年份待考 · {undated.length}
        </button>
      </div>
      {matches.length === 0 ? (
        <div className="empty-state">
          <h3>{query ? "没有匹配的事件" : "这段范围还没有事件数据"}</h3>
          <p>
            {query
              ? "试试其他人物、地名，或清除搜索。"
              : "目前已完成前五卷，点击“前五卷”可返回已收录内容。"}
          </p>
          {query && (
            <button className="quiet-button" onClick={() => setQuery("")}>
              清除搜索
            </button>
          )}
        </div>
      ) : (
        <div
          className={`timeline-layout ${activeLane === "undated" ? "undated-layout" : ""}`}
        >
          {activeLane === "dated" && (
            <nav className="year-list" aria-label="选择年份">
              {years.map(([value, items]) => (
                <button
                  key={value}
                  aria-pressed={selected?.[0] === value}
                  onClick={() => {
                    setYear(value);
                    setVisibleCount(20);
                  }}
                >
                  <strong>{formatYear(value)}</strong>
                  <span>{items.length} 件事</span>
                </button>
              ))}
            </nav>
          )}
          <div className="event-list">
            <div className="event-list-heading">
              <h3>
                {activeLane === "dated" && selected
                  ? formatYear(selected[0])
                  : "年份待考"}
              </h3>
              <span>{shown.length} 件事</span>
            </div>
            {activeLane === "undated" && (
              <p className="context-note">
                这些记载未明确发生年份，含人物追述与引用旧事。请结合原文理解，不将它们放入确定年代。
              </p>
            )}
            <div className="event-cards">
              {shown.slice(0, visibleCount).map((event) => (
                <button
                  className="event-card"
                  key={event.id}
                  onClick={() => onEventClick?.(event)}
                >
                  <span className="event-meta">
                    卷 {event.juan_index}
                    {event.location ? ` · ${event.location}` : ""}
                  </span>
                  <h4>{event.name}</h4>
                  <p>{event.description}</p>
                  <span className="event-card-footer">
                    <span>{event.participants.slice(0, 3).join(" · ")}</span>
                    <span>查看记载 ↗</span>
                  </span>
                </button>
              ))}
            </div>
            {shown.length > visibleCount && (
              <button
                className="quiet-button load-more"
                onClick={() => setVisibleCount((value) => value + 20)}
              >
                再看 20 件 · 还有 {shown.length - visibleCount} 件
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
