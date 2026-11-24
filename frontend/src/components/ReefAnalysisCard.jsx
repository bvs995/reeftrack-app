import React, { useState, forwardRef, useImperativeHandle } from 'react';
import { fetchPredictiveAnalysis, sendDiagnosticFeedback } from '../api';
import {
  AlertTriangle,
  ShieldCheck,
  Sparkles,
  Flag,
  CheckCircle,
  X,
  Send,
  Info,
  Clock,
  RotateCw
} from 'lucide-react';

const ReefAnalysisCard = forwardRef(function ReefAnalysisCard({ aquariumData = {}, backendUrl = null }, ref) {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);

  // Estados para el modal de feedback y reporte de diagnóstico incorrecto
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackConsent, setFeedbackConsent] = useState(false);
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);
  const [feedbackError, setFeedbackError] = useState(null);

  // Margen de error base metrológico para visualización (Fase 3 & 5)
  const getMeasurementMarginText = (paramKey, value) => {
    if (value === null || value === undefined) return null;
    const num = Number(value);
    switch (paramKey.toLowerCase()) {
      case 'kh':
      case 'alkalinity':
      case 'alkalinity_dkh':
        return `${num.toFixed(1)} ± 0.3 dKH`;
      case 'calcio':
      case 'calcium':
      case 'calcium_ppm':
        return `${num.toFixed(0)} ± 20 ppm`;
      case 'magnesio':
      case 'magnesium':
      case 'magnesium_ppm':
        return `${num.toFixed(0)} ± 50 ppm`;
      case 'nitrato':
      case 'nitrate':
      case 'nitrate_ppm':
        if (num <= 0.001) return `< 0.50 ppm (límite detección)`;
        const errNo3 = Math.max(0.5, 0.20 * num).toFixed(1);
        return `${num.toFixed(1)} ± ${errNo3} ppm`;
      case 'fosfato':
      case 'phosphate':
      case 'phosphate_ppm':
        if (num <= 0.001) return `< 0.02 ppm (límite detección)`;
        return `${num.toFixed(2)} ± 0.02 ppm`;
      case 'temperatura':
      case 'temperature':
        return `${num.toFixed(1)} ± 0.5 °C`;
      case 'salinidad':
      case 'salinity':
      case 'salinity_ppt':
        return num > 1.1 ? `${num.toFixed(1)} ± 1 ppt` : `${num.toFixed(3)} ± 0.001 SG`;
      case 'ph':
        return `${num.toFixed(2)} ± 0.05`;
      default:
        return `${num}`;
    }
  };

  // Solicitar análisis predictivo al backend
  const fetchAiAnalysis = async () => {
    setLoading(true);
    setError(null);
    setFeedbackSuccess(false);
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
        temperatura: aquariumData?.temperatura !== undefined ? Number(aquariumData.temperatura) : (aquariumData?.temperature ? Number(aquariumData.temperature) : null),
        salinity: aquariumData?.salinity !== undefined ? Number(aquariumData.salinity) : (aquariumData?.salinity_ppt ? Number(aquariumData.salinity_ppt) : null),
        tipo: aquariumData?.tipo || aquariumData?.tank_type || 'sps_reef',
        reef_profile: aquariumData?.reef_profile || aquariumData?.tank_type || 'sps_reef',
        tendencia_reciente: aquariumData?.tendencia_reciente || 'Estable en las últimas 48 horas',
      };

      let result;
      if (backendUrl) {
        const response = await fetch(`${backendUrl.replace(/\/+$/, '')}/api/analisis-predictivo`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error('Error al conectar con el servidor de análisis');
        result = await response.json();
      } else {
        result = await fetchPredictiveAnalysis(payload);
      }

      setAnalysis(result.data);
    } catch (err) {
      setError(err.message || 'Error al conectar con el servidor de análisis');
    } finally {
      setLoading(false);
    }
  };

  useImperativeHandle(ref, () => ({
    fetchAiAnalysis,
    loading,
    analysis
  }), [loading, analysis, aquariumData, backendUrl]);

  // Enviar reporte de diagnóstico incorrecto con consentimiento
  const handleSendFeedback = async (e) => {
    e.preventDefault();
    if (!feedbackConsent) {
      setFeedbackError('Debes otorgar tu consentimiento para enviar el reporte anónimo.');
      return;
    }
    if (!feedbackComment.trim()) {
      setFeedbackError('Por favor describe brevemente qué consideras incorrecto.');
      return;
    }

    setFeedbackSending(true);
    setFeedbackError(null);
    try {
      await sendDiagnosticFeedback({
        tank_id: aquariumData?.id || null,
        diagnosis_summary: analysis?.summary || analysis?.diagnostico_general || 'Diagnóstico evaluado',
        severity: analysis?.severity || analysis?.nivel_riesgo || 'unknown',
        user_comment: feedbackComment.trim(),
        category: 'incorrect_diagnosis',
        consent_given: true
      });
      setFeedbackSuccess(true);
      setFeedbackComment('');
      setTimeout(() => {
        setShowFeedbackModal(false);
      }, 2500);
    } catch (err) {
      setFeedbackError(err.message || 'Error al enviar el reporte. Inténtalo de nuevo.');
    } finally {
      setFeedbackSending(false);
    }
  };

  const getRiskBadgeColor = (nivel, severity) => {
    const sev = (severity || nivel || '').toLowerCase();
    if (sev === 'critical' || sev === 'crítico' || sev === 'colapso inminente') {
      return 'bg-red-500/20 text-red-400 border-red-500/50';
    }
    if (sev === 'warning' || sev === 'moderado') {
      return 'bg-amber-500/20 text-amber-400 border-amber-500/50';
    }
    if (sev === 'watch' || sev === 'probable') {
      return 'bg-blue-500/20 text-blue-300 border-blue-500/50';
    }
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
  };

  // Parámetros a mostrar con margen metrológico
  const currentParamsList = [
    { key: 'kh', label: 'Alcalinidad (KH)', val: aquariumData?.kh ?? aquariumData?.alkalinity_dkh },
    { key: 'calcio', label: 'Calcio (Ca)', val: aquariumData?.calcio ?? aquariumData?.calcium_ppm },
    { key: 'magnesio', label: 'Magnesio (Mg)', val: aquariumData?.magnesio ?? aquariumData?.magnesium_ppm },
    { key: 'nitrato', label: 'Nitrato (NO₃)', val: aquariumData?.nitrato ?? aquariumData?.nitrate_ppm },
    { key: 'fosfato', label: 'Fosfato (PO₄)', val: aquariumData?.fosfato ?? aquariumData?.phosphate_ppm },
    { key: 'salinidad', label: 'Salinidad', val: aquariumData?.salinidad ?? aquariumData?.salinity ?? aquariumData?.salinity_ppt },
    { key: 'temperatura', label: 'Temperatura', val: aquariumData?.temperatura ?? aquariumData?.temperature },
    { key: 'ph', label: 'pH', val: aquariumData?.ph }
  ].filter(p => p.val !== null && p.val !== undefined);

  return (
    <div className="p-6 bg-slate-900 rounded-xl text-slate-100 max-w-2xl mx-auto shadow-xl border border-slate-800">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h3 className="text-xl font-bold text-white flex items-center">
          <img 
            src="/robot-fish.jpg" 
            alt="AquaPulse AI" 
            className="w-8 h-8 mr-3 rounded-lg shadow-lg border border-cyan-500/30 object-cover" 
          />
          Diagnóstico y Verificación AquaPulse
        </h3>
        <button
          onClick={fetchAiAnalysis}
          disabled={loading}
          className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-slate-950 font-semibold rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <RotateCw className="w-4 h-4 animate-spin text-slate-950" />
              <span>Verificando con IA...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 text-slate-950" />
              <span>Analizar Agua</span>
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="p-3 mb-4 bg-red-500/10 border border-red-500/40 text-red-400 rounded-lg text-sm flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {analysis && (
        <div className="space-y-4 mt-4">
          {/* AVISO FIJO PUESTO POR EL BACKEND (Fase 5) */}
          <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs rounded-lg flex items-center gap-2.5">
            <Info className="w-4 h-4 shrink-0 text-amber-400" />
            <span className="font-medium">
              {analysis.disclaimer || "Orientativo, generado por IA y puede contener errores. Verifica con un retest."}
            </span>
          </div>

          {/* Tarjeta de Severidad Global */}
          <div className={`p-4 rounded-lg border ${getRiskBadgeColor(analysis.nivel_riesgo, analysis.severity)}`}>
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs uppercase tracking-wider font-semibold opacity-80">Severidad de Estado:</span>
                <h4 className="text-lg font-bold uppercase">{analysis.severity || analysis.nivel_riesgo}</h4>
              </div>
              {analysis.overall_confidence !== undefined && (
                <div className="text-right">
                  <span className="text-xs uppercase tracking-wider font-semibold opacity-80">Certeza:</span>
                  <p className="text-base font-bold font-mono">{(analysis.overall_confidence * 100).toFixed(0)}%</p>
                </div>
              )}
            </div>
            {analysis.needs_retest && (
              <div className="mt-2 text-xs font-semibold text-blue-300 flex items-center gap-1.5 bg-blue-950/40 px-2 py-1 rounded border border-blue-800/40">
                <Clock className="w-3.5 h-3.5 text-blue-400" />
                <span>Retest recomendado en 1–2 h para descartar márgenes de incertidumbre.</span>
              </div>
            )}
          </div>

          {/* SECCIÓN 1: REGLAS DETERMINÍSTICAS (INAPELABLE) CON MÁRGENES ± */}
          <div className="p-4 bg-slate-800/70 rounded-lg border border-blue-500/30">
            <div className="flex items-center justify-between mb-2.5">
              <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                Reglas (Inapelable)
              </span>
              <span className="text-xs text-slate-400">Valores con Margen de Error (±)</span>
            </div>

            {/* Listado de Valores con Margen de Error Metrológico */}
            {currentParamsList.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 my-2">
                {currentParamsList.map(p => (
                  <div key={p.key} className="bg-slate-900/60 p-2 rounded border border-slate-700/60 text-xs">
                    <span className="text-slate-400 block">{p.label}</span>
                    <span className="font-semibold text-slate-200">
                      {getMeasurementMarginText(p.key, p.val)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Alerta Predictiva de 48h de las reglas */}
            <p className="text-xs text-slate-300 mt-2 bg-slate-900/40 p-2.5 rounded border border-slate-700/40">
              <span className="text-cyan-300 font-semibold block mb-0.5">Evaluación Determinística:</span>
              {analysis.alerta_predictiva}
            </p>
          </div>

          {/* SECCIÓN 2: IA AQUAPULSE (INTERPRETACIÓN / CONTEXTO) */}
          <div className="p-4 bg-slate-800/70 rounded-lg border border-cyan-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                IA (Interpretación)
              </span>
              <span className="text-xs text-slate-400">Contexto Biológico</span>
            </div>
            <p className="text-sm text-slate-200 mb-3 leading-relaxed">
              {analysis.diagnostico_general || analysis.summary}
            </p>

            {/* Hallazgos específicos con confianza */}
            {analysis.findings && analysis.findings.length > 0 && (
              <div className="space-y-1.5 mt-2">
                <span className="text-xs font-semibold text-slate-400 block">Hallazgos Específicos:</span>
                {analysis.findings.map((f, idx) => (
                  <div key={idx} className="text-xs bg-slate-900/50 p-2 rounded flex justify-between items-start gap-2 border border-slate-800">
                    <div>
                      <span className="font-semibold text-cyan-300 uppercase mr-1.5">[{f.parameter}]:</span>
                      <span className="text-slate-300">{f.observation}</span>
                    </div>
                    {f.confidence !== undefined && (
                      <span className="shrink-0 px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">
                        {(f.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Acciones del Catálogo Cerrado */}
            {analysis.recommended_actions && analysis.recommended_actions.length > 0 && (
              <div className="mt-3 pt-2.5 border-t border-slate-700/60">
                <span className="text-xs font-semibold text-slate-400 block mb-1.5">Acciones Recomendadas (Catálogo Seguro):</span>
                <div className="flex flex-wrap gap-1.5">
                  {analysis.recommended_actions.map((act, i) => (
                    <span key={i} className="px-2 py-1 bg-cyan-950/60 text-cyan-300 border border-cyan-700/50 rounded text-xs font-medium">
                      ✓ {act.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* BOTÓN: REPORTAR DIAGNÓSTICO INCORRECTO (Fase 5) */}
          <div className="flex justify-end pt-2">
            <button
              onClick={() => {
                setShowFeedbackModal(true);
                setFeedbackSuccess(false);
                setFeedbackError(null);
              }}
              className="text-xs text-slate-400 hover:text-amber-300 flex items-center gap-1.5 transition py-1 px-2.5 rounded hover:bg-slate-800"
            >
              <Flag className="w-3.5 h-3.5" />
              <span>Reportar diagnóstico incorrecto</span>
            </button>
          </div>
        </div>
      )}

      {/* MODAL DE REPORTE CON CONSENTIMIENTO (Fase 5) */}
      {showFeedbackModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 max-w-md w-full shadow-2xl relative text-slate-100">
            <button
              onClick={() => setShowFeedbackModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h4 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
              <Flag className="w-5 h-5 text-amber-400" />
              Reportar Diagnóstico Incorrecto
            </h4>
            <p className="text-xs text-slate-300 mb-4 leading-relaxed">
              Tu reporte ayuda a auditar el modelo de IA y corregir discrepancias para garantizar la máxima seguridad en el acuario.
            </p>

            {feedbackSuccess ? (
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/40 text-emerald-300 rounded-lg text-sm text-center space-y-1">
                <CheckCircle className="w-8 h-8 mx-auto text-emerald-400 mb-2" />
                <p className="font-semibold">¡Reporte recibido!</p>
                <p className="text-xs text-emerald-400/90">Gracias por colaborar con la seguridad y precisión de AquaPulse.</p>
              </div>
            ) : (
              <form onSubmit={handleSendFeedback} className="space-y-4">
                {feedbackError && (
                  <div className="p-2.5 bg-red-500/10 border border-red-500/40 text-red-400 rounded text-xs">
                    {feedbackError}
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    ¿Qué consideras erróneo o impreciso en este diagnóstico?
                  </label>
                  <textarea
                    rows={3}
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                    placeholder="Ej. La IA sugirió cambio de agua cuando los nitratos están en cero..."
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                    required
                  />
                </div>

                {/* Consentimiento Explícito Obligatorio (Fase 5) */}
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <label className="flex items-start gap-2.5 cursor-pointer text-xs text-slate-300 leading-snug">
                    <input
                      type="checkbox"
                      checked={feedbackConsent}
                      onChange={(e) => setFeedbackConsent(e.target.checked)}
                      className="mt-0.5 rounded border-slate-700 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-900"
                    />
                    <span>
                      Doy mi <strong>consentimiento explícito</strong> para remitir de forma anónima los datos de esta medición y este diagnóstico para la auditoría y mejora continua del modelo de IA.
                    </span>
                  </label>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowFeedbackModal(false)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-medium transition"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={feedbackSending || !feedbackConsent}
                    className="px-4 py-1.5 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-slate-950 font-semibold rounded text-xs flex items-center gap-1.5 transition"
                  >
                    {feedbackSending ? (
                      <>
                        <RotateCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Enviando...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        <span>Enviar Reporte</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

export default ReefAnalysisCard;
