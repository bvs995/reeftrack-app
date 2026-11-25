import React from 'react'
import ReactDOM from 'react-dom/client'
import './i18n'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
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
