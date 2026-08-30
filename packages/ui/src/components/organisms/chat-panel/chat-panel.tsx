// This project was developed with assistance from AI tools.

import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { MessageSquare, X, Send, Loader2 } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { useChatContext } from '@/contexts/chat-context';
import { ChatBubble } from '@/components/atoms/chat-bubble/chat-bubble';
import { cn } from '@/lib/utils';
import { AGENT_NAME } from '@/lib/company';

export function ChatPanel() {
  const { isOpen, closeChat } = useChatContext();
  const { messages, isStreaming, sendMessage, connect } = useChat({
    path: '/api/chat',
  });
  const [input, setInput] = useState('');
  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Connect on open
  useEffect(() => {
    if (isOpen) {
      connect();
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen, connect]);

  // Auto-scroll to bottom on new messages
  useLayoutEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    const id = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(id);
  }, [messages, isStreaming]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <aside
      className={cn(
        'fixed bottom-0 right-0 top-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card/98 shadow-2xl backdrop-blur transition-transform duration-300',
        isOpen ? 'translate-x-0' : 'translate-x-full',
      )}
      aria-label="智能助手"
      role="complementary"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#C15F3C]">
            <MessageSquare className="h-4 w-4 text-white" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {AGENT_NAME || '小融'}
            </h2>
            <p className="text-xs text-muted-foreground">授信流程·材料审核·政策依据</p>
          </div>
        </div>
        <button
          onClick={closeChat}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground dark:hover:bg-muted"
          aria-label="关闭智能助手"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Messages */}
      <div ref={messagesRef} className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#C15F3C]/10">
              <MessageSquare className="h-6 w-6 text-[#C15F3C]" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                {AGENT_NAME
                  ? `您好，我是${AGENT_NAME}`
                  : '您好，我是小融，您的住房贷款助手'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                我可以为您介绍住房贷款办理流程、申请材料和相关政策。
                请选择示例问题，或直接输入您想了解的内容。
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 pt-2">
              {[
                '住房贷款一般需要经过哪些流程？',
                '申请住房贷款需要准备哪些材料？',
                '商业贷款、公积金贷款和组合贷款有什么区别？',
                '成都住房贷款相关政策在哪里查询？',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => sendMessage(suggestion)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-[#C15F3C] hover:text-[#C15F3C]"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} />
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2 rounded-xl border border-border bg-secondary px-3 py-2 focus-within:border-[#C15F3C] focus-within:ring-1 focus-within:ring-[#C15F3C] dark:bg-muted">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="请输入您的问题…"
            className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#C15F3C] text-white transition-colors hover:bg-[#C15F3C]/90 disabled:opacity-40"
            aria-label="发送消息"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </aside>
  );
}

export function ChatFab({ onClick }: { onClick: () => void }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [isBouncing, setIsBouncing] = useState(false);
  const hasEngagedChatRef = useRef(false);

  useEffect(() => {
    if (hasEngagedChatRef.current) return;
    const showTimer = setTimeout(() => {
      setShowPrompt(true);
      setIsBouncing(true);
    }, 5000);
    return () => clearTimeout(showTimer);
  }, []);

  useEffect(() => {
    if (!isBouncing) return;
    const stopTimer = setTimeout(() => setIsBouncing(false), 3000);
    return () => clearTimeout(stopTimer);
  }, [isBouncing]);

  function handleClick() {
    hasEngagedChatRef.current = true;
    setShowPrompt(false);
    setIsBouncing(false);
    onClick();
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 flex items-end gap-3">
      {showPrompt && (
        <button
          onClick={handleClick}
          className="relative mb-2 animate-fade-in rounded-xl bg-card px-4 py-2.5 text-sm font-medium text-[#C15F3C] shadow-lg transition-transform hover:scale-105 dark:bg-muted dark:text-orange-200"
        >
          {AGENT_NAME ? `您好，我是${AGENT_NAME}` : '有什么可以帮您？'}
          <span className="absolute -right-1.5 bottom-2.5 h-3 w-3 rotate-45 bg-card shadow-lg dark:bg-muted" />
        </button>
      )}
      <button
        onClick={handleClick}
        className={cn(
          'flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#D97757] text-white shadow-lg transition-all hover:scale-105 hover:bg-[#B85C3D] hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D97757] focus-visible:ring-offset-2',
          isBouncing && 'animate-bounce',
        )}
        aria-label="打开智能助手"
      >
        <MessageSquare className="h-6 w-6" />
      </button>
    </div>
  );
}
