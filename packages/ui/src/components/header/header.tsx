// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Menu, X, LogOut } from 'lucide-react';
import { Logo } from '../logo/logo';
import { Button } from '../atoms/button/button';
import { useAuth, type UserRole } from '@/contexts/auth-context';
import { cn } from '@/lib/utils';
import { COMPANY_NAME } from '@/lib/company';

const ROLE_BADGE_STYLES: Record<UserRole, string> = {
  prospect: 'bg-muted text-slate-700',
  borrower: 'bg-emerald-100 text-emerald-700',
  loan_officer: 'bg-purple-100 text-purple-700',
  underwriter: 'bg-orange-100 text-orange-700',
  ceo: 'bg-[#C15F3C]/10 text-[#C15F3C]',
};

const ROLE_LABELS: Record<UserRole, string> = {
  prospect: '访客',
  borrower: '借款人',
  loan_officer: '客户经理',
  underwriter: '审批人员',
  ceo: '管理驾驶舱',
};

export function Header() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { user, isAuthenticated, signOut } = useAuth();
  const navigate = useNavigate();

  function handleSignOut() {
    signOut();
    navigate({ to: '/' as never });
  }

  return (
    <header className="sticky top-0 z-30 border-b border-border/80 bg-card/92 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo + Brand */}
        <Link to="/" className="flex items-center gap-2">
          <Logo />
          <span className="font-display text-base font-semibold tracking-tight text-foreground">
            {COMPANY_NAME}
          </span>
        </Link>

        {/* Right side actions */}
        <div className="flex items-center gap-2">
          {isAuthenticated && user ? (
            <div className="hidden items-center gap-3 md:flex">
              <span className="text-sm font-medium text-foreground">{user.name}</span>
              <span
                className={cn(
                  'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                  ROLE_BADGE_STYLES[user.role],
                )}
              >
                {ROLE_LABELS[user.role]}
              </span>
              <button
                onClick={handleSignOut}
                className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground dark:hover:bg-white/10"
                aria-label="退出登录"
              >
                <LogOut className="h-4 w-4" />
                <span>退出</span>
              </button>
            </div>
          ) : (
            <div className="hidden items-center gap-2 md:flex">
              <Button
                asChild
                className="bg-primary text-primary-foreground hover:bg-primary/90"
                size="sm"
              >
                <Link to={'/sign-in' as never}>进入演示</Link>
              </Button>
            </div>
          )}

          {/* Mobile hamburger */}
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden"
            aria-label={isMobileMenuOpen ? '关闭菜单' : '打开菜单'}
            aria-expanded={isMobileMenuOpen}
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
          >
            {isMobileMenuOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu panel */}
      {isMobileMenuOpen && (
        <div className="border-t border-border bg-card px-4 pb-4 md:hidden">
          <nav className="flex flex-col gap-1 pt-2" aria-label="Mobile navigation">
            <div className="mt-2 flex flex-col gap-2">
              {isAuthenticated && user ? (
                <>
                  <div className="flex items-center gap-2 px-1 py-2">
                    <span className="text-sm font-medium text-foreground">
                      {user.name}
                    </span>
                    <span
                      className={cn(
                        'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                        ROLE_BADGE_STYLES[user.role],
                      )}
                    >
                      {ROLE_LABELS[user.role]}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      handleSignOut();
                      setIsMobileMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    <LogOut className="h-4 w-4" />
                    退出
                  </button>
                </>
              ) : (
                <Button
                  asChild
                  className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                  size="sm"
                >
                  <Link to={'/sign-in' as never}>进入演示</Link>
                </Button>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
