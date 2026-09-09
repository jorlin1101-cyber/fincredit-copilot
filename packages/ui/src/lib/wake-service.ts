let requested = false;

/** A visitor-triggered wake-up only; never carries auth or reads business data. */
export function wakeDemoService(): void {
  const runtime = (
    window as unknown as { __RUNTIME_CONFIG__?: { API_WAKE_URL?: string } }
  ).__RUNTIME_CONFIG__;
  const value = runtime?.API_WAKE_URL;
  if (requested || !value) return;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return;
  }
  if (
    url.protocol !== 'https:' ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== '/health/'
  )
    return;
  requested = true;
  // Opaque response is expected. Readiness is checked through the existing proxy.
  void fetch(url.href, {
    mode: 'no-cors',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    redirect: 'follow',
    signal: AbortSignal.timeout(90_000),
  }).catch(() => {});
}
