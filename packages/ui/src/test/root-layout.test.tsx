import type { ReactNode, ComponentType } from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ workspace: false, signIn: false }));
vi.mock('@tanstack/react-router', () => ({
  createRootRoute: (options: unknown) => ({ options }),
  Outlet: () => <div>Page content</div>,
  useMatchRoute: () => () => state.signIn,
  useMatches: ({ select }: { select: (matches: { routeId: string }[]) => boolean }) =>
    select(state.workspace ? [{ routeId: '/_authenticated' }] : [{ routeId: '/' }]),
}));
vi.mock('../components/header/header', () => ({
  Header: () => <header>Signed-in user</header>,
}));
vi.mock('../components/footer/footer', () => ({
  Footer: () => <footer>Public footer</footer>,
}));
vi.mock('../components/organisms/chat-panel/chat-panel', () => ({
  ChatPanel: () => <aside>Public chat</aside>,
  ChatFab: () => <button>Open chat</button>,
}));
vi.mock('../contexts/chat-context', () => ({
  ChatProvider: ({ children }: { children: ReactNode }) => children,
  useChatContext: () => ({ isOpen: false, openChat: vi.fn() }),
}));
import { Route } from '../routes/__root';
const Layout = Route.options.component as ComponentType;

afterEach(() => {
  cleanup();
  state.workspace = false;
  state.signIn = false;
});

describe('Route-aware root layout', () => {
  it('lets the public homepage grow even with a signed-in header', () => {
    render(<Layout />);
    expect(screen.getByRole('main')).not.toHaveClass('overflow-hidden');
    expect(screen.getByRole('main').parentElement).toHaveClass('min-h-screen');
    expect(screen.getByText('Public footer')).toBeInTheDocument();
    expect(screen.getByText('Public chat')).toBeInTheDocument();
  });
  it('releases the viewport lock when returning from a workspace', () => {
    state.workspace = true;
    const { rerender } = render(<Layout />);
    expect(screen.getByRole('main')).toHaveClass('overflow-hidden');
    expect(screen.queryByText('Public chat')).not.toBeInTheDocument();
    state.workspace = false;
    rerender(<Layout />);
    expect(screen.getByRole('main')).not.toHaveClass('overflow-hidden');
    expect(screen.getByRole('main').parentElement).not.toHaveClass('h-dvh');
    expect(screen.getByText('Public footer')).toBeInTheDocument();
  });
  it('keeps sign-in outside the page shell', () => {
    state.signIn = true;
    render(<Layout />);
    expect(screen.queryByRole('main')).not.toBeInTheDocument();
    expect(screen.getByText('Page content')).toBeInTheDocument();
  });
});
