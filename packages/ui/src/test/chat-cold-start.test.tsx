import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { WsHandler } from '../lib/ws';

const mock = vi.hoisted(() => ({ connect: vi.fn(), send: vi.fn() }));
vi.mock('../lib/ws', () => ({ connectChat: mock.connect }));
import { useChat } from '../hooks/use-chat';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

it('keeps a cold-start message queued and sends it once after reconnecting', () => {
  vi.useFakeTimers();
  const states: number[] = [WebSocket.CONNECTING, WebSocket.OPEN];
  const handlers: WsHandler[] = [];
  let attempts = 0;

  mock.connect.mockImplementation(
    (_path: string, onMessage: WsHandler, onClose?: () => void) => {
      const index = attempts++;
      handlers[index] = onMessage;
      return {
        readyState: () => states[index],
        send: mock.send,
        close: () => {
          states[index] = WebSocket.CLOSED;
          onClose?.();
        },
      };
    },
  );

  const { result } = renderHook(() => useChat({ path: '/api/chat' }));
  act(() => result.current.sendMessage('有哪些产品'));
  expect(result.current.messages.at(-1)?.content).toContain('演示服务正在启动');

  act(() => vi.advanceTimersByTime(15_000));
  expect(mock.send).not.toHaveBeenCalled();
  act(() => vi.advanceTimersByTime(15_100));
  expect(mock.connect).toHaveBeenCalledTimes(2);
  expect(mock.send).toHaveBeenCalledTimes(1);
  expect(mock.send).toHaveBeenCalledWith('有哪些产品');
  expect(result.current.messages.at(-1)?.content).toBe('');

  act(() => handlers[1]({ type: 'done', content: '目前提供三类产品。' }));
  expect(result.current.isStreaming).toBe(false);
  expect(result.current.messages.at(-1)?.content).toBe('目前提供三类产品。');
});

it('ends the pending reply when an active connection drops', () => {
  vi.useFakeTimers();
  let onClose: (() => void) | undefined;
  mock.connect.mockImplementation(
    (_path: string, _onMessage: WsHandler, closeHandler?: () => void) => {
      onClose = closeHandler;
      return {
        readyState: () => WebSocket.OPEN,
        send: mock.send,
        close: vi.fn(),
      };
    },
  );

  const { result } = renderHook(() => useChat({ path: '/api/chat' }));
  act(() => result.current.connect());
  act(() => vi.advanceTimersByTime(100));
  act(() => result.current.sendMessage('有哪些产品'));
  act(() => onClose?.());

  expect(result.current.isStreaming).toBe(false);
  expect(result.current.messages.at(-1)?.content).toContain('连接中断');
  expect(result.current.messages.at(-1)?._streaming).toBeUndefined();
});

it('stops waiting instead of leaving the typing indicator forever', () => {
  vi.useFakeTimers();
  let onMessage: WsHandler = () => {};
  const close = vi.fn();
  mock.connect.mockImplementation((_path: string, handler: WsHandler) => {
    onMessage = handler;
    return {
      readyState: () => WebSocket.OPEN,
      send: mock.send,
      close,
    };
  });

  const { result } = renderHook(() => useChat({ path: '/api/chat' }));
  act(() => result.current.connect());
  act(() => vi.advanceTimersByTime(100));
  act(() => result.current.sendMessage('有哪些产品'));
  act(() => onMessage({ type: 'token', content: '目前' }));
  act(() => vi.advanceTimersByTime(105_000));

  expect(close).toHaveBeenCalled();
  expect(result.current.isStreaming).toBe(false);
  expect(result.current.messages.at(-1)?.content).toContain('等待超时');
  expect(result.current.messages.at(-1)?._streaming).toBeUndefined();
});
