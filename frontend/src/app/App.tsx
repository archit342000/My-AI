import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router';
import { router } from './routes';
import { shouldRetryQuery } from '../api/client';
import { ErrorBoundary } from './ErrorBoundary';
import { UserGate } from './UserGate';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: shouldRetryQuery, refetchOnWindowFocus: false } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <UserGate>
          <RouterProvider router={router} />
        </UserGate>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}
