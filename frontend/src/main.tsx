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
import { App } from './app/App';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
