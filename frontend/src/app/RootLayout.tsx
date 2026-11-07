import { Outlet } from 'react-router';

export function RootLayout() {
  return (
    <div className="app-root">
      <Outlet />
    </div>
  );
}
