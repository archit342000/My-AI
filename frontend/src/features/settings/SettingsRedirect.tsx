import { Navigate, useParams } from 'react-router';
import { SETTINGS_PARAM } from './settings-nav';

/** `/settings` and `/settings/<part>` open the settings page over the home page. */
export function SettingsRedirect() {
  const { section = 'chat' } = useParams();
  return (
    <Navigate
      to={{ pathname: '/', search: `?${SETTINGS_PARAM}=${encodeURIComponent(section)}` }}
      replace
    />
  );
}
