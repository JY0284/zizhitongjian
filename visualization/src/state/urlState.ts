export type TabType = 'timeline' | 'network' | 'power' | 'locations' | 'map';

export type SelectionType = 'event' | 'role' | 'location' | 'relationPair';

export interface UrlGlobalContext {
  tab: TabType;
  juanRange: [number, number];
  yearRange: [number | null, number | null];
  selection?:
    | { type: 'event'; id: string }
    | { type: 'role'; id: string }
    | { type: 'location'; id: string }
    | { type: 'relationPair'; sourceId: string; targetId: string };
  focusRoleId?: string;
}

const DEFAULT_CONTEXT: UrlGlobalContext = {
  tab: 'timeline',
  juanRange: [1, 5],
  yearRange: [null, null],
};

function toInt(value: string | null): number | null {
  if (value == null || value.trim() === '') return null;
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : null;
}

function clampJuan(n: number, maxJuan: number): number {
  if (!Number.isFinite(n)) return 1;
  return Math.min(maxJuan, Math.max(1, n));
}

function parseTab(value: string | null): TabType {
  if (value === 'timeline' || value === 'network' || value === 'power' || value === 'locations' || value === 'map') return value;
  return DEFAULT_CONTEXT.tab;
}

export function parseUrlGlobalContext(params: URLSearchParams, maxJuan: number): UrlGlobalContext {
  const tab = parseTab(params.get('tab'));

  const js = toInt(params.get('js'));
  const je = toInt(params.get('je'));
  const startJuan = clampJuan(js ?? DEFAULT_CONTEXT.juanRange[0], maxJuan);
  const endJuan = clampJuan(je ?? DEFAULT_CONTEXT.juanRange[1], maxJuan);
  const juanRange: [number, number] = [Math.min(startJuan, endJuan), Math.max(startJuan, endJuan)];

  const ys = toInt(params.get('ys'));
  const ye = toInt(params.get('ye'));
  const yearRange: [number | null, number | null] = [ys, ye];

  const selType = params.get('selType') as SelectionType | null;
  const selId = params.get('selId');

  let selection: UrlGlobalContext['selection'] | undefined;
  if (selType === 'event' && selId) selection = { type: 'event', id: selId };
  if (selType === 'role' && selId) selection = { type: 'role', id: selId };
  if (selType === 'location' && selId) selection = { type: 'location', id: selId };
  if (selType === 'relationPair' && selId && selId.includes('|')) {
    const [sourceId, targetId] = selId.split('|', 2);
    if (sourceId && targetId) selection = { type: 'relationPair', sourceId, targetId };
  }

  const focusRoleId = params.get('focus') || undefined;

  return {
    tab,
    juanRange,
    yearRange,
    selection,
    focusRoleId,
  };
}

export function writeUrlGlobalContext(
  params: URLSearchParams,
  ctx: Pick<UrlGlobalContext, 'tab' | 'juanRange' | 'yearRange' | 'selection' | 'focusRoleId'>
): URLSearchParams {
  const next = new URLSearchParams(params);

  next.set('tab', ctx.tab);
  next.set('js', String(ctx.juanRange[0]));
  next.set('je', String(ctx.juanRange[1]));

  const [ys, ye] = ctx.yearRange;
  if (ys == null) next.delete('ys');
  else next.set('ys', String(ys));

  if (ye == null) next.delete('ye');
  else next.set('ye', String(ye));

  if (ctx.focusRoleId) next.set('focus', ctx.focusRoleId);
  else next.delete('focus');

  if (!ctx.selection) {
    next.delete('selType');
    next.delete('selId');
  } else {
    next.set('selType', ctx.selection.type);
    if (ctx.selection.type === 'relationPair') {
      next.set('selId', `${ctx.selection.sourceId}|${ctx.selection.targetId}`);
    } else {
      next.set('selId', ctx.selection.id);
    }
  }

  return next;
}
