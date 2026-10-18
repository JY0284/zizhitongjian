import type { UnifiedKnowledgeBase } from '../types/unified';

export function resolveRoleId(kb: UnifiedKnowledgeBase | null, name: string): string | null {
  if (!kb) return null;
  if (kb.roles[name]) return name;
  const indexed = kb.name_to_role_id?.[name];
  if (indexed && kb.roles[indexed]) return indexed;
  return Object.values(kb.roles).find(role => role.all_names.includes(name))?.id ?? null;
}

export function roleNavigation(
  kb: UnifiedKnowledgeBase | null, name: string, juanRange: [number, number],
  yearRange: [number | null, number | null], visibleIds: Set<string>,
) {
  const id = resolveRoleId(kb, name);
  if (!id || !kb) return null;
  const juans = kb.roles[id].juans_appeared;
  const inVolumeRange = juans.some(j => j >= juanRange[0] && j <= juanRange[1]);
  const nextJuans: [number, number] = !inVolumeRange && juans.length
    ? [Math.min(...juans), Math.max(...juans)] : juanRange;
  // The detail is available even for people without a graph edge. Remove a
  // restrictive year filter when revealing somebody outside the visible graph.
  const nextYears: [number | null, number | null] = visibleIds.has(id) ? yearRange : [null, null];
  return { id, juanRange: nextJuans, yearRange: nextYears };
}

export function relatedEntities(kb: UnifiedKnowledgeBase | null, names: string[]) {
  const people = new Map<string, string>();
  const others = new Map<string, { name: string; kind: string }>();
  for (const name of names) {
    const roleId = resolveRoleId(kb, name);
    if (roleId && kb) {
      people.set(roleId, kb.roles[roleId].canonical_name);
      continue;
    }
    let matched = false;
    for (const [kind, entities] of [
      ['国家', kb?.polities], ['组织', kb?.organizations], ['学派', kb?.schools],
    ] as const) {
      const entity = Object.values(entities ?? {}).find(e => e.id === name || e.all_names.includes(name));
      if (entity) {
        others.set(`${kind}:${entity.id}`, { name: entity.canonical_name, kind });
        matched = true;
        break;
      }
    }
    if (!matched) others.set(name, { name, kind: '未匹配实体' });
  }
  return { people: [...people.values()], others: [...others.values()] };
}
