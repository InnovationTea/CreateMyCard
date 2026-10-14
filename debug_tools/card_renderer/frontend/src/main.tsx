import React from 'react';
import { createRoot } from 'react-dom/client';
import CardRenderer from './CardRenderer';

const root = document.getElementById('root');
if (root) createRoot(root).render(<React.StrictMode><CardRenderer /></React.StrictMode>);

