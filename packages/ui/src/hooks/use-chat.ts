// This project was developed with assistance from AI tools.

import { useState, useCallback, useRef, useEffect } from 'react';
import { apiGet, apiDelete } from '@/lib/api-client';
import {
  connectChat,
  type WsMessage,
  type ChatWs,
  type ConnectChatOptions,
} from '@/lib/ws';

const CONNECT_ATTEMPT_TIMEOUT_MS = 15_000;
const RESPONSE_WAIT_TIMEOUT_MS = 105_000;
const SERVICE_STARTING_MESSAGE = '演示服务正在启动，连接成功后会自动回复，请稍候…';

/** crypto.randomUUID() requires a secure context (HTTPS). Fall back for plain HTTP. */
function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) =>
    (+c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(
      16,
    ),
  );
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  timestamp: Date;
  _streaming?: boolean;
}

interface ToolCall {
  name: string;
  input?: Record<string, unknown>;
  output?: unknown;
}

interface UseChatOptions {
  path: string;
  historyPath?: string;
  wsOptions?: ConnectChatOptions;
}

export function useChat({ path, historyPath, wsOptions }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<ChatWs | null>(null);
  const currentToolCallsRef = useRef<ToolCall[]>([]);
  const mountedRef = useRef(true);
  const prevOptionsRef = useRef<string>('');
  const connectCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const connectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const responseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingMessageRef = useRef<string | null>(null);
  const isStreamingRef = useRef(false);

  const clearConnectTimers = useCallback(() => {
    if (connectCheckRef.current) {
      clearInterval(connectCheckRef.current);
      connectCheckRef.current = null;
    }
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current);
      connectTimeoutRef.current = null;
    }
  }, []);

  const clearResponseTimeout = useCallback(() => {
    if (responseTimeoutRef.current) {
      clearTimeout(responseTimeoutRef.current);
      responseTimeoutRef.current = null;
    }
  }, []);

  const finishWithError = useCallback(
    (content: string) => {
      if (!mountedRef.current || !isStreamingRef.current) return;
      pendingMessageRef.current = null;
      isStreamingRef.current = false;
      clearResponseTimeout();
      currentToolCallsRef.current = [];
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant' && isStreamingMsg(last)) {
          const updated = { ...last, content };
          delete (updated as Record<string, unknown>)['_streaming'];
          return [...prev.slice(0, -1), updated];
        }
        return prev;
      });
      setConnectionError(content);
      setIsStreaming(false);
    },
    [clearResponseTimeout],
  );

  const loadHistory = useCallback(async () => {
    if (!historyPath) return;
    try {
      const qs = wsOptions?.appId ? `?app_id=${wsOptions.appId}` : '';
      const data = await apiGet<{ data: { role: string; content: string }[] }>(
        `${historyPath}${qs}`,
      );
      if (!mountedRef.current) return;
      if (data.data.length > 0) {
        setMessages(
          data.data.map((m) => ({
            id: uuid(),
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: new Date(),
          })),
        );
      }
    } catch {
      // History unavailable -- start fresh
    }
  }, [historyPath, wsOptions?.appId]);

  const connect = useCallback(() => {
    // Detect if options changed (reconnect scenario)
    const optionsKey = JSON.stringify(wsOptions ?? {});
    const optionsChanged = optionsKey !== prevOptionsRef.current;
    prevOptionsRef.current = optionsKey;

    if (optionsChanged && wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setMessages([]);
      setIsConnected(false);
    }

    if (
      wsRef.current &&
      (wsRef.current.readyState() === WebSocket.OPEN ||
        wsRef.current.readyState() === WebSocket.CONNECTING)
    )
      return;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionError(null);

    let ws: ChatWs;
    ws = connectChat(
      path,
      (msg: WsMessage) => {
        if (!mountedRef.current) return;

        switch (msg.type) {
          case 'token':
            setConnectionError(null);
            if (msg.content) {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last?.role !== 'assistant' || !isStreamingMsg(last)) return prev;
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: last.content + msg.content },
                ];
              });
            }
            break;

          case 'reset':
            setConnectionError(null);
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last?.role !== 'assistant' || !isStreamingMsg(last)) return prev;
              return [...prev.slice(0, -1), { ...last, content: '' }];
            });
            break;

          case 'tool_start':
            setConnectionError(null);
            if (msg.tool_name) {
              currentToolCallsRef.current.push({
                name: msg.tool_name,
                input: msg.tool_input,
              });
            }
            break;

          case 'tool_result':
            setConnectionError(null);
            if (msg.tool_name) {
              const tc = currentToolCallsRef.current.find(
                (t) => t.name === msg.tool_name && !t.output,
              );
              if (tc) tc.output = msg.tool_output;
            }
            break;

          case 'done': {
            clearResponseTimeout();
            // The final, cleaned answer replaces any streamed draft.
            const doneContent = msg.content ?? '';
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last?.role === 'assistant') {
                const updated = { ...last, content: doneContent };
                if (currentToolCallsRef.current.length > 0) {
                  updated.toolCalls = [...currentToolCallsRef.current];
                }
                delete (updated as Record<string, unknown>)['_streaming'];
                return [...prev.slice(0, -1), updated];
              }
              return [
                ...prev,
                {
                  id: uuid(),
                  role: 'assistant' as const,
                  content: doneContent,
                  timestamp: new Date(),
                },
              ];
            });
            currentToolCallsRef.current = [];
            isStreamingRef.current = false;
            setIsStreaming(false);
            setConnectionError(null);
            window.dispatchEvent(new Event('chat-done'));
            break;
          }

          case 'error':
            if (msg.content === '智能助手连接失败') {
              if (pendingMessageRef.current) {
                setConnectionError(SERVICE_STARTING_MESSAGE);
              } else if (isStreamingRef.current) {
                finishWithError('连接中断，本次回复未能完成，请重新发送。');
              } else {
                setConnectionError('暂时无法连接小融，请稍后重试。');
              }
            } else {
              finishWithError(msg.content ?? '暂时无法完成本次查询，请稍后重试。');
            }
            break;
        }
      },
      () => {
        if (!mountedRef.current || wsRef.current !== ws) return;
        clearConnectTimers();
        setIsConnected(false);
        if (pendingMessageRef.current && isStreamingRef.current) {
          setConnectionError(SERVICE_STARTING_MESSAGE);
        } else if (isStreamingRef.current) {
          finishWithError('连接中断，本次回复未能完成，请重新发送。');
        }
      },
      wsOptions,
    );

    wsRef.current = ws;
    clearConnectTimers();
    const check = setInterval(() => {
      if (ws.readyState() === WebSocket.OPEN) {
        setIsConnected(true);
        setConnectionError(null);
        clearConnectTimers();
        // Load history once connected
        if (optionsChanged) {
          loadHistory();
        }
        // Send any message queued while connecting
        if (pendingMessageRef.current) {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role !== 'assistant' || !isStreamingMsg(last)) return prev;
            return [...prev.slice(0, -1), { ...last, content: '' }];
          });
          ws.send(pendingMessageRef.current);
          pendingMessageRef.current = null;
        }
      }
      if (ws.readyState() === WebSocket.CLOSED) {
        clearConnectTimers();
      }
    }, 100);
    connectCheckRef.current = check;
    connectTimeoutRef.current = setTimeout(() => {
      if (wsRef.current === ws && ws.readyState() === WebSocket.CONNECTING) {
        clearConnectTimers();
        ws.close();
      }
    }, CONNECT_ATTEMPT_TIMEOUT_MS);
  }, [
    path,
    wsOptions,
    loadHistory,
    clearConnectTimers,
    clearResponseTimeout,
    finishWithError,
  ]);

  // Recover after a cold start and send a queued message exactly once.
  // The ref prevents unstable option objects from continually resetting the timer.
  const reconnectRef = useRef(connect);
  reconnectRef.current = connect;
  useEffect(() => {
    const timer = setInterval(() => {
      if (mountedRef.current && wsRef.current?.readyState() === WebSocket.CLOSED) {
        reconnectRef.current();
      }
    }, 15_000);
    return () => clearInterval(timer);
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    pendingMessageRef.current = null;
    isStreamingRef.current = false;
    clearConnectTimers();
    clearResponseTimeout();
    setIsConnected(false);
    setIsStreaming(false);
  }, [clearConnectTimers, clearResponseTimeout]);

  const sendMessage = useCallback(
    (content: string, displayContent?: string) => {
      if (!content.trim()) return;
      const socket = wsRef.current;
      const needsConnection =
        !socket || socket.readyState() !== WebSocket.OPEN;
      if (needsConnection) {
        pendingMessageRef.current = content;
        setConnectionError(SERVICE_STARTING_MESSAGE);
        connect();
      } else {
        socket.send(content);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: uuid(),
          role: 'user',
          content: displayContent ?? content,
          timestamp: new Date(),
        },
        {
          id: uuid(),
          role: 'assistant',
          content: needsConnection ? SERVICE_STARTING_MESSAGE : '',
          timestamp: new Date(),
          _streaming: true,
        },
      ]);
      currentToolCallsRef.current = [];
      isStreamingRef.current = true;
      setIsStreaming(true);
      clearResponseTimeout();
      responseTimeoutRef.current = setTimeout(() => {
        const socket = wsRef.current;
        finishWithError('本次连接等待超时，请重新发送。');
        socket?.close();
      }, RESPONSE_WAIT_TIMEOUT_MS);
    },
    [connect, clearResponseTimeout, finishWithError],
  );

  const clearHistory = useCallback(async () => {
    if (!historyPath) return;
    try {
      const qs = wsOptions?.appId ? `?app_id=${wsOptions.appId}` : '';
      await apiDelete(`${historyPath}${qs}`);
    } catch {
      // Best-effort -- clear local state regardless
    }
    setMessages([]);
  }, [historyPath, wsOptions?.appId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      prevOptionsRef.current = '';
      clearConnectTimers();
      clearResponseTimeout();
      wsRef.current?.close();
    };
  }, [clearConnectTimers, clearResponseTimeout]);

  return {
    messages,
    isStreaming,
    isConnected,
    connectionError,
    sendMessage,
    connect,
    disconnect,
    clearHistory,
  };
}

function isStreamingMsg(msg: ChatMessage): boolean {
  return msg._streaming === true;
}
