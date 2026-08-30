// This project was developed with assistance from AI tools.

import { Link } from '@tanstack/react-router';
import { useChatContext } from '@/contexts/chat-context';

export function Hero() {
  const { openChat } = useChatContext();

  return (
    <section className="relative w-full overflow-hidden bg-gradient-to-br from-[#FBF8F2] via-[#F3ECE2] to-[#E9DED0] py-14 dark:from-background dark:via-card dark:to-[#352E29] lg:py-24">
      <div className="pointer-events-none absolute -right-28 -top-36 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
      <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col-reverse items-center gap-10 lg:flex-row lg:gap-16">
          {/* Text side */}
          <div className="flex flex-1 flex-col gap-6 text-center lg:text-left">
            <h1 className="font-display text-4xl font-semibold leading-[1.12] tracking-[-0.025em] text-foreground sm:text-5xl lg:text-6xl">
              让住房贷款办理
              <span className="mt-1 block text-primary">更清晰、更省心</span>
            </h1>
            <p className="max-w-xl text-base leading-7 text-muted-foreground lg:max-w-none">
              融安住房金融为购房客户提供住房贷款咨询、方案测算、材料准备、申请进度查询和政策指引，
              帮助您看懂流程、少走弯路。
            </p>
            <div className="flex flex-col items-center gap-3 sm:flex-row lg:items-start">
              <Link
                to={'/sign-in' as never}
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-sm transition-all hover:-translate-y-px hover:bg-primary/90 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                登录服务平台
              </Link>
              <button
                onClick={() => openChat()}
                className="inline-flex items-center gap-2 rounded-xl border border-primary/25 bg-card/80 px-6 py-3 text-sm font-semibold text-primary shadow-sm backdrop-blur transition-all hover:-translate-y-px hover:border-primary/40 hover:bg-card hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
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
              className="aspect-[4/3] w-full rounded-[1.5rem] border border-white/60 object-cover shadow-[0_24px_60px_rgba(72,54,41,0.16)] saturate-[.86] sepia-[.08] dark:border-border"
            />

            {/* Pre-qualified callout */}
            <div className="absolute -bottom-4 left-4 flex items-center gap-3 rounded-2xl border border-border bg-card/95 px-4 py-3 shadow-[0_12px_32px_rgba(72,54,41,0.14)] backdrop-blur">
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
                  申请进度清晰可查
                </p>
                <p className="text-xs text-muted-foreground">
                  材料、审批与签约节点一目了然
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
