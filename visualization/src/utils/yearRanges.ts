import type { JuanYearIndex } from '../types/pipelineArtifacts';

type YearRange = [number | null, number | null];

export function juanYearRange(index: JuanYearIndex, range: [number, number]): YearRange | null {
  const start = index.juan_start_year[String(range[0])];
  // Older artifacts only contain start years. Do not truncate the final volume
  // to its first year when the exact end is unavailable.
  const end = index.juan_end_year?.[String(range[1])] ?? index.juan_start_year[String(range[1] + 1)];
  if (typeof start !== 'number') return null;
  return [start, typeof end === 'number' ? Math.max(start, end) : null];
}

export function juansOverlappingYears(index: JuanYearIndex, range: YearRange): [number, number] | null {
  if (range.every(year => year === null)) return null;
  const matches = Object.entries(index.juan_start_year).filter(([juan, start]) => {
    if (typeof start !== 'number') return false;
    const end = juanYearRange(index, [Number(juan), Number(juan)])?.[1] ?? Infinity;
    return end >= (range[0] ?? -Infinity) && start <= (range[1] ?? Infinity);
  }).map(([juan]) => Number(juan));
  return matches.length ? [Math.min(...matches), Math.max(...matches)] : null;
}
