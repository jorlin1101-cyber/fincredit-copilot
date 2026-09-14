import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { WsHandler } from '../lib/ws';

const mock = vi.hoisted(() => ({ connect: vi.fn(), send: vi.fn() }));
vi.mock('../lib/ws', () => ({ connectChat: mock.connect }));
import { useChat } from '../hooks/use-chat';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it('shows chunks as they arrive and replaces the draft with the final answer', () => {
  let onMessage: WsHandler = () => {};
  mock.connect.mockImplementation((_path: string, handler: WsHandler) => {
    onMessage = handler;
    return { readyState: () => WebSocket.OPEN, send: mock.send, close: vi.fn() };
  });

  const { result } = renderHook(() => useChat({ path: '/api/chat' }));
  act(() => result.current.connect());
  act(() => result.current.sendMessage('住房贷款流程？'));
  act(() => onMessage({ type: 'token', content: '先准备' }));
  expect(result.current.messages.at(-1)?.content).toBe('先准备');
  expect(result.current.isStreaming).toBe(true);

  act(() => onMessage({ type: 'token', content: '材料' }));
  expect(result.current.messages.at(-1)?.content).toBe('先准备材料');
  act(() => onMessage({ type: 'reset' }));
  expect(result.current.messages.at(-1)?.content).toBe('');
  act(() => onMessage({ type: 'token', content: '最终结果' }));
  act(() => onMessage({ type: 'done', content: '最终结果。' }));
  expect(result.current.messages.at(-1)?.content).toBe('最终结果。');
  expect(result.current.messages.at(-1)?._streaming).toBeUndefined();
  expect(result.current.isStreaming).toBe(false);
});
