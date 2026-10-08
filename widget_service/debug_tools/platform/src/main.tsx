import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('工作台缺少根节点');
}

createRoot(root).render(
  <StrictMode>
    <BrowserRouter basename="/debug">
      <App />
    </BrowserRouter>
  </StrictMode>,
);
