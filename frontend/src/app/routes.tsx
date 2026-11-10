import { createBrowserRouter } from 'react-router';
import { NotFoundPage, RouteError } from './DeadEnds';
import { RootLayout } from './RootLayout';
import { HomePage } from '../features/home/HomePage';
import { ChatPage } from '../features/chat/ChatPage';
import { WorkspacePage } from '../features/workspace/WorkspacePage';
import { LogsPage } from '../features/logs/LogsPage';
import { SettingsRedirect } from '../features/settings/SettingsRedirect';
import { PrimitivesDemo } from '../features/dev/PrimitivesDemo';

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/chat/:chatId', element: <ChatPage /> },
      { path: '/workspace/:workspaceId', element: <WorkspacePage /> },
      { path: '/logs', element: <LogsPage /> },
      // The settings page lies over whatever page is open (`?settings=<part>`); these addresses lead to it.
      { path: '/settings', element: <SettingsRedirect /> },
      { path: '/settings/:section', element: <SettingsRedirect /> },
      ...(import.meta.env.DEV ? [{ path: '/dev/ui', element: <PrimitivesDemo /> }] : []),
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
