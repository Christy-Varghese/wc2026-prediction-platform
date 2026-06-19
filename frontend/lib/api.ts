export const API =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
export const pct0 = (x: number) => `${Math.round(x * 100)}%`;
