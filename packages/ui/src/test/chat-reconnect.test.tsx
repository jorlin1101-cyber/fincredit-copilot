import { act, renderHook, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
const mock = vi.hoisted(() => ({ connect: vi.fn(), state: 3, send: vi.fn() }));
vi.mock('../lib/ws', () => ({ connectChat: mock.connect }));
import { useChat } from '../hooks/use-chat';
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});
it('reconnects closed sockets without duplicating requests or resending messages', () => {
  vi.useFakeTimers();
  mock.state = 3;
  mock.connect.mockImplementation(() => ({
    readyState: () => mock.state,
    send: mock.send,
    close: vi.fn(),
  }));
  const { result, unmount } = renderHook(() => useChat({ path: '/api/chat' }));
  act(() => result.current.connect());
  expect(mock.connect).toHaveBeenCalledTimes(1);
  act(() => vi.advanceTimersByTime(15_000));
  expect(mock.connect).toHaveBeenCalledTimes(2);
  mock.state = 0;
  act(() => {
    result.current.connect();
    vi.advanceTimersByTime(15_000);
  });
  expect(mock.connect).toHaveBeenCalledTimes(2);
  expect(mock.send).not.toHaveBeenCalled();
  unmount();
  act(() => vi.advanceTimersByTime(30_000));
  expect(mock.connect).toHaveBeenCalledTimes(2);
});
