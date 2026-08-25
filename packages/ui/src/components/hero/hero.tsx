// This project was developed with assistance from AI tools.

import { Link } from '@tanstack/react-router';
import { useChatContext } from '@/contexts/chat-context';

export function Hero() {
  const { openChat } = useChatContext();

  return (
    <section className="w-full bg-gradient-to-br from-slate-50 via-blue-50 to-slate-200 py-12 dark:from-background dark:via-slate-900 dark:to-card lg:py-20">
      <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col-reverse items-center gap-10 lg:flex-row lg:gap-16">
          {/* Text side */}
          <div className="flex flex-1 flex-col gap-6 text-center lg:text-left">
            <div className="flex flex-wrap justify-center gap-2 lg:justify-start">
              {['多角色 Agent', '受控 Agentic RAG', '页级证据', '人工审批'].map(
                (tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-[#1e3a5f]/15 bg-white/80 px-3 py-1 text-xs font-semibold text-[#1e3a5f] shadow-sm dark:bg-slate-900 dark:text-blue-200"
                  >
                    {tag}
                  </span>
                ),
              )}
            </div>
            <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              <span className="text-[#1e3a5f] dark:text-blue-300">
                FinCredit Copilot
              </span>
            </h1>
            <p className="max-w-xl text-base leading-7 text-muted-foreground lg:max-w-none">
              基于多角色 Agent 与受控型 Agentic RAG 的住房贷款授信辅助平台。
              串联材料提取、交叉核验、全国与成都政策检索、DTI/LTV
              计算、风险建议和人工审批， 每一步均可追溯至原始证据与 trace_id。
            </p>
            <div className="flex flex-col items-center gap-3 sm:flex-row lg:items-start">
              <Link
                to={'/sign-in' as never}
                className="inline-flex items-center gap-2 rounded-md bg-[#cc0000] px-6 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-[#990000] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#cc0000] focus-visible:ring-offset-2"
              >
                进入角色演示
              </Link>
              <button
                onClick={() =>
                  openChat(
                    '请介绍 FinCredit Copilot 的端到端授信辅助流程，以及每个 Agent 的职责。',
                  )
                }
                className="inline-flex items-center gap-2 rounded-md bg-[#cc0000] px-6 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-[#990000] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#cc0000] focus-visible:ring-offset-2"
              >
                咨询智能助手
              </button>
            </div>
          </div>

          {/* Visual side */}
          <div className="relative flex-1">
            <img
              src="/hero-home.png"
              alt="住房贷款授信辅助平台场景"
              className="aspect-[4/3] w-full rounded-2xl object-cover shadow-md"
            />

            {/* Pre-qualified callout */}
            <div className="absolute -bottom-4 left-4 flex items-center gap-3 rounded-xl border border-border bg-white px-4 py-3 shadow-lg dark:bg-card">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-100 text-green-600">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  className="h-4 w-4"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  授信建议已生成，等待人工确认
                </p>
                <p className="text-xs text-muted-foreground">
                  证据完整 · 规则可解释 · 全程可审计
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="mx-auto mt-10 max-w-[1200px] px-4 text-center text-xs text-muted-foreground sm:px-6 lg:px-8">
        融安住房金融为虚构演示机构；页面数据与材料均为合成数据，仅供产品演示，不构成授信承诺或法律意见。
      </div>
    </section>
  );
}
