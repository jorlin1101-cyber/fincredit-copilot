// This project was developed with assistance from AI tools.

import { useState, useEffect } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import {
  Eye,
  EyeOff,
  X,
  Home,
  Briefcase,
  ClipboardCheck,
  BarChart3,
  Loader2,
} from 'lucide-react';
import { Logo } from '../components/logo/logo';
import { useAuth, DEV_USERS, type UserRole } from '../contexts/auth-context';
import { COMPANY_NAME } from '@/lib/company';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const Route = createFileRoute('/sign-in' as any)({
  component: SignIn,
});

const PERSONAS: {
  role: UserRole;
  label: string;
  icon: typeof Home;
  bg: string;
  text: string;
  hoverBg: string;
}[] = [
  {
    role: 'borrower',
    label: '借款人',
    icon: Home,
    bg: 'bg-green-100',
    text: 'text-green-700',
    hoverBg: 'hover:bg-green-200',
  },
  {
    role: 'loan_officer',
    label: '客户经理',
    icon: Briefcase,
    bg: 'bg-purple-100',
    text: 'text-purple-700',
    hoverBg: 'hover:bg-purple-200',
  },
  {
    role: 'underwriter',
    label: '审批人员',
    icon: ClipboardCheck,
    bg: 'bg-orange-100',
    text: 'text-orange-700',
    hoverBg: 'hover:bg-orange-200',
  },
  {
    role: 'ceo',
    label: '管理驾驶舱',
    icon: BarChart3,
    bg: 'bg-[#C15F3C]/10',
    text: 'text-[#C15F3C]',
    hoverBg: 'hover:bg-[#C15F3C]/20',
  },
];

// Keycloak demo credentials (must match config/keycloak/mortgage-ai-realm.json)
const KEYCLOAK_DEMO_USERS: Partial<
  Record<UserRole, { email: string; password: string }>
> = {
  borrower: { email: 'li.xiaoyu@example.com', password: 'demo' }, // #notsecret
  loan_officer: { email: 'wang.chen@example.com', password: 'demo' }, // #notsecret
  underwriter: { email: 'chen.jing@example.com', password: 'demo' }, // #notsecret
  ceo: { email: 'zhou.mingyuan@example.com', password: 'demo' }, // #notsecret
};

const ROLE_REDIRECTS: Record<UserRole, string> = {
  prospect: '/',
  borrower: '/borrower',
  loan_officer: '/loan-officer',
  underwriter: '/underwriter',
  ceo: '/ceo',
};

function SignIn() {
  const { signInWithCredentials, isAuthenticated, isKeycloak, isInitializing, user } =
    useAuth();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // When Keycloak SSO resolves and user is authenticated, redirect to their dashboard
  useEffect(() => {
    if (isAuthenticated && user) {
      const redirect = ROLE_REDIRECTS[user.role] ?? '/';
      navigate({ to: redirect as never });
    }
  }, [isAuthenticated, user, navigate]);

  // Show loading while Keycloak initializes
  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#C15F3C]" />
      </div>
    );
  }

  function handlePersonaClick(role: UserRole) {
    if (isKeycloak) {
      const kcUser = KEYCLOAK_DEMO_USERS[role];
      if (kcUser) {
        setEmail(kcUser.email);
        setPassword(kcUser.password);
      }
    } else {
      const devUser = DEV_USERS[role];
      setEmail(devUser.email);
      setPassword('demo1234'); // #notsecret
    }
    setError(null);
  }

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await signInWithCredentials(email, password);
      // useEffect above handles redirect once isAuthenticated + user are set
      if (!isKeycloak) {
        const match = Object.values(DEV_USERS).find((u) => u.email === email);
        const redirect = match ? ROLE_REDIRECTS[match.role] : '/';
        navigate({ to: redirect as never });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full items-stretch bg-background">
      {/* Left side: image + hero text -- flows to left edge */}
      <div className="relative hidden flex-1 flex-col justify-end overflow-hidden bg-[#3A3029] lg:flex">
        <div
          className="absolute inset-0 z-0 bg-cover bg-center opacity-35 mix-blend-soft-light saturate-50 sepia"
          style={{ backgroundImage: 'url("/sign-in-bg.png")' }}
        />
        <div className="absolute inset-0 z-10 bg-gradient-to-t from-[#302721] via-[#48372D]/70 to-[#C15F3C]/10" />
        <div className="relative z-20 flex flex-col gap-6 p-16">
          <h1 className="max-w-2xl font-display text-5xl font-semibold leading-tight tracking-tight text-[#FFF8F0] drop-shadow-md">
            住房贷款服务，一站了解、清晰办理。
          </h1>
          <p className="max-w-xl text-lg text-[#E8DDD1]">
            在线查看贷款方案、准备申请材料、跟踪办理进度，并获得清晰的业务指引。
          </p>
        </div>
      </div>

      {/* Right side: sign-in form */}
      <div className="flex w-full flex-col items-center justify-center px-6 py-12 lg:w-[480px] lg:shrink-0">
        <div className="w-full max-w-[410px] rounded-[1.5rem] border border-border bg-card p-8 shadow-[0_18px_50px_rgba(72,54,41,0.09)] sm:p-10">
          {/* Logo + Close */}
          <div className="mb-10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Logo />
              <span className="font-display text-xl font-semibold tracking-tight text-foreground">
                {COMPANY_NAME}
              </span>
            </div>
            <button
              type="button"
              onClick={() => navigate({ to: '/' as never })}
              className="flex h-10 w-10 items-center justify-center rounded-full text-slate-500 transition hover:bg-muted hover:text-slate-800 dark:hover:bg-white/10 dark:hover:text-white"
              aria-label="返回首页"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <div className="flex flex-col gap-8">
            {/* Heading */}
            <div>
              <h2 className="font-display text-3xl font-semibold tracking-tight text-foreground">
                进入演示
              </h2>
              <p className="mt-2 text-muted-foreground">
                选择角色并登录对应的住房贷款业务工作台。
              </p>
            </div>

            <form onSubmit={handleSignIn} className="flex flex-col gap-5">
              <div className="relative">
                <input
                  id="email"
                  type="email"
                  placeholder="邮箱地址"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-xl border border-input bg-background/40 px-4 py-3.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full rounded-xl border border-input bg-background/40 px-4 py-3.5 pr-12 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-3.5 text-muted-foreground hover:text-[#C15F3C]"
                  aria-label={showPassword ? '隐藏密码' : '显示密码'}
                >
                  {showPassword ? (
                    <Eye className="h-5 w-5" />
                  ) : (
                    <EyeOff className="h-5 w-5" />
                  )}
                </button>
              </div>

              <div className="flex items-center justify-between">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-input text-[#C15F3C] focus:ring-[#C15F3C]"
                  />
                  <span className="text-sm text-muted-foreground">记住我</span>
                </label>
                <button
                  type="button"
                  className="text-sm font-semibold text-[#C15F3C] hover:underline dark:text-orange-300"
                >
                  忘记密码？
                </button>
              </div>

              {error && (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="flex h-12 w-full items-center justify-center rounded-xl bg-primary text-base font-semibold text-primary-foreground shadow-sm transition-all hover:-translate-y-px hover:bg-primary/90 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-60"
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  '登录工作台'
                )}
              </button>
            </form>

            {/* Persona demo login */}
            <div className="mt-4 rounded-2xl border border-border bg-secondary/65 p-6">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                演示角色快捷登录
              </p>
              <div className="grid grid-cols-4 gap-2">
                {PERSONAS.map(({ role, label, icon: Icon, bg, text, hoverBg }) => (
                  <button
                    key={role}
                    data-testid={`persona-${role}`}
                    type="button"
                    onClick={() => handlePersonaClick(role)}
                    className="group flex flex-col items-center gap-2 rounded-lg p-2 transition-colors hover:bg-muted dark:hover:bg-white/10"
                    title={label}
                  >
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full transition ${bg} ${text} ${hoverBg}`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[10px] font-medium text-muted-foreground">
                      {label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
