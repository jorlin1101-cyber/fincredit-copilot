// This project was developed with assistance from AI tools.

import {
  createFileRoute,
  Outlet,
  useNavigate,
  useLocation,
} from '@tanstack/react-router';
import { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth, type UserRole } from '@/contexts/auth-context';
import { ChatSidebar } from '@/components/organisms/chat-sidebar/chat-sidebar';

const ROLE_HOME: Record<UserRole, string> = {
  prospect: '/sign-in',
  borrower: '/borrower',
  loan_officer: '/loan-officer',
  underwriter: '/underwriter',
  ceo: '/executive',
};

/** Check if the current path is allowed for the user's role. */
function isRouteAllowed(pathname: string, role: UserRole): boolean {
  if (pathname.startsWith('/borrower')) return role === 'borrower';
  if (pathname.startsWith('/loan-officer')) return role === 'loan_officer';
  if (pathname.startsWith('/underwriter')) return role === 'underwriter';
  if (pathname.startsWith('/executive')) return role === 'ceo';
  if (pathname.startsWith('/ceo')) return role === 'ceo';
  return true; // root or unknown routes
}

export const Route = createFileRoute('/_authenticated')({
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const { user, isAuthenticated, isInitializing } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (isInitializing) return;
    if (!isAuthenticated) {
      navigate({ to: '/sign-in' as never });
      return;
    }
    // Role-based redirect: prevent cross-role route access
    if (user && !isRouteAllowed(location.pathname, user.role)) {
      navigate({ to: (ROLE_HOME[user.role] ?? '/') as never });
    }
  }, [isAuthenticated, isInitializing, navigate, user, location.pathname]);

  if (isInitializing) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <main
          data-testid="authenticated-content-scroll"
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-12 lg:pr-[340px]"
        >
          <Outlet />
        </main>
        <ChatSidebar />
      </div>
      <div className="fixed bottom-0 left-0 right-0 z-10 border-t border-border/80 bg-secondary/95 px-4 py-1.5 text-center text-[10px] leading-tight text-muted-foreground backdrop-blur lg:right-[320px]">
        本平台及其中展示的机构、人员、申请与审批数据均为虚构演示内容，不代表任何真实金融机构、个人或授信结果；如有雷同，纯属巧合。
      </div>
    </div>
  );
}
