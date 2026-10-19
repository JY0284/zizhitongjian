import { useEffect, useRef, useState, useMemo } from "react";
import * as d3 from "d3";
import type { RoleNodeUnified, RoleLinkUnified } from "../types/unified";
import {
  networkSubset,
  powerColor,
  roleSearchNames,
} from "../utils/exploration";

interface NetworkGraphProps {
  nodes: RoleNodeUnified[];
  links: RoleLinkUnified[];
  onNodeClick?: (node: RoleNodeUnified) => void;
  onLinkClick?: (sourceId: string, targetId: string) => void;
  focusNodeId?: string | null;
  onFocusNodeHandled?: () => void;
}
interface GraphNode extends RoleNodeUnified, d3.SimulationNodeDatum {}
interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  action: string;
  weight: number;
}

export function NetworkGraph({
  nodes,
  links,
  onNodeClick,
  onLinkClick,
  focusNodeId,
  onFocusNodeHandled,
}: NetworkGraphProps) {
  const container = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const fitRef = useRef<() => void>(() => {});
  const callbacks = useRef({ onNodeClick, onLinkClick, onFocusNodeHandled });
  useEffect(() => {
    callbacks.current = { onNodeClick, onLinkClick, onFocusNodeHandled };
  });
  const [width, setWidth] = useState(800);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"core" | "all" | "person">("core");
  const [focus, setFocus] = useState<string | null>(null);
  const [power, setPower] = useState("all");
  const [minAppearances, setMinAppearances] = useState(1);
  const [hint, setHint] = useState("");
  const powers = useMemo(
    () =>
      [...new Set(nodes.map((node) => node.power).filter(Boolean))] as string[],
    [nodes],
  );
  const maxAppearances = Math.max(1, ...nodes.map((node) => node.appearances));
  const activeDensity = Math.min(minAppearances, maxAppearances);
  const activePower = powers.includes(power) ? power : "all";
  const focusNode = nodes.find((node) => node.id === focus);
  const activeMode = mode === "person" && !focusNode ? "core" : mode;
  const view = useMemo(
    () =>
      networkSubset(
        nodes,
        links,
        activeMode,
        focus,
        activePower,
        activeDensity,
      ),
    [nodes, links, activeMode, focus, activePower, activeDensity],
  );
  const height =
    activeMode === "person" && view.nodes.length <= 8
      ? 300
      : width < 600
        ? 380
        : 470;
  const results = useMemo(() => {
    const term = query.trim();
    return term
      ? nodes
          .filter((node) =>
            roleSearchNames(node.name, node.aliases).some((name) =>
              name.includes(term),
            ),
          )
          .sort(
            (a, b) =>
              Number(b.name === term) - Number(a.name === term) ||
              b.appearances - a.appearances,
          )
      : [];
  }, [nodes, query]);
  const localRelations = useMemo(
    () =>
      focusNode && activeMode === "person"
        ? links.filter(
            (link) =>
              link.source === focusNode.id || link.target === focusNode.id,
          )
        : [],
    [links, focusNode, activeMode],
  );

  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(280, Math.floor(entries[0].contentRect.width))),
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!focusNodeId) return;
    const target = nodes.find(
      (node) => node.id === focusNodeId || node.aliases.includes(focusNodeId),
    );
    // Consume the external navigation command; ordinary renders preserve graph state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFocus(target?.id ?? null);
    setMode(target ? "person" : "core");
    setQuery("");
    setHint(
      target ? "" : "此人物在当前范围内没有已知的人物连线，详情仍可阅读。",
    );
    callbacks.current.onFocusNodeHandled?.();
  }, [focusNodeId, nodes]);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`).attr("height", height);
    if (!view.nodes.length) return;
    const graphNodes: GraphNode[] = view.nodes.map((node) => ({ ...node }));
    const graphLinks: GraphLink[] = view.links.map((link) => ({
      source: link.source,
      target: link.target,
      action: link.action,
      weight: link.weight,
    }));
    const nodeNames = new Map(graphNodes.map((node) => [node.id, node.name]));
    const g = svg.append("g");
    const mainLabels = new Set(
      [...graphNodes]
        .sort((a, b) => b.appearances - a.appearances)
        .slice(0, 18)
        .map((node) => node.id),
    );
    const showLabel = (node: GraphNode) =>
      graphNodes.length <= 25 || mainLabels.has(node.id) || node.id === focus;
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 5])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
        g.selectAll<SVGTextElement, GraphNode>(".graph-label")
          .attr("opacity", (node) =>
            event.transform.k > 1.6 || showLabel(node) ? 1 : 0,
          )
          .attr("font-size", 12 / event.transform.k)
          .attr("stroke-width", 3 / event.transform.k)
          .attr("y", -15 - 8 / event.transform.k);
      });
    zoomRef.current = zoom;
    svg.call(zoom).on("dblclick.zoom", null);
    svg
      .append("defs")
      .append("marker")
      .attr("id", "relation-arrow")
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 22)
      .attr("markerUnits", "userSpaceOnUse")
      .attr("markerWidth", 8)
      .attr("markerHeight", 8)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", "#8a9d99");
    const edges = g
      .append("g")
      .selectAll("line")
      .data(graphLinks)
      .join("line")
      .attr("stroke", "#a5b5b0")
      .attr("stroke-width", (link) => Math.min(1 + Math.sqrt(link.weight), 4))
      .attr("stroke-opacity", 0.55)
      .attr("marker-end", "url(#relation-arrow)");
    const hitEdges = g
      .append("g")
      .selectAll("line")
      .data(graphLinks)
      .join("line")
      .attr("stroke", "transparent")
      .attr("stroke-width", 12)
      .attr("class", "graph-edge")
      .attr("role", "button")
      .attr("tabindex", 0)
      .attr(
        "aria-label",
        (link) =>
          `${nodeNames.get(String(link.source))} → ${nodeNames.get(String(link.target))}：${link.action}`,
      )
      .style("cursor", "pointer")
      .on("keydown", (event, link) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          callbacks.current.onLinkClick?.(
            (link.source as GraphNode).id,
            (link.target as GraphNode).id,
          );
        }
      })
      .on("click", (event, link) => {
        event.stopPropagation();
        callbacks.current.onLinkClick?.(
          (link.source as GraphNode).id,
          (link.target as GraphNode).id,
        );
      });
    hitEdges
      .append("title")
      .text(
        (link) =>
          `${nodeNames.get(String(link.source))} → ${nodeNames.get(String(link.target))}：${link.action}`,
      );
    const simulation = d3
      .forceSimulation(graphNodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphLink>(graphLinks)
          .id((node) => node.id)
          .distance(100),
      )
      .force("charge", d3.forceManyBody().strength(-260))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.08))
      .force("y", d3.forceY(height / 2).strength(0.18))
      .force(
        "collision",
        d3
          .forceCollide<GraphNode>()
          .radius((node) => (showLabel(node) ? 34 : 19)),
      )
      .stop();
    simulation.tick(180);
    const vertices = g
      .append("g")
      .selectAll<SVGGElement, GraphNode>("g")
      .data(graphNodes)
      .join("g")
      .attr("class", "graph-node")
      .attr("role", "button")
      .attr("tabindex", 0)
      .attr("aria-label", (node) => `查看人物 ${node.name}`)
      .on("click", (_, node) => callbacks.current.onNodeClick?.(node))
      .on("keydown", (event, node) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          callbacks.current.onNodeClick?.(node);
        }
      })
      .on("mouseenter", (_, node) => {
        const connected = new Set([node.id]);
        graphLinks.forEach((link) => {
          const a = (link.source as GraphNode).id,
            b = (link.target as GraphNode).id;
          if (a === node.id) connected.add(b);
          if (b === node.id) connected.add(a);
        });
        vertices.attr("opacity", (item) => (connected.has(item.id) ? 1 : 0.16));
        edges.attr("stroke-opacity", (link) =>
          (link.source as GraphNode).id === node.id ||
          (link.target as GraphNode).id === node.id
            ? 0.95
            : 0.07,
        );
        vertices
          .select<SVGTextElement>(".graph-label")
          .attr("opacity", (item) => (connected.has(item.id) ? 1 : 0));
      })
      .on("mouseleave", () => {
        vertices.attr("opacity", 1);
        edges.attr("stroke-opacity", 0.55);
        vertices
          .select<SVGTextElement>(".graph-label")
          .attr("opacity", (node) =>
            d3.zoomTransform(svgRef.current!).k > 1.6 || showLabel(node)
              ? 1
              : 0,
          );
      });
    vertices
      .append("circle")
      .attr("r", (node) => Math.min(7 + Math.sqrt(node.appearances), 18))
      .attr("fill", (node) => powerColor(node.power))
      .attr("stroke", (node) => (node.id === focus ? "#233e39" : "#fff"))
      .attr("stroke-width", (node) => (node.id === focus ? 3 : 2));
    vertices
      .append("text")
      .attr("class", "graph-label")
      .attr("text-anchor", "middle")
      .attr("y", -23)
      .attr("font-size", 12)
      .attr("font-weight", 550)
      .attr("fill", "#263d37")
      .attr("stroke", "#fff")
      .attr("stroke-width", 4)
      .attr("paint-order", "stroke")
      .text((node) =>
        node.name.length > 12 ? node.name.slice(0, 11) + "…" : node.name,
      );
    vertices
      .append("title")
      .text(
        (node) =>
          `${node.name} · ${node.power || "归属未详"} · 提及 ${node.appearances} 次`,
      );
    const position = () => {
      [edges, hitEdges].forEach((selection) =>
        selection
          .attr("x1", (link) => (link.source as GraphNode).x!)
          .attr("y1", (link) => (link.source as GraphNode).y!)
          .attr("x2", (link) => (link.target as GraphNode).x!)
          .attr("y2", (link) => (link.target as GraphNode).y!),
      );
      vertices.attr("transform", (node) => `translate(${node.x},${node.y})`);
    };
    vertices.call(
      d3
        .drag<SVGGElement, GraphNode>()
        .on("start", (_, node) => {
          node.fx = node.x;
          node.fy = node.y;
        })
        .on("drag", (event, node) => {
          node.x = event.x;
          node.y = event.y;
          position();
        })
        .on("end", (_, node) => {
          node.fx = null;
          node.fy = null;
        }),
    );
    position();
    const fit = () => {
      const x0 = d3.min(graphNodes, (node) => node.x!)!,
        x1 = d3.max(graphNodes, (node) => node.x!)!;
      const y0 = d3.min(graphNodes, (node) => node.y!)!,
        y1 = d3.max(graphNodes, (node) => node.y!)!;
      const scale = Math.min(
        1.35,
        (width - 90) / Math.max(1, x1 - x0),
        (height - 90) / Math.max(1, y1 - y0),
      );
      svg.call(
        zoom.transform,
        d3.zoomIdentity
          .translate(width / 2, height / 2)
          .scale(scale)
          .translate(-(x0 + x1) / 2, -(y0 + y1) / 2),
      );
    };
    fitRef.current = fit;
    fit();
    return () => {
      simulation.stop();
      svg.on(".zoom", null);
    };
  }, [view, width, height, focus]);

  const focusPerson = (id: string) => {
    setFocus(id);
    setMode("person");
    setQuery("");
    setHint("");
  };
  return (
    <section className="surface network-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">由一人，读懂一段关系</p>
          <h2>
            {activeMode === "person" && focusNode
              ? `${focusNode.name}的人物关系`
              : "人物关系网"}
          </h2>
        </div>
        <span className="count-label">
          {view.nodes.length} / {nodes.length} 人物 · {view.links.length} 关系
        </span>
      </div>
      <label className="search-field">
        <span>查找人物</span>
        <input
          type="search"
          value={query}
          placeholder="输入姓名或别名，查看其直接关系"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && results.length)
              focusPerson(results[0].id);
          }}
        />
      </label>
      {query.trim() && (
        <div className="search-results" aria-label="人物搜索结果">
          {results.slice(0, 8).map((node) => (
            <button key={node.id} onClick={() => focusPerson(node.id)}>
              <strong>{node.name}</strong>
              <span>{node.power || "归属未详"} · 聚焦关系 →</span>
            </button>
          ))}
          {!results.length && (
            <p role="status">
              当前范围内未找到相连人物。试试更短的姓名或扩大卷数范围。
            </p>
          )}
          {results.length > 8 && (
            <p>共 {results.length} 位匹配人物，请继续输入以缩小范围。</p>
          )}
        </div>
      )}
      <div className="network-controls">
        <div className="segmented">
          <button
            aria-pressed={activeMode === "core"}
            onClick={() => {
              setMode("core");
              setFocus(null);
            }}
          >
            重点人物
          </button>
          <button
            aria-pressed={activeMode === "all"}
            onClick={() => {
              setMode("all");
              setFocus(null);
            }}
          >
            全部人物
          </button>
        </div>
        {activeMode !== "person" && (
          <label className="inline-select">
            势力
            <select
              aria-label="关系网势力"
              value={activePower}
              onChange={(event) => setPower(event.target.value)}
            >
              <option value="all">全部势力</option>
              {powers.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
        )}
        {activeMode === "person" && focusNode && (
          <button
            className="quiet-button"
            onClick={() => onNodeClick?.(focusNode)}
          >
            阅读 {focusNode.name} 详情 ↗
          </button>
        )}
      </div>
      {activeMode !== "person" && (
        <label className="density-control">
          图谱密度 · 至少提及 {activeDensity} 次
          <input
            type="range"
            aria-label="最低提及次数"
            min="1"
            max={maxAppearances}
            value={activeDensity}
            onChange={(event) => setMinAppearances(Number(event.target.value))}
          />
          {activeDensity > 1 && (
            <button
              className="quiet-button"
              onClick={() => setMinAppearances(1)}
            >
              重置密度
            </button>
          )}
        </label>
      )}
      <p className="context-note">
        {activeMode === "core"
          ? "先展示提及较多的最多 50 位人物；搜索姓名可查看直接关系。"
          : activeMode === "all"
            ? "全景适合观察结构；搜索一位人物，可以看清局部关系。"
            : "仅显示此人物及有直接互动的人物；箭头表示行动方向。"}{" "}
        节点大小表示提及次数，颜色表示势力。
      </p>
      {hint && (
        <p className="context-note" role="status">
          {hint}
        </p>
      )}
      <div className="graph-toolbar">
        <button onClick={() => fitRef.current()}>适配画布</button>
        {[
          ["放大", 1.4],
          ["缩小", 1 / 1.4],
        ].map(([label, factor]) => (
          <button
            key={label}
            onClick={() => {
              if (svgRef.current && zoomRef.current)
                d3.select(svgRef.current).call(
                  zoomRef.current.scaleBy,
                  Number(factor),
                );
            }}
          >
            {label}
          </button>
        ))}
        <span>拖动平移 · 点击人物或连线阅读</span>
      </div>
      <div className="graph-surface" ref={container}>
        {view.nodes.length ? (
          <svg ref={svgRef} aria-label="人物关系画布" />
        ) : (
          <div className="empty-state">
            <h3>当前范围内没有相连人物</h3>
            <p>试试其他势力，或返回前五卷。</p>
          </div>
        )}
      </div>
      <div className="graph-legend">
        {[...new Set(view.nodes.map((node) => node.power))].map((value) => (
          <span key={value || "unknown"}>
            <i style={{ background: powerColor(value) }} />
            {value || "归属未详"}
          </span>
        ))}
      </div>
      {localRelations.length > 0 && (
        <details className="relation-list">
          <summary>用列表阅读这些关系 · {localRelations.length} 条</summary>
          {localRelations.map((link, i) => (
            <button
              key={`${link.source}-${link.target}-${i}`}
              onClick={() => onLinkClick?.(link.source, link.target)}
            >
              {nodes.find((node) => node.id === link.source)?.name ??
                link.source}{" "}
              →{" "}
              {nodes.find((node) => node.id === link.target)?.name ??
                link.target}
              <span>{link.action}</span>
            </button>
          ))}
        </details>
      )}
    </section>
  );
}
