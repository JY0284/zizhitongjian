import { useEffect, useMemo, useState } from "react";

type GitHubRepoBadgeProps = {
  repoFullName: string; // e.g. "owner/repo"
  repoUrl: string;
  className?: string;
};

type RepoResponse = {
  stargazers_count?: number;
};

const CACHE_KEY_PREFIX = "githubRepoStats:";
const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

type CachedValue = {
  stars: number;
  fetchedAt: number;
};

function readCache(key: string): CachedValue | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CachedValue>;
    if (
      typeof parsed.stars !== "number" ||
      typeof parsed.fetchedAt !== "number"
    )
      return null;
    return { stars: parsed.stars, fetchedAt: parsed.fetchedAt };
  } catch {
    return null;
  }
}

function writeCache(key: string, value: CachedValue) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore storage failures (private mode, quota, etc.)
  }
}

export function GitHubRepoBadge({
  repoFullName,
  repoUrl,
  className,
}: GitHubRepoBadgeProps) {
  const [stars, setStars] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const cacheKey = useMemo(
    () => `${CACHE_KEY_PREFIX}${repoFullName}`,
    [repoFullName],
  );
  const apiUrl = useMemo(
    () => `https://api.github.com/repos/${repoFullName}`,
    [repoFullName],
  );

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const cached = readCache(cacheKey);
    const now = Date.now();
    if (cached && now - cached.fetchedAt < CACHE_TTL_MS) {
      setStars(cached.stars);
      setLoading(false);
    }

    // Always refresh in background (unless we already have very fresh data)
    const shouldFetch = !cached || now - cached.fetchedAt >= 60 * 1000;
    if (!shouldFetch) {
      return () => {
        cancelled = true;
        controller.abort();
      };
    }

    (async () => {
      try {
        const resp = await fetch(apiUrl, {
          signal: controller.signal,
          headers: {
            Accept: "application/vnd.github+json",
          },
        });

        if (!resp.ok) throw new Error(`GitHub API ${resp.status}`);
        const data = (await resp.json()) as RepoResponse;
        const nextStars =
          typeof data.stargazers_count === "number"
            ? data.stargazers_count
            : null;

        if (cancelled) return;
        if (nextStars !== null) {
          setStars(nextStars);
          writeCache(cacheKey, { stars: nextStars, fetchedAt: Date.now() });
        }
        setLoading(false);
      } catch {
        if (cancelled) return;
        // Keep cached value if we had one; otherwise show fallback.
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [apiUrl, cacheKey]);

  return (
    <a
      href={repoUrl}
      target="_blank"
      rel="noreferrer"
      className={["repo-badge", className ?? ""].join(" ")}
      aria-label={`Open ${repoFullName} on GitHub`}
    >
      <span className="font-medium">GitHub</span>

      <span className="repo-name">{repoFullName}</span>
      <span className="ml-1 h-4 w-px bg-white/20" />
      <span className="inline-flex items-center gap-1 tabular-nums">
        <span className="opacity-90">★</span>
        {loading ? (
          <span className="inline-block w-10 h-4 rounded bg-white/15 animate-pulse" />
        ) : (
          <span className="font-semibold">{stars ?? "—"}</span>
        )}
      </span>
    </a>
  );
}
