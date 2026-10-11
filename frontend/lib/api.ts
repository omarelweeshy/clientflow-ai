let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  extra?: Record<string, string>,
): Promise<T> {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
    const { demoApi } = await import("./demo-api");
    return demoApi<T>(path, method, body, extra);
  }
  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...extra,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const value = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path.startsWith("/admin"))
      throw new Error("Session expired. Please sign in again.");
    const detail = Array.isArray(value.detail)
      ? value.detail
          .map(
            (x: { field: string; message: string }) =>
              `${x.field}: ${x.message}`,
          )
          .join("; ")
      : value.detail;
    throw new Error(detail || "Request failed");
  }
  return value as T;
}
