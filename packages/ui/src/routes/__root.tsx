// This project was developed with assistance from AI tools.

import {
  createRootRoute,
  Outlet,
  useMatchRoute,
  useMatches,
} from '@tanstack/react-router';
import { Header } from '../components/header/header';
import { Footer } from '../components/footer/footer';
import { ChatPanel, ChatFab } from '../components/organisms/chat-panel/chat-panel';
import { ChatProvider, useChatContext } from '../contexts/chat-context';
import { useEffect } from 'react';
import { wakeDemoService } from '../lib/wake-service';

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayoutInner() {
  const { isOpen, openChat } = useChatContext();
  const isWorkspace = useMatches({
    select: (matches) => matches.some((match) => match.routeId === '/_authenticated'),
  });
  const matchRoute = useMatchRoute();
  const isFullscreen = !!matchRoute({ to: '/sign-in' as never });

  if (isFullscreen) {
    return <Outlet />;
  }

  // Authenticated routes get their own chat sidebar via _authenticated layout
  const showPublicChat = !isWorkspace;

  return (
    <div
      className={`flex flex-col ${isWorkspace ? 'h-dvh overflow-hidden' : 'min-h-screen'}`}
    >
      <Header />
      <main className={`flex-1 ${isWorkspace ? 'flex min-h-0 overflow-hidden' : ''}`}>
        <Outlet />
      </main>
      {showPublicChat && <Footer />}
      {showPublicChat && !isOpen && <ChatFab onClick={() => openChat()} />}
      {showPublicChat && <ChatPanel />}
    </div>
  );
}

function RootLayout() {
  useEffect(() => {
    wakeDemoService();
  }, []);
  return (
    <ChatProvider>
      <RootLayoutInner />
    </ChatProvider>
  );
}
