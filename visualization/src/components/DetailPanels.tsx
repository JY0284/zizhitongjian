import type {
  TimelineEventUnified,
  RoleNodeUnified,
  UnifiedLocation,
  UnifiedRelation,
  RoleLinkUnified,
  UnifiedKnowledgeBase,
} from '../types/unified';

import { resolveRoleId, relatedEntities } from '../utils/roleNavigation';

function formatJuanSpan(juans: number[] | undefined): string {
  if (!juans || juans.length === 0) return '未知卷';
  const sorted = [...juans].sort((a, b) => a - b);
  const start = sorted[0];
  const end = sorted[sorted.length - 1];
  return start === end ? `卷${start}` : `卷${start}–${end}`;
}

function renderRelatedRoleChip(
  opts: {
    name: string;
    kb: UnifiedKnowledgeBase | null;
    availableRoleIds: Set<string>;
    onClick: (name: string) => void;
    variant?: 'neutral' | 'danger';
  }
) {
  const { name, kb, availableRoleIds, onClick, variant } = opts;
  const roleId = resolveRoleId(kb, name);
  const available = roleId ? availableRoleIds.has(roleId) : false;
  const juanSpan = roleId && kb?.roles?.[roleId] ? formatJuanSpan(kb.roles[roleId].juans_appeared) : null;

  if (roleId) {
    const baseClass =
      variant === 'danger'
        ? 'inline-flex items-center px-2 py-1 bg-[#c41e3a] text-white rounded text-sm hover:bg-[#8b4513] transition-colors cursor-pointer'
        : 'inline-flex items-center px-2 py-1 bg-[#faf8f5] border border-[#d4c5b5] rounded text-sm hover:bg-[#8b4513] hover:text-white hover:border-[#8b4513] transition-colors cursor-pointer';
    return (
      <button key={name} onClick={() => onClick(roleId)} className={baseClass}
        title={available ? '查看人物详情与关系图' : `打开人物所在卷：${juanSpan}`}>
        {name}
        {!available && juanSpan && <span className="ml-1 text-[10px] opacity-70">({juanSpan})</span>}
      </button>
    );
  }

  // Unavailable: show chip + optional info text below (only if we know where it appears)
  return (
    <span
      key={name}
      className="inline-flex items-center px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm text-gray-400 cursor-not-allowed"
      title={juanSpan ? `不可用（当前范围内不存在）。出现：${juanSpan}` : '不可用（未知来源）'}
    >
      {name}
      {juanSpan && <span className="ml-1 text-[10px] text-gray-400">({juanSpan})</span>}
    </span>
  );
}

function RelatedEntities({ names, kb, availableRoleIds, onClick, title = '相关人物' }: {
  names: string[]; kb: UnifiedKnowledgeBase | null; availableRoleIds: Set<string>;
  onClick: (name: string) => void; title?: string;
}) {
  const { people, others } = relatedEntities(kb, names);
  return <>
    {people.length > 0 && <div>
      <span className="font-semibold text-[#2c1810]">{title}：</span>
      <p className="text-xs text-gray-500 mt-0.5">点击查看人物与关系图；跨卷人物会自动切换范围</p>
      <div className="flex flex-wrap gap-2 mt-1">
        {people.map(name => renderRelatedRoleChip({ name, kb, availableRoleIds, onClick }))}
      </div>
    </div>}
    {others.length > 0 && <div>
      <span className="font-semibold text-[#2c1810]">相关国家、组织与其他实体：</span>
      <div className="flex flex-wrap gap-2 mt-1">
        {others.map(entity => <span key={`${entity.kind}:${entity.name}`}
          className="inline-flex items-center px-2 py-1 bg-[#faf8f5] border border-[#d4c5b5] rounded text-sm">
          {entity.name}<span className="ml-1 text-xs text-gray-500">{entity.kind}</span>
        </span>)}
      </div>
    </div>}
  </>;
}

interface EventDetailProps {
  event: TimelineEventUnified | null;
  onClose: () => void;
  onEntityClick?: (entityName: string) => void;
  onLocationClick?: (locationName: string) => void;
  kb: UnifiedKnowledgeBase | null;
  availableRoleIds: Set<string>;
}

export function EventDetail({ event, onClose, onEntityClick, onLocationClick, kb, availableRoleIds }: EventDetailProps) {
  if (!event) return null;

  const handleEntityClick = (name: string) => {
    onEntityClick?.(name);
  };

  const handleLocationClick = (name: string) => {
    onClose();
    onLocationClick?.(name);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-xl font-bold text-[#8b4513]">{event.name}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-3">
          {event.time && (
            <div>
              <span className="font-semibold text-[#2c1810]">时间：</span>
              <span className="text-gray-700">{event.time}</span>
            </div>
          )}

          {event.location && (
            <div>
              <span className="font-semibold text-[#2c1810]">地点：</span>
              {onLocationClick ? (
                <button
                  onClick={() => handleLocationClick(event.location!)}
                  className="text-[#8b4513] hover:underline cursor-pointer"
                >
                  {event.location}
                </button>
              ) : (
                <span className="text-gray-700">{event.location}</span>
              )}
            </div>
          )}

          <RelatedEntities names={event.participants} kb={kb} availableRoleIds={availableRoleIds}
            onClick={handleEntityClick} title="参与人物" />

          <div>
            <span className="font-semibold text-[#2c1810]">描述：</span>
            <p className="text-gray-700 mt-1">{event.description}</p>
          </div>

          {event.significance && (
            <div>
              <span className="font-semibold text-[#2c1810]">历史意义：</span>
              <p className="text-gray-700 mt-1 text-sm italic">{event.significance}</p>
            </div>
          )}

          <div className="text-sm text-gray-500 pt-2 border-t border-[#d4c5b5]">
            来源：卷{event.juan_index}
          </div>
        </div>
      </div>
    </div>
  );
}

interface RoleDetailProps {
  role: RoleNodeUnified | null;
  onClose: () => void;
  onEntityClick?: (entityName: string) => void;
  onEventClick?: (event: TimelineEventUnified) => void;
  relatedEvents?: TimelineEventUnified[];
  kb: UnifiedKnowledgeBase | null;
  availableRoleIds: Set<string>;
}

export function RoleDetail({ role, onClose, onEntityClick, onEventClick, relatedEvents, kb, availableRoleIds }: RoleDetailProps) {
  if (!role) return null;

  const handleEntityClick = (name: string) => {
    onEntityClick?.(name);
  };

  const handleEventClick = (event: TimelineEventUnified) => {
    onClose();
    onEventClick?.(event);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-xl font-bold text-[#8b4513]">{role.name}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-3">
          {role.aliases && role.aliases.length > 0 && (
            <div>
              <span className="font-semibold text-[#2c1810]">别名：</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {role.aliases.map((alias, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-1 bg-[#faf8f5] border border-[#d4a574] rounded text-sm text-[#8b4513]"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          )}

          {role.power && (
            <div>
              <span className="font-semibold text-[#2c1810]">势力：</span>
              <span className="px-2 py-1 bg-[#c41e3a] text-white rounded text-sm ml-2">
                {role.power}
              </span>
            </div>
          )}

          <div>
            <span className="font-semibold text-[#2c1810]">模型抽取简介：</span>
            <p className="text-gray-700 mt-1">{role.description || '暂无描述'}</p>
          </div>

          <RelatedEntities names={role.relatedEntities ?? []} kb={kb} availableRoleIds={availableRoleIds}
            onClick={handleEntityClick} />

          {relatedEvents && relatedEvents.length > 0 && (
            <div>
              <span className="font-semibold text-[#2c1810]">相关事件：</span>
              <p className="text-xs text-gray-500 mt-0.5">点击可查看详情</p>
              <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                {relatedEvents.slice(0, 10).map((event) => (
                  <button
                    key={event.id}
                    onClick={() => handleEventClick(event)}
                    className="w-full text-left p-2 bg-[#faf8f5] border border-[#d4c5b5] rounded hover:bg-[#8b4513] hover:text-white hover:border-[#8b4513] transition-colors"
                  >
                    <div className="font-medium text-sm">{event.name}</div>
                    {event.time && <div className="text-xs opacity-70">{event.time}</div>}
                  </button>
                ))}
                {relatedEvents.length > 10 && (
                  <span className="text-sm text-gray-500 block text-center">+{relatedEvents.length - 10} 更多事件</span>
                )}
              </div>
            </div>
          )}

          <div>
            <span className="font-semibold text-[#2c1810]">出现次数：</span>
            <span className="text-gray-700">{role.appearances} 次</span>
          </div>

          {!!kb?.roles[role.id]?.occurrences.length && (
            <details className="rounded border border-[#d4c5b5] p-3">
              <summary className="cursor-pointer font-semibold text-[#8b4513]">
                原文依据（{kb.roles[role.id].occurrences.length} 处）
              </summary>
              <p className="text-xs text-gray-500 mt-2">以下为仓库的文白对照，可能包含引语和史论；简介及人物对应关系仍需审校。</p>
              <div className="mt-2 space-y-2">
                {kb.roles[role.id].occurrences.map((item, index) => (
                  <details key={index} className="border-t border-[#d4c5b5] pt-2 text-sm">
                    <summary className="cursor-pointer text-gray-600">卷{item.juan_index} · 段{item.segment_index} · 片段{item.chunk_index + 1}</summary>
                    <p className="mt-2 whitespace-pre-wrap leading-relaxed text-gray-700">{item.source_sentence || item.original_description || '此处未保存原文摘录。'}</p>
                    {kb.source_passages?.[`${item.juan_index}-${item.segment_index}-${item.chunk_index}`] && (
                      <div className="mt-2 rounded bg-amber-50 p-2 text-xs leading-relaxed text-gray-700">
                        <p className="font-semibold">文言对照</p>
                        <p>{kb.source_passages[`${item.juan_index}-${item.segment_index}-${item.chunk_index}`].original}</p>
                        <p className="mt-1 text-amber-800">{kb.source_passages[`${item.juan_index}-${item.segment_index}-${item.chunk_index}`].review_note}</p>
                      </div>
                    )}
                  </details>
                ))}
              </div>
            </details>
          )}

          <div>
            <span className="font-semibold text-[#2c1810]">出现卷目：</span>
            <div className="flex flex-wrap gap-2 mt-1">
              {role.juans.map((j) => (
                <span
                  key={j}
                  className="px-2 py-1 bg-[#faf8f5] border border-[#d4c5b5] rounded text-sm"
                >
                  卷{j}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface LocationListProps {
  locations: UnifiedLocation[];
  onLocationClick?: (location: UnifiedLocation) => void;
}

export function LocationList({ locations, onLocationClick }: LocationListProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h3 className="text-lg font-bold text-[#2c1810] mb-4">地点列表</h3>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {locations.map((loc) => (
          <div
            key={loc.id}
            className="p-3 border border-[#d4c5b5] rounded-lg hover:bg-[#faf8f5] cursor-pointer transition-colors"
            onClick={() => onLocationClick?.(loc)}
          >
            <div className="flex justify-between items-start">
              <h4 className="font-semibold text-[#8b4513]">{loc.canonical_name}</h4>
              {loc.location_type && (
                <span className="text-xs px-2 py-1 bg-[#d4a574] text-white rounded">
                  {loc.location_type}
                </span>
              )}
            </div>
            {loc.modern_name && (
              <p className="text-sm text-gray-500 mt-1">今：{loc.modern_name}</p>
            )}
            {loc.description && (
              <p className="text-sm text-gray-700 mt-1 line-clamp-2">{loc.description}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

interface LocationDetailProps {
  location: UnifiedLocation | null;
  relatedEvents: TimelineEventUnified[];
  relatedRoles: string[];
  relatedActions: UnifiedRelation[];
  onClose: () => void;
  onEntityClick?: (entityName: string) => void;
  onNavigateToMap?: () => void;
  kb: UnifiedKnowledgeBase | null;
  availableRoleIds: Set<string>;
}

export function LocationDetail({
  location,
  relatedEvents,
  relatedRoles,
  onClose,
  onEntityClick,
  onNavigateToMap,
  kb,
  availableRoleIds,
}: LocationDetailProps) {
  if (!location) return null;

  const handleEntityClick = (name: string) => {
    onEntityClick?.(name);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold text-[#8b4513]">{location.canonical_name}</h2>
            {location.modern_name && (
              <p className="text-sm text-gray-500">今：{location.modern_name}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          {location.location_type && (
            <div>
              <span className="px-2 py-1 bg-[#d4a574] text-white rounded text-sm">
                {location.location_type}
              </span>
            </div>
          )}

          {location.all_names && location.all_names.length > 1 && (
            <div>
              <span className="font-semibold text-[#2c1810]">别名：</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {location.all_names.filter(n => n !== location.canonical_name).map((alias, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-1 bg-[#faf8f5] border border-[#d4c5b5] rounded text-sm"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          )}

          {location.description && (
            <div>
              <span className="font-semibold text-[#2c1810]">描述：</span>
              <p className="text-gray-700 mt-1">{location.description}</p>
            </div>
          )}

          {(location.coordinates || onNavigateToMap) && (
            <div className="flex items-center gap-4">
              {location.coordinates ? <div>
                <span className="font-semibold text-[#2c1810]">坐标：</span>
                <span className="text-gray-700 ml-2">
                  {location.coordinates[0].toFixed(4)}, {location.coordinates[1].toFixed(4)}
                </span>
              </div> : <p className="text-sm text-amber-800">现代位置参考：{location.geocoding?.matched_address} · 古址待核验</p>}
              {onNavigateToMap && (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onNavigateToMap();
                  }}
                  className="inline-flex items-center px-3 py-1.5 text-sm bg-[#faf8f5] border border-[#d4c5b5] text-[#8b4513] rounded hover:bg-white transition-colors"
                >
                  在地图中查看
                </button>
              )}
            </div>
          )}

          {relatedEvents.length > 0 && (
            <div>
              <span className="font-semibold text-[#2c1810]">相关事件：</span>
              <div className="mt-2 space-y-2">
                {relatedEvents.map((event) => (
                  <div
                    key={event.id}
                    className="p-2 bg-[#faf8f5] border border-[#d4c5b5] rounded"
                  >
                    <div className="font-medium text-[#8b4513]">{event.name}</div>
                    {event.time && <div className="text-xs text-gray-500">{event.time}</div>}
                    <p className="text-sm text-gray-700 mt-1 line-clamp-2">{event.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <RelatedEntities names={relatedRoles} kb={kb} availableRoleIds={availableRoleIds}
            onClick={handleEntityClick} />
        </div>
      </div>
    </div>
  );
}

interface RelationDetailProps {
  relations: RoleLinkUnified[];
  sourceName: string;
  targetName: string;
  onClose: () => void;
  onEntityClick?: (entityName: string) => void;
  onEventClick?: (event: TimelineEventUnified) => void;
  relatedEvents?: TimelineEventUnified[];
  kb: UnifiedKnowledgeBase | null;
  availableRoleIds: Set<string>;
}

export function RelationDetail({
  relations,
  sourceName,
  targetName,
  onClose,
  onEntityClick,
  onEventClick,
  relatedEvents,
  kb,
}: RelationDetailProps) {
  if (!relations || relations.length === 0) return null;

  const handleEntityClick = (name: string) => {
    onEntityClick?.(name);
  };

  const handleEventClick = (event: TimelineEventUnified) => {
    onClose();
    onEventClick?.(event);
  };

  // Aggregate stats from all relations
  const allSourceJuans = [...new Set(relations.flatMap(r => r.sourceJuans || []))].sort((a, b) => a - b);
  const totalWeight = relations.reduce((sum, r) => sum + r.weight, 0);
  
  // Get the earliest time
  const times = relations.map(r => r.time).filter(Boolean);
  const earliestTime = times.length > 0 ? times[0] : null;

  const sourceId = resolveRoleId(kb, sourceName);
  const targetId = resolveRoleId(kb, targetName);
  const sourceAvailable = Boolean(sourceId);
  const targetAvailable = Boolean(targetId);
  const sourceJuanSpan = sourceId && kb?.roles?.[sourceId] ? formatJuanSpan(kb.roles[sourceId].juans_appeared) : '未知卷';
  const targetJuanSpan = targetId && kb?.roles?.[targetId] ? formatJuanSpan(kb.roles[targetId].juans_appeared) : '未知卷';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold text-[#8b4513]">
              人物关系详情
            </h2>
            <p className="text-lg text-[#2c1810] mt-1">
              <button
                onClick={() => sourceAvailable && handleEntityClick(sourceName)}
                disabled={!sourceAvailable}
                className={
                  sourceAvailable
                    ? 'font-semibold hover:text-[#8b4513] hover:underline cursor-pointer'
                    : 'font-semibold text-gray-400 cursor-not-allowed'
                }
              >
                {sourceName}
              </button>
              <span className="mx-2 text-gray-500">⇄</span>
              <button
                onClick={() => targetAvailable && handleEntityClick(targetName)}
                disabled={!targetAvailable}
                className={
                  targetAvailable
                    ? 'font-semibold hover:text-[#8b4513] hover:underline cursor-pointer'
                    : 'font-semibold text-gray-400 cursor-not-allowed'
                }
              >
                {targetName}
              </button>
            </p>
            <p className="text-xs text-gray-500 mt-0.5">点击人物名可在图中查看</p>
            {(!sourceAvailable || !targetAvailable) && (
              <p className="text-xs text-gray-400 mt-1">
                {!sourceAvailable ? `${sourceName} 不可用 · ${sourceJuanSpan}` : null}
                {!sourceAvailable && !targetAvailable ? '；' : null}
                {!targetAvailable ? `${targetName} 不可用 · ${targetJuanSpan}` : null}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          {/* Relations Summary */}
          {relations.length > 1 && (
            <div className="p-3 bg-[#f5f0e8] border border-[#d4a574] rounded-lg">
              <span className="text-sm text-[#8b4513]">
                共找到 <strong>{relations.length}</strong> 条关系记录（包含双向关系）
              </span>
            </div>
          )}

          {/* Individual Relations */}
          {relations.map((relation, relIdx) => {
            const relSourceId = relation.source;
            const isReverse = relSourceId !== sourceName && relSourceId !== relations[0].source;
            const fromName = isReverse ? targetName : sourceName;
            const toName = isReverse ? sourceName : targetName;
            
            return (
              <div key={relIdx} className="border border-[#d4c5b5] rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm font-semibold text-[#8b4513]">关系 {relIdx + 1}:</span>
                  <span className="text-sm text-gray-700">{fromName}</span>
                  <span className="text-gray-400">→</span>
                  <span className="text-sm text-gray-700">{toName}</span>
                </div>

                {/* Primary Action */}
                <div className="mb-2">
                  <span className="font-semibold text-[#2c1810] text-sm">主要行动：</span>
                  <span className="ml-2 px-2 py-0.5 bg-[#8b4513] text-white rounded-full text-xs">
                    {relation.action}
                  </span>
                </div>

                {/* Action Types */}
                {relation.actionTypes && relation.actionTypes.length > 0 && (
                  <div className="mb-2">
                    <span className="font-semibold text-[#2c1810] text-sm">行动类型：</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {relation.actionTypes.slice(0, 8).map((type, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 bg-[#f5f0e8] border border-[#d4a574] text-[#8b4513] rounded text-xs"
                        >
                          {type}
                        </span>
                      ))}
                      {relation.actionTypes.length > 8 && (
                        <span className="text-xs text-gray-500 self-center">
                          +{relation.actionTypes.length - 8}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Contexts for this relation */}
                {relation.contexts && relation.contexts.length > 0 && (
                  <div>
                    <span className="font-semibold text-[#2c1810] text-sm">
                      互动记录 ({relation.contexts.length})：
                    </span>
                    <div className="mt-1 space-y-1 max-h-40 overflow-y-auto">
                      {relation.contexts.map((context, idx) => (
                        <div
                          key={idx}
                          className="p-2 bg-[#faf8f5] border border-[#d4c5b5] rounded text-xs text-gray-700"
                        >
                          {context}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Summary Stats */}
          <div className="pt-3 border-t border-[#d4c5b5] grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-semibold text-[#2c1810]">总互动次数：</span>
              <span className="text-gray-700 ml-2">{totalWeight} 次</span>
            </div>
            {earliestTime && (
              <div>
                <span className="font-semibold text-[#2c1810]">最早记录：</span>
                <span className="text-gray-700 ml-2">{earliestTime}</span>
              </div>
            )}
          </div>

          {/* Related Events */}
          {relatedEvents && relatedEvents.length > 0 && (
            <div>
              <span className="font-semibold text-[#2c1810] text-sm">相关事件：</span>
              <p className="text-xs text-gray-500 mt-0.5">点击可查看详情</p>
              <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                {relatedEvents.slice(0, 8).map((event) => (
                  <button
                    key={event.id}
                    onClick={() => handleEventClick(event)}
                    className="w-full text-left p-2 bg-[#faf8f5] border border-[#d4c5b5] rounded hover:bg-[#8b4513] hover:text-white hover:border-[#8b4513] transition-colors"
                  >
                    <div className="font-medium text-sm">{event.name}</div>
                    {event.time && <div className="text-xs opacity-70">{event.time}</div>}
                  </button>
                ))}
                {relatedEvents.length > 8 && (
                  <span className="text-sm text-gray-500 block text-center">+{relatedEvents.length - 8} 更多事件</span>
                )}
              </div>
            </div>
          )}

          {/* Source Juans */}
          {allSourceJuans.length > 0 && (
            <div>
              <span className="font-semibold text-[#2c1810] text-sm">出现卷目：</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {allSourceJuans.map((j) => (
                  <span
                    key={j}
                    className="px-2 py-0.5 bg-[#faf8f5] border border-[#d4c5b5] rounded text-xs"
                  >
                    卷{j}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
