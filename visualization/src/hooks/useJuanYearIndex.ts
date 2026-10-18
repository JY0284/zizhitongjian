import { useEffect, useState } from 'react';
import { fetchRuntimeData } from '../utils/runtimeData';

export interface JuanYearIndex {
  version: string;
  generated_at: string;
  juan_start_year: Record<string, number | null>;
}

export function useJuanYearIndex() {
  const [juanYearIndex, setJuanYearIndex] = useState<JuanYearIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const data = await fetchRuntimeData<JuanYearIndex>(
          `${import.meta.env.BASE_URL}data/juan_year_index.json`, controller.signal);
        if (!data.juan_start_year || typeof data.juan_start_year !== 'object' || Array.isArray(data.juan_start_year)) {
          throw new Error('卷年份索引格式无效，请重新构建数据。');
        }
        if (controller.signal.aborted) return;
        setJuanYearIndex(data);
        setLoading(false);
      } catch (err) {
        if (controller.signal.aborted) return;
        console.error('Error loading juan year index:', err);
        setError(err instanceof Error ? err.message : 'Unknown error loading juan year index');
        setLoading(false);
      }
    }

    load();
    return () => controller.abort();
  }, []);

  return { juanYearIndex, loading, error };
}
