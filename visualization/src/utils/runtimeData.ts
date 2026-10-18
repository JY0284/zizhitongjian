/** Fetch runtime artifacts with a useful error for Vite's HTML fallback. */
export async function fetchRuntimeData<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
    throw new Error(`无法加载 ${url}，请先准备运行时数据。`);
  }
  try {
    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Expected a JSON object');
    }
    return data as T;
  } catch {
    throw new Error(`${url} 不是有效的 JSON 对象，请重新构建数据。`);
  }
}
