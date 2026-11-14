import React, { useState } from 'react';
import { fetchPredictiveAnalysis } from '../api';

export default function ReefAnalysisCard({ aquariumData = {}, backendUrl = null }) {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);

  // Función para solicitar el análisis al backend de FastAPI
  const fetchAiAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        nombre_acuario: aquariumData?.nombre_acuario || aquariumData?.name || 'Mi Acuario Principal',
        volumen_litros: Number(aquariumData?.volumen_litros || aquariumData?.volume_liters || 280),
        ph: aquariumData?.ph !== undefined ? Number(aquariumData.ph) : null,
        kh: aquariumData?.kh !== undefined ? Number(aquariumData.kh) : (aquariumData?.alkalinity_dkh ? Number(aquariumData.alkalinity_dkh) : null),
        calcio: aquariumData?.calcio !== undefined ? Number(aquariumData.calcio) : (aquariumData?.calcium_ppm ? Number(aquariumData.calcium_ppm) : null),
        magnesio: aquariumData?.magnesio !== undefined ? Number(aquariumData.magnesio) : (aquariumData?.magnesium_ppm ? Number(aquariumData.magnesium_ppm) : null),
        nitrato: aquariumData?.nitrato !== undefined ? Number(aquariumData.nitrato) : (aquariumData?.nitrate_ppm ? Number(aquariumData.nitrate_ppm) : null),
        fosfato: aquariumData?.fosfato !== undefined ? Number(aquariumData.fosfato) : (aquariumData?.phosphate_ppm ? Number(aquariumData.phosphate_ppm) : null),
        tendencia_reciente: aquariumData?.tendencia_reciente || 'Estable en las últimas 48 horas',
      };

      let result;
      if (backendUrl) {
        // Soporte para URL personalizada explícita si se provee
        const response = await fetch(`${backendUrl.replace(/\/+$/, '')}/api/analisis-predictivo`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error('Error al conectar con el servidor de IA');
        result = await response.json();
      } else {
        // Conexión resiliente a través del cliente API autenticado
        result = await fetchPredictiveAnalysis(payload);
      }

      setAnalysis(result.data); // Guarda el JSON estructurado
    } catch (err) {
      setError(err.message || 'Error al conectar con el servidor de IA');
    } finally {
      setLoading(false);
    }
  };

  // Función para determinar el color de la tarjeta según el nivel de riesgo
  const getRiskBadgeColor = (nivel) => {
    switch (nivel?.toLowerCase()) {
      case 'crítico':
      case 'colapso inminente':
        return 'bg-red-500/20 text-red-400 border-red-500';
      case 'moderado':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500';
      case 'bajo':
      default:
        return 'bg-green-500/20 text-green-400 border-green-500';
    }
  };

  return (
    <div className="p-6 bg-slate-900 rounded-xl text-slate-100 max-w-xl mx-auto shadow-xl border border-slate-800">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h3 className="text-xl font-bold text-white mb-4 sm:mb-0 flex items-center">
          <img 
            src="/robot-fish.jpg" 
            alt="AquaPulse AI" 
            className="w-8 h-8 mr-3 rounded-lg shadow-lg border border-cyan-500/30 object-cover" 
          />
          Diagnóstico Predictivo AquaPulse
        </h3>
        <button
          onClick={fetchAiAnalysis}
          disabled={loading}
          className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-slate-950 font-semibold rounded-lg transition disabled:opacity-50 flex items-center gap-2"
        >
          {loading && (
            <svg className="animate-spin h-4 w-4 text-slate-950" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          <span>{loading ? 'Analizando agua...' : 'Analizar con IA'}</span>
        </button>
      </div>

      {error && <div className="p-3 mb-4 bg-red-500/10 border border-red-500 text-red-400 rounded-lg">{error}</div>}

      {analysis && (
        <div className="space-y-4 mt-4">
          {/* Tarjeta de Nivel de Riesgo Dinámica */}
          <div className={`p-4 rounded-lg border ${getRiskBadgeColor(analysis.nivel_riesgo)}`}>
            <span className="text-xs uppercase tracking-wider font-semibold">Nivel de Riesgo:</span>
            <h4 className="text-lg font-bold">{analysis.nivel_riesgo}</h4>
          </div>

          {/* Diagnóstico General */}
          <div className="p-4 bg-slate-800/60 rounded-lg border border-slate-700">
            <h5 className="text-sm font-semibold text-slate-400 mb-1">Diagnóstico General</h5>
            <p className="text-sm">{analysis.diagnostico_general}</p>
          </div>

          {/* Alerta Predictiva (Próximas 48h) */}
          <div className="p-4 bg-slate-800/60 rounded-lg border border-slate-700">
            <h5 className="text-sm font-semibold text-cyan-300 mb-1">⚠️ Predicción a 48 Horas</h5>
            <p className="text-sm">{analysis.alerta_predictiva}</p>
          </div>

          {/* Acciones Correctoras y Dosificaciones */}
          <div className="p-4 bg-slate-800/60 rounded-lg border border-slate-700">
            <h5 className="text-sm font-semibold text-slate-400 mb-2">Acciones y Dosis Sugeridas</h5>
            {analysis.acciones_correctoras && analysis.acciones_correctoras.length > 0 ? (
              <ul className="space-y-2">
                {analysis.acciones_correctoras.map((accion, index) => (
                  <li key={index} className="text-sm flex justify-between items-center bg-slate-900/50 p-2 rounded">
                    <span className="font-medium text-slate-200">{accion.parametro} ({accion.producto})</span>
                    <span className="px-2 py-1 bg-cyan-500/20 text-cyan-300 rounded text-xs font-bold">{accion.cantidad_sugerida}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400">No se requieren adiciones químicas inmediatas.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
