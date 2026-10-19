import type {
  TimelineEventUnified,
  RoleNodeUnified,
  RoleLinkUnified,
} from "../types/unified";

// Search vocabulary only: these familiar names do not modify extracted evidence or entity IDs.
const familiarNames: Record<string, string[]> = { 公孙鞅: ["商鞅", "卫鞅"] };
export function roleSearchNames(name: string, aliases: string[]) {
  return [...new Set([name, ...aliases, ...(familiarNames[name] ?? [])])];
}

export function eventsInYears(
  events: TimelineEventUnified[],
  [start, end]: [number | null, number | null],
) {
  if (start === null && end === null) return events;
  return events.filter(
    (event) =>
      event.timeNumeric !== null &&
      (start === null || event.timeNumeric >= start) &&
      (end === null || event.timeNumeric <= end),
  );
}

export function timelineGroups(
  events: TimelineEventUnified[],
  query: string,
  aliasGroups: string[][] = [],
) {
  const term = query.trim().toLocaleLowerCase();
  const terms = new Set([term]);
  for (const names of aliasGroups) {
    if (names.some((name) => name.toLocaleLowerCase() === term))
      names.forEach((name) => terms.add(name.toLocaleLowerCase()));
  }
  const matches = events.filter(
    (event) =>
      !term ||
      [
        event.name,
        event.description,
        event.location,
        ...event.participants,
      ].some(
        (value) =>
          value &&
          [...terms].some((name) => value.toLocaleLowerCase().includes(name)),
      ),
  );
  const years = new Map<number, TimelineEventUnified[]>();
  const undated: TimelineEventUnified[] = [];
  for (const event of matches) {
    if (event.timeNumeric === null) undated.push(event);
    else
      years.set(event.timeNumeric, [
        ...(years.get(event.timeNumeric) ?? []),
        event,
      ]);
  }
  return { matches, undated, years: [...years].sort(([a], [b]) => a - b) };
}

export function networkSubset(
  nodes: RoleNodeUnified[],
  links: RoleLinkUnified[],
  mode: "core" | "all" | "person",
  focus: string | null,
  power: string,
  minAppearances = 0,
) {
  let visible = nodes.filter(
    (node) =>
      (power === "all" || node.power === power) &&
      node.appearances >= minAppearances,
  );
  if (mode === "person" && focus) {
    const ids = new Set([focus]);
    for (const link of links) {
      if (link.source === focus) ids.add(link.target);
      if (link.target === focus) ids.add(link.source);
    }
    visible = nodes.filter((node) => ids.has(node.id));
  } else if (mode === "core") {
    visible = [...visible]
      .sort((a, b) => b.appearances - a.appearances || a.id.localeCompare(b.id))
      .slice(0, 50);
  }
  const ids = new Set(visible.map((node) => node.id));
  return {
    nodes: visible,
    links: links.filter((link) => ids.has(link.source) && ids.has(link.target)),
  };
}

/** Half-open year windows keep boundary events in exactly one bucket. */
export function timelineBuckets(
  years: [number, TimelineEventUnified[]][],
  start: number,
  end: number,
  capacity: number,
) {
  const step = Math.max(1, Math.ceil((end - start) / Math.max(1, capacity)));
  const buckets = new Map<
    number,
    { start: number; end: number; count: number; years: number[] }
  >();
  for (const [year, items] of years) {
    if (year < start || year >= end) continue;
    const lower = start + Math.floor((year - start) / step) * step;
    const bucket = buckets.get(lower) ?? {
      start: lower,
      end: Math.min(end, lower + step),
      count: 0,
      years: [],
    };
    bucket.count += items.length;
    bucket.years.push(year);
    buckets.set(lower, bucket);
  }
  return [...buckets.values()].sort((a, b) => a.start - b.start);
}

export function clampYearWindow(
  start: number,
  span: number,
  min: number,
  max: number,
): [number, number] {
  const width = Math.max(1, Math.min(max - min, Math.round(span)));
  const lower = Math.max(min, Math.min(max - width, Math.round(start)));
  return [lower, lower + width];
}

export function readFilterDraft(
  juans: [string, string],
  years: [string, string],
  maxJuan: number,
) {
  const integer = (text: string) =>
    /^-?\d+$/.test(text.trim()) && Number.isSafeInteger(Number(text));
  if (
    !juans.every(integer) ||
    juans.some((value) => Number(value) < 1 || Number(value) > maxJuan)
  ) {
    return { error: `卷数请输入 1–${maxJuan} 之间的整数。` } as const;
  }
  if (years.some((value) => value.trim() && !integer(value)))
    return { error: "年份请输入整数，留空表示不限。" } as const;
  const j: [number, number] = [Number(juans[0]), Number(juans[1])];
  const y = years.map((value) => (value.trim() ? Number(value) : null)) as [
    number | null,
    number | null,
  ];
  if (j[0] > j[1] || (y[0] !== null && y[1] !== null && y[0] > y[1])) {
    return { error: "起始值不能大于结束值，请调整后应用。" } as const;
  }
  return { juans: j, years: y } as const;
}

export const formatYear = (year: number) =>
  year < 0 ? `前${Math.abs(year)}年` : `公元${year}年`;

export function powerColor(power: string | null) {
  const colors = [
    "#356d69",
    "#ad633f",
    "#6e689d",
    "#68834f",
    "#9b5065",
    "#477f9b",
    "#95743b",
  ];
  const mainPowers: Record<string, string> = {
    秦国: colors[0],
    楚国: colors[1],
    燕国: colors[2],
    齐国: colors[3],
    赵国: colors[4],
    韩国: colors[5],
    魏国: colors[6],
  };
  if (power && mainPowers[power]) return mainPowers[power];
  const hash = [...(power || "未详")].reduce(
    (sum, letter) => (sum * 31 + letter.charCodeAt(0)) | 0,
    0,
  );
  return colors[Math.abs(hash % colors.length)];
}
