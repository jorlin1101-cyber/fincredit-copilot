// This project was developed with assistance from AI tools.

import { Logo } from '../logo/logo';
import { COMPANY_NAME } from '@/lib/company';

export function Footer() {
  return (
    <footer className="w-full bg-[#302A25] text-[#F7F1E8] dark:bg-[#1D1A18]">
      <div className="mx-auto max-w-[1200px] px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
          {/* Brand */}
          <div className="flex items-center gap-2">
            <Logo />
            <span className="font-display text-base font-bold">{COMPANY_NAME}</span>
          </div>

          {/* Section links */}
          <div className="flex gap-8">
            <span className="text-sm font-semibold tracking-widest text-white/70">
              住房贷款服务
            </span>
            <span className="text-sm font-semibold tracking-widest text-white/70">
              关于平台
            </span>
            <span className="text-sm font-semibold tracking-widest text-white/70">
              客户帮助
            </span>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-10 border-t border-white/10 pt-8 text-xs text-white/50">
          <p>
            融安住房金融为虚构演示机构；页面中的机构、人员、申请与审批数据均为合成内容，仅供产品演示，不代表真实授信结果。
          </p>
        </div>
      </div>
    </footer>
  );
}
