import { createBrowserRouter } from 'react-router';
import { RootLayout } from './RootLayout';
import { HomePage } from '../features/home/HomePage';
import { ChatPage } from '../features/chat/ChatPage';
import { WorkspacePage } from '../features/workspace/WorkspacePage';
import { LogsPage } from '../features/logs/LogsPage';
import { PrimitivesDemo } from '../features/dev/PrimitivesDemo';

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/chat/:chatId', element: <ChatPage /> },
      { path: '/workspace/:workspaceId', element: <WorkspacePage /> },
      { path: '/logs', element: <LogsPage /> },
      ...(import.meta.env.DEV ? [{ path: '/dev/ui', element: <PrimitivesDemo /> }] : []),
      { path: '*', element: <div className="chat-error">Page not found</div> },
    ],
  },
]);
