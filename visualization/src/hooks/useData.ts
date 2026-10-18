import { useState, useEffect, useMemo } from 'react';
import type { JuanData, Metadata } from '../types';

// In a real application, this would fetch from an API
// For now, we'll load the data statically

export function useHistoricalData() {
  const [data, setData] = useState<JuanData | null>(null);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        // Load data from public directory
        const [juanResponse, metadataResponse] = await Promise.all([
          fetch(`${import.meta.env.BASE_URL}data/juan_1.json`),
          fetch(`${import.meta.env.BASE_URL}data/metadata.json`),
        ]);

        if (!juanResponse.ok || !metadataResponse.ok) {
          throw new Error('Failed to load data files');
        }

        const juanData = await juanResponse.json();
        const metadataData = await metadataResponse.json();

        setData(juanData);
        setMetadata(metadataData);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setLoading(false);
      }
    }

    loadData();
  }, []);

  return { data, metadata, loading, error };
}

export function useFilteredData(
  data: JuanData | null,
  juanRange: [number, number],
  _timeRange: [number | null, number | null]
) {
  void _timeRange; // Legacy hook: this schema supports volume filtering only.
  return useMemo(() => {
    if (!data) return null;

    const filtered: JuanData = {};
    Object.entries(data).forEach(([key, extraction]) => {
      const inJuanRange =
        extraction.juan_index >= juanRange[0] &&
        extraction.juan_index <= juanRange[1];

      if (inJuanRange) {
        filtered[key] = extraction;
      }
    });

    return filtered;
  }, [data, juanRange]);
}
