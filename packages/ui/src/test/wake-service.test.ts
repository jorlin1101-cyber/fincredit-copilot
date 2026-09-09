import { afterEach, expect, it, vi } from 'vitest';
afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});
it('wakes once without credentials, including repeated mount calls', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ type: 'opaque' });
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('__RUNTIME_CONFIG__', {
    API_WAKE_URL: 'https://fincredit-demo-api.onrender.com/health/',
  });
  const { wakeDemoService } = await import('../lib/wake-service');
  wakeDemoService();
  wakeDemoService();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock).toHaveBeenCalledWith(
    'https://fincredit-demo-api.onrender.com/health/',
    expect.objectContaining({
      mode: 'no-cors',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
    }),
  );
});
it('does nothing with missing or unsafe configuration', async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  const { wakeDemoService } = await import('../lib/wake-service');
  wakeDemoService();
  for (const url of [
    'http://example.com/health/',
    'https://key@example.com/health/',
    'https://example.com/api/private',
    'https://example.com/health/?token=secret',
  ]) {
    vi.stubGlobal('__RUNTIME_CONFIG__', { API_WAKE_URL: url });
    wakeDemoService();
  }
  expect(fetchMock).not.toHaveBeenCalled();
});
