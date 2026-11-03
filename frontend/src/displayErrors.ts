export const UI_BUILD = "0.5.4";
const sent = new Set<string>();

function safe(value: unknown, limit: number) {
  return String(value ?? "")
    .replace(/sk-[A-Za-z0-9_-]{12,}/g, "[credential removed]")
    .slice(0, limit);
}

export function reportDisplayError(
  kind: string,
  error: unknown,
  componentStack = "",
) {
  const e = error instanceof Error ? error : new Error(String(error));
  const key = kind + ":" + e.message;
  if (sent.has(key) || sent.size >= 20) return;
  sent.add(key);
  const payload = {
    kind,
    build: UI_BUILD,
    message: safe(e.message, 1200),
    stack: safe(e.stack, 6000),
    component_stack: safe(componentStack, 6000),
  };
  // Diagnostics never include settings, API credentials, questions or browser storage.
  void fetch("/api/client-errors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {});
}

export function installDisplayErrorReporting() {
  window.addEventListener("error", (event) => {
    if (event.error) reportDisplayError("window", event.error);
  });
  window.addEventListener("unhandledrejection", (event) =>
    reportDisplayError("promise", event.reason),
  );
}
