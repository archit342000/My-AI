import { createBrowserRouter } from 'react-router';
import { RootLayout } from './RootLayout';
import { HomePage } from '../features/home/HomePage';
import { ChatPage } from '../features/chat/ChatPage';
import { WorkspacePage } from '../features/workspace/WorkspacePage';
import { LogsPage } from '../features/logs/LogsPage';

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/chat/:chatId', element: <ChatPage /> },
      { path: '/workspace/:workspaceId', element: <WorkspacePage /> },
      { path: '/logs', element: <LogsPage /> },
    ],
  },
]);
