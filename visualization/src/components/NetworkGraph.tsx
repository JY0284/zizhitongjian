import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import type { RoleNodeUnified, RoleLinkUnified } from '../types/unified';

interface NetworkGraphProps {
  nodes: RoleNodeUnified[];
  links: RoleLinkUnified[];
  onNodeClick?: (node: RoleNodeUnified) => void;
  onLinkClick?: (sourceId: string, targetId: string) => void;
  focusNodeId?: string | null; // Node ID to focus/highlight from external trigger
  onFocusNodeHandled?: () => void; // Callback when focus is handled
}

interface SimulationNode extends RoleNodeUnified {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimulationLink {
  source: SimulationNode;
  target: SimulationNode;
  action: string;
  weight: number;
  time: string | null;
}

/**
 * PERFORMANCE CRITICAL: Helper to create a stable key for data comparison.
 * 
 * This function is essential to prevent unnecessary D3 force simulation rebuilds.
 * 
 * Problem it solves:
 * - React's useMemo creates new array references even when data content is identical
 * - D3 force simulation is expensive to rebuild - it resets all node positions
 * - Without this check, clicking a node would cause the entire graph to "refresh"
 *   because the click handler triggers URL updates, which causes parent re-renders,
 *   which creates new array references for nodes/links props
 * 
 * How it works:
 * - Generates a string key from node IDs and link source-target pairs
 * - If the key matches the previous render, we skip rebuilding the simulation
 * - This allows interactions (clicks, hovers) without disrupting the graph layout
 * 
 * DO NOT REMOVE THIS - it's critical for usable graph interactions!
 */
function createDataKey(nodes: RoleNodeUnified[], links: RoleLinkUnified[]): string {
  const nodeIds = nodes.map(n => n.id).sort().join(',');
  const linkIds = links.map(l => {
    const sourceId = typeof l.source === 'object' ? (l.source as SimulationNode).id : l.source;
    const targetId = typeof l.target === 'object' ? (l.target as SimulationNode).id : l.target;
    return `${sourceId}-${targetId}`;
  }).sort().join(',');
  return `${nodeIds}|${linkIds}`;
}

export function NetworkGraph({ nodes, links, onNodeClick, onLinkClick, focusNodeId, onFocusNodeHandled }: NetworkGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: RoleNodeUnified } | null>(null);
  const [linkTooltip, setLinkTooltip] = useState<{ x: number; y: number; content: RoleLinkUnified; sourceName: string; targetName: string } | null>(null);
  
  // Use refs for callbacks to avoid re-triggering useEffect
  const onNodeClickRef = useRef(onNodeClick);
  const onLinkClickRef = useRef(onLinkClick);
  useEffect(() => { onNodeClickRef.current = onNodeClick; }, [onNodeClick]);
  useEffect(() => { onLinkClickRef.current = onLinkClick; }, [onLinkClick]);
  
  // PERFORMANCE: Refs to track simulation state and avoid unnecessary rebuilds.
  // The D3 force simulation is expensive - rebuilding it resets all node positions.
  // These refs allow us to check if data actually changed before rebuilding.
  // See createDataKey() for detailed explanation.
  const simulationRef = useRef<d3.Simulation<SimulationNode, SimulationLink> | null>(null);
  const prevDataKeyRef = useRef<string>('');
  
  // Refs for zoom/pan functionality to center on focused nodes
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const nodesDataRef = useRef<SimulationNode[]>([]);
  const fitLayoutRef = useRef<() => void>(() => {});
  
  // Interactive state
  const [searchTerm, setSearchTerm] = useState('');
  const [minAppearances, setMinAppearances] = useState(1);
  const [selectedPower, setSelectedPower] = useState<string>('all');
  const [highlightOverride, setHighlightedNode] = useState<string | null>(null);
  const [notFoundMessage, setNotFoundMessage] = useState<string | null>(null);

  // Get unique powers for filter dropdown
  const availablePowers = useMemo(() => {
    const powers = new Set(nodes.map(n => n.power).filter(Boolean) as string[]);
    return Array.from(powers).sort();
  }, [nodes]);

  // Filter nodes based on appearances and power
  // Create fresh copies to avoid D3 mutating the original data
  const filteredNodes = useMemo(() => {
    return nodes
      .filter(n => n.appearances >= minAppearances)
      .filter(n => selectedPower === 'all' || n.power === selectedPower)
      .map(n => ({ ...n }));
  }, [nodes, minAppearances, selectedPower]);

  // Filter links to match filtered nodes
  // Note: We need to create fresh copies of links to avoid D3 mutating them with object references
  const filteredLinks = useMemo(() => {
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return links
      .filter(l => {
        const sourceId = typeof l.source === 'object' ? (l.source as SimulationNode).id : l.source;
        const targetId = typeof l.target === 'object' ? (l.target as SimulationNode).id : l.target;
        return nodeIds.has(sourceId) && nodeIds.has(targetId);
      })
      .map(l => ({
        ...l,
        // Reset source/target to string IDs for fresh simulation
        source: typeof l.source === 'object' ? (l.source as SimulationNode).id : l.source,
        target: typeof l.target === 'object' ? (l.target as SimulationNode).id : l.target,
      }));
  }, [links, filteredNodes]);

  // Search functionality
  const searchResult = useMemo(() => {
    if (!searchTerm) return null;
    return filteredNodes.find(n => 
      n.name.includes(searchTerm) || 
      n.aliases.some(a => a.includes(searchTerm))
    );
  }, [filteredNodes, searchTerm]);

  const searchResultRef = useRef(searchResult);
  useEffect(() => { searchResultRef.current = searchResult; }, [searchResult]);

  const highlightedNode = highlightOverride ?? searchResult?.id ?? null;

  /**
   * Center the graph view on a specific node with smooth animation.
   * 
   * This is called when:
   * - User clicks on a related entity in a detail panel (RoleDetail, EventDetail, etc.)
   * - The entity should become visually prominent in the network graph
   * 
   * The function:
   * 1. Finds the node's current position from the simulation
   * 2. Calculates a transform to center and zoom in on that node
   * 3. Applies a smooth animated transition
   */
  const centerOnNode = useCallback((nodeId: string) => {
    if (!svgRef.current || !containerRef.current || !zoomRef.current) return;
    
    // Find the node in the simulation data (which has x, y positions)
    const node = nodesDataRef.current.find(n => n.id === nodeId || n.name === nodeId);
    if (!node || node.x === undefined || node.y === undefined) return;
    
    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 600;
    
    // Calculate transform to center on the node with a nice zoom level
    const scale = 1.5; // Zoom in a bit to make the focused node prominent
    const x = width / 2 - node.x * scale;
    const y = height / 2 - node.y * scale;
    
    // Apply smooth transition to center on the node
    svg.transition()
      .duration(750)
      .call(
        zoomRef.current.transform,
        d3.zoomIdentity.translate(x, y).scale(scale)
      );
  }, []);

  /**
   * Handle external focus request - highlight AND center on the node.
   * 
   * This effect responds to `focusNodeId` prop changes, which occur when:
   * - User clicks on a related entity button in detail panels (EventDetail, RoleDetail, etc.)
   * - User navigates via URL with a focus parameter
   * 
   * The effect:
   * 1. Finds the node (by ID or name) in filtered nodes, or adjusts filters if needed
   * 2. Sets the node as highlighted (dims other nodes, shows connections)
   * 3. Centers the view on the node with a smooth zoom animation
   * 
   * The setTimeout delay ensures that if filters were changed, the simulation
   * has time to include the newly visible node before we try to center on it.
   */
  useEffect(() => {
    if (focusNodeId) {
      // Clear any previous not-found message
      // This consumes an external focus command and synchronizes the D3 view.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setNotFoundMessage(null);
      
      // Check if the node exists in filtered nodes (by ID, name, or alias)
      let targetNodeId: string | null = null;
      const nodeInFiltered = filteredNodes.find(n => 
        n.id === focusNodeId || 
        n.name === focusNodeId ||
        n.aliases?.some(alias => alias === focusNodeId)
      );
      
      if (nodeInFiltered) {
        targetNodeId = nodeInFiltered.id;
        setHighlightedNode(targetNodeId);
        setSearchTerm(''); // Clear search when focusing externally
      } else {
        // Try to find by ID, name, or alias in all nodes and adjust filters
        const node = nodes.find(n => 
          n.id === focusNodeId || 
          n.name === focusNodeId ||
          n.aliases?.some(alias => alias === focusNodeId)
        );
        if (node) {
          // Reset filters to show this node
          setMinAppearances(1);
          setSelectedPower('all');
          targetNodeId = node.id;
          setHighlightedNode(node.id);
          setSearchTerm('');
        } else {
          // Node not found in the knowledge base
          // This can happen when a related entity is mentioned but not extracted as a proper node
          console.warn(`[NetworkGraph] Entity "${focusNodeId}" not found in graph nodes. It may be a generic term or an unextracted entity.`);
          setNotFoundMessage(`"${focusNodeId}" 未在图谱中找到，可能是通用术语或未被提取的实体`);
          // Auto-hide after 3 seconds
          setTimeout(() => setNotFoundMessage(null), 3000);
        }
      }
      
      // Center view on the focused node after a short delay
      // (allows time for filter changes to take effect if needed)
      if (targetNodeId) {
        const nodeIdToCenter = targetNodeId;
        setTimeout(() => {
          centerOnNode(nodeIdToCenter);
        }, 100);
      }
      
      onFocusNodeHandled?.();
    }
  }, [focusNodeId, filteredNodes, nodes, onFocusNodeHandled, centerOnNode]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;
    if (filteredNodes.length === 0) {
      d3.select(svgRef.current).attr('height', 0).selectAll('*').remove();
      nodesDataRef.current = [];
      zoomRef.current = null;
      prevDataKeyRef.current = '';
      return;
    }

    // PERFORMANCE CRITICAL: Check if the data actually changed by comparing keys.
    // This prevents simulation rebuild when only interactions (clicks, hovers) occur.
    // Without this check, clicking a node would reset all node positions!
    // See createDataKey() function for detailed explanation.
    const currentDataKey = createDataKey(filteredNodes, filteredLinks);
    if (currentDataKey === prevDataKeyRef.current && simulationRef.current) {
      // Data hasn't changed, skip rebuilding the simulation
      return;
    }
    prevDataKeyRef.current = currentDataKey;

    // Stop previous simulation if exists
    if (simulationRef.current) {
      simulationRef.current.stop();
      simulationRef.current = null;
    }

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 600;

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3
      .select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    // Create a container group for zoom/pan
    const g = svg.append('g');

    // Add zoom behavior
    let viewAdjusted = false;
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        viewAdjusted = true;
        g.attr('transform', event.transform);
      });

    svg.call(zoom);
    
    // Store zoom ref for external centering functionality
    zoomRef.current = zoom;

    // Color scale for powers
    const powers = [...new Set(filteredNodes.map((n) => n.power || '无'))];
    const colorScale = d3.scaleOrdinal(d3.schemeTableau10).domain(powers);

    // Create force simulation
    const simulation = d3
      .forceSimulation<SimulationNode>(filteredNodes as SimulationNode[])
      .force(
        'link',
        d3
          .forceLink<SimulationNode, SimulationLink>(filteredLinks as unknown as SimulationLink[])
          .id((d) => d.id)
          .distance(120)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX(width / 2).strength(0.08))
      .force('y', d3.forceY(height / 2).strength(0.10))
      .force('collision', d3.forceCollide().radius(24));
    
    // Store simulation reference
    simulationRef.current = simulation;
    
    // Store nodes data ref for external access to node positions
    nodesDataRef.current = filteredNodes as SimulationNode[];

    // Create arrow marker
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#999');

    // Draw links
    const link = g
      .append('g')
      .selectAll('line')
      .data(filteredLinks)
      .enter()
      .append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.min(d.weight, 5))
      .attr('marker-end', 'url(#arrowhead)')
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        const linkData = d as RoleLinkUnified;
        const sourceId = typeof linkData.source === 'object' ? (linkData.source as SimulationNode).id : linkData.source;
        const targetId = typeof linkData.target === 'object' ? (linkData.target as SimulationNode).id : linkData.target;
        onLinkClickRef.current?.(sourceId, targetId);
      })
      .on('mouseover', (event, d) => {
        const linkData = d as RoleLinkUnified;
        const sourceId = typeof linkData.source === 'object' ? (linkData.source as SimulationNode).id : linkData.source;
        const targetId = typeof linkData.target === 'object' ? (linkData.target as SimulationNode).id : linkData.target;
        const sourceNode = filteredNodes.find(n => n.id === sourceId);
        const targetNode = filteredNodes.find(n => n.id === targetId);
        const [x, y] = d3.pointer(event, containerRef.current);
        setLinkTooltip({
          x: Math.max(8, Math.min(x + 10, (containerRef.current?.clientWidth ?? 800) - 460)),
          y: Math.max(8, Math.min(y + 10, 400)),
          content: linkData,
          sourceName: sourceNode?.name || sourceId,
          targetName: targetNode?.name || targetId,
        });
        d3.select(event.currentTarget)
          .attr('stroke', '#8b4513')
          .attr('stroke-opacity', 1)
          .attr('stroke-width', Math.min(linkData.weight + 2, 8));
      })
      .on('mouseout', (event, d) => {
        setLinkTooltip(null);
        const linkData = d as RoleLinkUnified;
        d3.select(event.currentTarget)
          .attr('stroke', '#999')
          .attr('stroke-opacity', 0.6)
          .attr('stroke-width', Math.min(linkData.weight, 5));
      });

    // Draw nodes
    const node = g
      .append('g')
      .attr('class', 'nodes-container')
      .selectAll('g')
      .data(filteredNodes as SimulationNode[])
      .enter()
      .append('g')
      .attr('class', 'node-group')
      .attr('role', 'button')
      .attr('aria-label', d => d.name)
      .attr('tabindex', 0)
      .on('keydown', (event, d) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onNodeClickRef.current?.(d);
        }
      })
      .style('cursor', 'pointer')
      .call(
        d3
          .drag<SVGGElement, SimulationNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      )
      .on('click', (_, d) => onNodeClickRef.current?.(d))
      .on('mouseover', (event, d) => {
        const [x, y] = d3.pointer(event, containerRef.current);
        setTooltip({
          x: Math.max(8, Math.min(x + 10, (containerRef.current?.clientWidth ?? 800) - 340)),
          y: Math.max(8, Math.min(y + 10, 400)),
          content: d,
        });
        setHighlightedNode(d.id);
      })
      .on('mouseout', () => {
        setTooltip(null);
        setHighlightedNode(searchResultRef.current?.id ?? null);
      });

    // Node circles
    node
      .append('circle')
      .attr('r', (d) => Math.min(8 + d.appearances * 2, 20))
      .attr('fill', (d) => colorScale(d.power || '无'))
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    // Node labels
    node
      .append('text')
      .attr('x', 0)
      .attr('y', -15)
      .attr('text-anchor', 'middle')
      .style('font-size', '10px')
      .style('fill', '#2c1810')
      .text((d) => d.name);

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as unknown as SimulationNode).x ?? 0)
        .attr('y1', (d) => (d.source as unknown as SimulationNode).y ?? 0)
        .attr('x2', (d) => (d.target as unknown as SimulationNode).x ?? 0)
        .attr('y2', (d) => (d.target as unknown as SimulationNode).y ?? 0);

      node.attr('transform', (d) => `translate(${d.x ?? 0}, ${d.y ?? 0})`);
    });

    // Disconnected groups can settle outside the SVG. Fit the initial layout,
    // while preserving any pan, zoom, or focused-node navigation by the reader.
    const fitLayout = () => {
      if (width <= 64) return;
      const positions = simulation.nodes();
      const minX = d3.min(positions, d => d.x ?? 0) ?? 0;
      const maxX = d3.max(positions, d => d.x ?? 0) ?? width;
      const minY = d3.min(positions, d => d.y ?? 0) ?? 0;
      const maxY = d3.max(positions, d => d.y ?? 0) ?? height;
      const scale = Math.max(0.1, Math.min(1, (width - 64) / Math.max(1, maxX - minX),
        (height - 64) / Math.max(1, maxY - minY)));
      svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2)
        .scale(scale).translate(-(minX + maxX) / 2, -(minY + maxY) / 2));
    };
    fitLayoutRef.current = fitLayout;
    simulation.on('end', () => { if (!viewAdjusted) fitLayout(); });

    // Add legend
    const legend = svg
      .append('g')
      .attr('class', 'legend')
      .attr('transform', `translate(${width - 120}, 20)`);

    powers.slice(0, 8).forEach((power, i) => {
      const legendRow = legend.append('g').attr('transform', `translate(0, ${i * 20})`);

      legendRow
        .append('circle')
        .attr('r', 6)
        .attr('fill', colorScale(power));

      legendRow
        .append('text')
        .attr('x', 12)
        .attr('y', 4)
        .style('font-size', '11px')
        .style('fill', '#2c1810')
        .text(power.length > 6 ? power.slice(0, 6) + '...' : power);
    });

    // Cleanup
    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
  }, [filteredNodes, filteredLinks]); // Re-run only when filtered data changes, not on callback changes

  // Effect for highlighting
  useEffect(() => {
    if (!svgRef.current) return;
    
    const svg = d3.select(svgRef.current);
    const node = svg.selectAll<SVGGElement, SimulationNode>('.node-group'); // Select only node groups, not legend
    const link = svg.selectAll<SVGLineElement, SimulationLink>('line');

    if (highlightedNode) {
      // Find connected nodes
      const connectedNodeIds = new Set<string>();
      connectedNodeIds.add(highlightedNode);
      
      filteredLinks.forEach(l => {
        const sourceId = typeof l.source === 'object' ? (l.source as SimulationNode).id : l.source;
        const targetId = typeof l.target === 'object' ? (l.target as SimulationNode).id : l.target;
        
        if (sourceId === highlightedNode) connectedNodeIds.add(targetId);
        if (targetId === highlightedNode) connectedNodeIds.add(sourceId);
      });

      // Dim unconnected nodes
      node.style('opacity', (d) => d && d.id && connectedNodeIds.has(d.id) ? 1 : 0.1);
      
      // Dim unconnected links
      link.style('opacity', (d) => {
        if (!d) return 0.1;
        const sourceId = typeof d.source === 'object' ? d.source?.id : d.source;
        const targetId = typeof d.target === 'object' ? d.target?.id : d.target;
        return (sourceId === highlightedNode || targetId === highlightedNode) ? 1 : 0.1;
      });
    } else {
      // Reset opacity
      node.style('opacity', 1);
      link.style('opacity', 1);
    }
  }, [highlightedNode, filteredLinks]);

  return (
    <div ref={containerRef} className="w-full bg-white rounded-lg shadow-md p-4 relative">
      <div className="flex flex-wrap justify-between items-center mb-4 gap-2">
        <h3 className="text-lg font-bold text-[#2c1810]">人物关系网络图</h3>
        
        <div className="flex flex-wrap gap-3 items-center">
          {/* Search Input */}
          <div className="relative">
            <input
              type="text"
              placeholder="搜索人物..."
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setHighlightedNode(null); }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && searchResult) centerOnNode(searchResult.id);
              }}
              className="px-3 py-1 border border-[#d4c5b5] rounded-md text-sm focus:outline-none focus:border-[#8b4513] w-32"
            />
            {searchResult && (
              <div className="absolute right-2 top-1.5 text-green-600 text-xs">
                ✓
              </div>
            )}
          </div>

          {/* Power Filter */}
          <div className="flex items-center gap-1 text-sm text-gray-600">
            <span>势力:</span>
            <select
              value={selectedPower}
              onChange={(e) => setSelectedPower(e.target.value)}
              className="px-2 py-1 border border-[#d4c5b5] rounded-md text-sm focus:outline-none focus:border-[#8b4513] bg-white"
            >
              <option value="all">全部</option>
              {availablePowers.map(power => (
                <option key={power} value={power}>{power}</option>
              ))}
            </select>
          </div>

          {/* Density Filter */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>重要度:</span>
            <input
              type="range"
              min="1"
              max="20"
              value={minAppearances}
              onChange={(e) => setMinAppearances(parseInt(e.target.value))}
              className="w-20 accent-[#8b4513]"
            />
            <span className="w-8 text-right">{minAppearances}+</span>
          </div>
        </div>
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <button className="rounded border px-2 py-1" onClick={() => fitLayoutRef.current()}>适配画布</button>
        {[['放大', 1.5], ['缩小', 1 / 1.5]].map(([label, factor]) => (
          <button key={String(label)} className="rounded border px-2 py-1" onClick={() => {
            if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().duration(200)
              .call(zoomRef.current.scaleBy, Number(factor));
          }}>{label}</button>
        ))}
        <span>搜索后按 Enter 定位；滚轮缩放，拖动画布或人物。</span>
      </div>

      <svg ref={svgRef} className="w-full" />
      {filteredNodes.length === 0 && <p className="py-12 text-center text-gray-500">当前筛选范围没有人物，请调整筛选条件。</p>}
      
      {/* Toast notification for entity not found */}
      {notFoundMessage && (
        <div className="absolute top-16 left-1/2 transform -translate-x-1/2 bg-amber-100 border border-amber-400 text-amber-800 px-4 py-2 rounded-lg shadow-lg z-20 animate-fade-in">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚠️</span>
            <span className="text-sm">{notFoundMessage}</span>
          </div>
        </div>
      )}
      
      {tooltip && (
        <div
          className="absolute bg-white border border-[#d4c5b5] rounded-lg shadow-lg p-3 z-10 w-80 max-w-[90vw] pointer-events-none break-words"
          style={{
            left: tooltip.x,
            top: tooltip.y,
          }}
        >
          <h4 className="font-bold text-[#8b4513]">{tooltip.content.name}</h4>
          <p className="text-sm text-gray-600">势力: {tooltip.content.power || '无'}</p>
          <p className="text-sm mt-1 line-clamp-3 break-words">{tooltip.content.description}</p>
          <p className="text-xs text-gray-500 mt-1">出现次数: {tooltip.content.appearances}</p>
          <p className="text-xs text-[#8b4513] mt-1 font-medium">点击查看详情</p>
        </div>
      )}

      {linkTooltip && (
        <div
          className="absolute bg-white border border-[#8b4513] rounded-lg shadow-lg p-3 z-10 w-[28rem] max-w-[90vw] pointer-events-none break-words"
          style={{
            left: linkTooltip.x,
            top: linkTooltip.y,
          }}
        >
          <h4 className="font-bold text-[#8b4513]">
            {linkTooltip.sourceName} → {linkTooltip.targetName}
          </h4>
          <p className="text-sm text-gray-700 mt-1">
            <span className="font-medium">主要行动:</span> {linkTooltip.content.action}
          </p>
          <div className="text-sm mt-1">
            <span className="font-medium text-gray-700">行动类型:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {linkTooltip.content.actionTypes?.slice(0, 5).map((type, i) => (
                <span key={i} className="px-2 py-0.5 bg-[#f5f0e8] text-[#8b4513] rounded text-xs">
                  {type}
                </span>
              ))}
              {linkTooltip.content.actionTypes && linkTooltip.content.actionTypes.length > 5 && (
                <span className="text-xs text-gray-500">
                  +{linkTooltip.content.actionTypes.length - 5}更多
                </span>
              )}
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            互动次数: {linkTooltip.content.weight}
          </p>
          {linkTooltip.content.time && (
            <p className="text-xs text-gray-500">首次互动: {linkTooltip.content.time}</p>
          )}
          <p className="text-xs text-[#8b4513] mt-2 font-medium">点击查看详细记录</p>
        </div>
      )}
    </div>
  );
}
