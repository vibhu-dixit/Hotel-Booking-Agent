/** Low-level HTTP helpers (DRY error handling). */

async function readErrorBody(r: Response): Promise<string> {
  try {
    const j: unknown = await r.json();
    if (typeof j === "object" && j !== null && "detail" in j) {
      const d = (j as { detail: unknown }).detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d))
        return d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("; ");
    }
    return JSON.stringify(j);
  } catch {
    return await r.text();
  }
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await readErrorBody(r));
  return r.json() as Promise<T>;
}

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(await readErrorBody(r));
  return r.json() as Promise<T>;
}
