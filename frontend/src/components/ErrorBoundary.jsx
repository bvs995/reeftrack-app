import React from 'react';
import { AlertTriangle, RefreshCw, Home, ShieldAlert } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('🌊 [AquaPulse ErrorBoundary] Excepción capturada en componente:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[280px] p-6 sm:p-8 flex items-center justify-center animate-in fade-in">
          <div className="w-full max-w-lg glass-panel rounded-3xl p-6 sm:p-7 border border-rose-500/40 bg-marine-950/95 shadow-neon-coral text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-rose-500/20 border border-rose-500/40 text-rose-400 mx-auto flex items-center justify-center">
              <ShieldAlert className="w-7 h-7 stroke-[2.2]" />
            </div>

            <div className="space-y-1">
              <h3 className="text-lg font-black text-white tracking-tight">
                Se detectó un problema en este módulo
              </h3>
              <p className="text-xs text-slate-300 max-w-sm mx-auto leading-relaxed">
                Ocurrió un error inesperado al renderizar los datos. Tu base de datos y mediciones están seguras.
              </p>
            </div>

            {/* Detalles del error colapsables */}
            {this.state.error && (
              <details className="text-left bg-marine-900/80 rounded-2xl p-3 border border-marine-800 text-[11px] font-mono text-rose-300">
                <summary className="cursor-pointer text-slate-400 hover:text-white font-sans font-bold select-none">
                  Ver detalle técnico
                </summary>
                <div className="mt-2 max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-[10px] text-slate-300">
                  {String(this.state.error?.message || this.state.error)}
                </div>
              </details>
            )}

            {/* Acciones de recuperación táctiles */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                type="button"
                onClick={this.handleReset}
                className="btn-touch-secondary w-full sm:w-auto py-2.5 px-4 text-xs font-bold rounded-xl flex items-center justify-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Reintentar Módulo</span>
              </button>

              <button
                type="button"
                onClick={this.handleReload}
                className="btn-touch w-full sm:w-auto py-2.5 px-4 bg-gradient-to-r from-cyan-500 to-emerald-400 text-marine-950 text-xs font-black rounded-xl shadow-neon-cyan flex items-center justify-center gap-2"
              >
                <Home className="w-4 h-4" />
                <span>Recargar Aplicación</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
