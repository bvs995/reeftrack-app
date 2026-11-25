import React from 'react'
import ReactDOM from 'react-dom/client'
import './i18n'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import LegalPage, { legalDocForPath } from './components/LegalPage.jsx'
import './index.css'

// /privacidad y /terminos son páginas públicas (sin sesión) fuera de la app principal.
const legalDoc = typeof window !== 'undefined' ? legalDocForPath(window.location.pathname) : null;

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      {legalDoc ? <LegalPage doc={legalDoc} /> : <App />}
    </ErrorBoundary>
  </React.StrictMode>,
)

// Registro de Service Worker para capacidades PWA (sin scripts inline requeridos por CSP)
if (typeof window !== 'undefined' && 'serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then(
      (reg) => console.log('AquaReef PWA Service Worker registrado con éxito:', reg.scope),
      (err) => console.log('Fallo al registrar Service Worker:', err)
    );
  });
}
