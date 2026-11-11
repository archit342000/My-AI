import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'katex/dist/katex.min.css';
// The typefaces, then the shared values (a synced copy of the Console at Rest design system).
import './styles/fonts.css';
import './styles/tokens.css';
// The app's own sheets, one per area, built only from the shared values.
import './styles/ds/base.css';
import './styles/ds/controls.css';
import './styles/ds/layers.css';
import './styles/ds/frame.css';
import './styles/ds/home.css';
import './styles/ds/chat.css';
import './styles/ds/content.css';
import './styles/ds/files.css';
import './styles/ds/workspace.css';
import './styles/ds/settings.css';
import './styles/ds/logs.css';
import './styles/ds/tools.css';
import './styles/ds/states.css';
import './styles/ds/phone.css';
import './styles/ds/dev.css';
import { App } from './app/App';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
