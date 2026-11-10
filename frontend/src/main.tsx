import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'katex/dist/katex.min.css';
// Order matters: the shared values load after the legacy sheets so they win every shared name,
// and bridge.css then points the remaining legacy variables at them.
import './styles/fonts.css';
import './styles/legacy.css';
import './styles/components.css';
import './styles/tokens.css';
import './styles/bridge.css';
// The design system's own sheets, one per area. They replace the two legacy sheets block by block.
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
