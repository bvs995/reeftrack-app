import React, { useState, useEffect } from 'react';
import {
  X,
  Droplets,
  Layers,
  Sparkles,
  Delete
} from 'lucide-react';
import QuickEntryForm from './QuickEntryForm';
import { recordMeasurement } from '../api';

export default function QuickLogModal({
  isOpen,
  onClose,
  tank,
  parameters = [],
  preselectedCode = null,
  onSuccess
}) {
  // 'form' para el formulario en tarjetas compactas con teclado numérico
  // 'numpad' para el teclado virtual de 1 parámetro en pantalla
  const [mode, setMode] = useState('form');
  const [selectedParam, setSelectedParam] = useState(null);
  const [value, setValue] = useState('');
  const [notes, setNotes] = useState('');
  const [measuredAt, setMeasuredAt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      const initial = preselectedCode
        ? parameters.find(p => p.code === preselectedCode) || parameters[0]
        : parameters[0];
      setSelectedParam(initial);
      setValue(initial ? String(initial.optimal_target || '') : '');
      setNotes('');
      setMeasuredAt(new Date().toISOString().slice(0, 16));

      // Si el usuario abrió el modal tocando un parámetro específico en la tarjeta, abrir modo numpad
      if (preselectedCode) {
        setMode('numpad');
      } else {
        setMode('form');
      }
    }
  }, [isOpen, preselectedCode, parameters]);

  if (!isOpen || !tank) return null;

  const triggerHaptic = (ms = 20) => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(ms);
    }
  };

  const handleSelectParam = (p) => {
    triggerHaptic();
    setSelectedParam(p);
    setValue(p.optimal_target ? String(p.optimal_target) : '');
  };

  const handleNumpadPress = (char) => {
    triggerHaptic();
    if (char === '.') {
      if (!value.includes('.')) {
        setValue(value === '' ? '0.' : value + '.');
      }
    } else {
      if (value === '0') {
        setValue(char);
      } else {
        setValue(value + char);
      }
    }
  };

  const handleBackspace = () => {
    triggerHaptic();
    setValue(prev => prev.slice(0, -1));
  };

  const handleIncrement = (delta) => {
    triggerHaptic();
    const cur = parseFloat(value) || 0;
    const decimals = delta.toString().includes('.') ? delta.toString().split('.')[1].length : 0;
    setValue((cur + delta).toFixed(decimals));
  };

  const handleSubmitSingle = async (e) => {
    if (e) e.preventDefault();
    if (!value || isNaN(parseFloat(value))) {
      setError('Ingresa un valor numérico válido.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const codeMap = {
        dkh: 'alkalinity_dkh',
        alkalinity: 'alkalinity_dkh',
        alkalinity_dkh: 'alkalinity_dkh',
        ca: 'calcium_ppm',
        calcium: 'calcium_ppm',
        calcium_ppm: 'calcium_ppm',
        mg: 'magnesium_ppm',
        magnesium: 'magnesium_ppm',
        magnesium_ppm: 'magnesium_ppm',
        no3: 'nitrate_ppm',
        nitrate: 'nitrate_ppm',
        nitrate_ppm: 'nitrate_ppm',
        po4: 'phosphate_ppm',
        phosphate: 'phosphate_ppm',
        phosphate_ppm: 'phosphate_ppm',
        salinity: 'salinity_ppt',
        salinity_ppt: 'salinity_ppt'
      };

      const fieldKey = codeMap[selectedParam?.code] || selectedParam?.code || 'alkalinity_dkh';
      const numVal = parseFloat(value);
      const isoTimestamp = measuredAt ? new Date(measuredAt).toISOString() : new Date().toISOString();

      await recordMeasurement(tank.id, {
        tank_id: tank.id,
        [fieldKey]: numVal,
        parameter_code: selectedParam?.code,
        value: numVal,
        timestamp: isoTimestamp,
        measured_at: isoTimestamp,
        notes: notes?.trim() || undefined
      });
      triggerHaptic(40);
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setError(err.message || 'Error al guardar medición');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header Náutico Neón */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center shadow-neon-cyan">
              <Droplets className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-white text-base sm:text-lg tracking-tight">
                Registrar Mediciones
              </h3>
              <p className="text-xs text-cyan-400 font-semibold">{tank.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl bg-marine-800 hover:bg-marine-700 text-slate-400 hover:text-white flex items-center justify-center transition active:scale-90"
            aria-label="Cerrar modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Selector de Pestañas Grandes */}
        <div className="grid grid-cols-2 p-2 bg-marine-950/60 border-b border-marine-800 gap-2">
          <button
            type="button"
            onClick={() => { triggerHaptic(); setMode('form'); }}
            className={`min-h-[46px] flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs sm:text-sm font-black transition ${
              mode === 'form'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/60 shadow-neon-cyan'
                : 'text-slate-400 hover:text-slate-200 hover:bg-marine-800'
            }`}
          >
            <Layers className="w-4 h-4 text-cyan-400" />
            Tarjetas de Parámetros
          </button>

          <button
            type="button"
            onClick={() => { triggerHaptic(); setMode('numpad'); }}
            className={`min-h-[46px] flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs sm:text-sm font-black transition ${
              mode === 'numpad'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/60 shadow-neon-cyan'
                : 'text-slate-400 hover:text-slate-200 hover:bg-marine-800'
            }`}
          >
            <Sparkles className="w-4 h-4 text-cyan-400" />
            Numpad 1 Parámetro
          </button>
        </div>

        {error && (
          <div className="mx-4 mt-3 p-3.5 rounded-2xl bg-coral-500/15 border border-coral-500/40 text-coral-300 text-xs font-semibold">
            {error}
          </div>
        )}

        {/* Contenido con Scroll */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1">
          {mode === 'form' ? (
            /* COMPONENTE QUICK ENTRY FORM */
            <QuickEntryForm
              tank={tank}
              tankId={tank?.id}
              onSuccess={() => {
                if (onSuccess) onSuccess();
                onClose();
              }}
              onCancel={onClose}
            />
          ) : (
            /* MODO NUMPAD 1 PARÁMETRO PARA DEDOS MOJADOS */
            <div className="space-y-4">
              <div>
                <label className="block text-[11px] font-black uppercase tracking-wider text-slate-400 mb-2">
                  Selecciona Parámetro a Registrar
                </label>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                  {parameters.map((p) => {
                    const isSelected = selectedParam?.code === p.code;
                    return (
                      <button
                        key={p.code}
                        type="button"
                        onClick={() => handleSelectParam(p)}
                        className={`min-h-[50px] p-2 rounded-xl border text-center transition flex flex-col justify-center items-center ${
                          isSelected
                            ? 'bg-cyan-500/25 border-cyan-400 text-white shadow-neon-cyan ring-2 ring-cyan-400/50'
                            : 'bg-marine-800/80 border-marine-700/80 text-slate-300 hover:bg-marine-800'
                        }`}
                      >
                        <span className="font-extrabold text-xs truncate max-w-full">
                          {p.name.split('(')[0]}
                        </span>
                        <span className="text-[10px] text-cyan-400 font-bold">
                          {p.unit}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {selectedParam && (
                <div className="bg-marine-950/90 p-4 rounded-2xl border border-marine-800 space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-extrabold text-slate-200">
                      Valor ({selectedParam.unit})
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Óptimo: <strong className="text-emerald-400">{selectedParam.optimal_target} {selectedParam.unit}</strong>
                    </span>
                  </div>

                  <div className="bg-marine-900 border-2 border-cyan-500/50 rounded-2xl p-3 text-center shadow-neon-cyan relative flex items-center justify-center">
                    <span className="text-4xl sm:text-5xl font-black text-white tracking-widest min-h-[50px] flex items-center">
                      {value || '0'}
                    </span>
                    <span className="absolute right-4 text-xs font-bold text-cyan-400 uppercase">
                      {selectedParam.unit}
                    </span>
                  </div>

                  {/* Bumps rápidos */}
                  <div className="flex items-center justify-center gap-1.5 flex-wrap pt-1">
                    {selectedParam.code === 'salinity' ? (
                      <>
                        <button type="button" onClick={() => { triggerHaptic(); setValue('1.024'); }} className="quick-bump">1.024</button>
                        <button type="button" onClick={() => { triggerHaptic(); setValue('1.025'); }} className="quick-bump active">1.025</button>
                        <button type="button" onClick={() => { triggerHaptic(); setValue('1.026'); }} className="quick-bump">1.026</button>
                        <button type="button" onClick={() => handleIncrement(0.001)} className="quick-bump">+0.001</button>
                      </>
                    ) : (
                      <>
                        <button type="button" onClick={() => handleIncrement(-0.5)} className="quick-bump">-0.5</button>
                        <button type="button" onClick={() => handleIncrement(-0.1)} className="quick-bump">-0.1</button>
                        <button type="button" onClick={() => handleIncrement(0.1)} className="quick-bump">+0.1</button>
                        <button type="button" onClick={() => handleIncrement(0.5)} className="quick-bump">+0.5</button>
                      </>
                    )}
                  </div>

                  {/* Teclado táctil virtual */}
                  <div className="grid grid-cols-3 gap-2 pt-2">
                    {['1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '0'].map((digit) => (
                      <button
                        key={digit}
                        type="button"
                        onClick={() => handleNumpadPress(digit)}
                        className="numpad-key"
                      >
                        {digit}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={handleBackspace}
                      className="numpad-key text-coral-400"
                    >
                      <Delete className="w-6 h-6" />
                    </button>
                  </div>
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-3 safe-bottom">
                <button
                  type="button"
                  onClick={onClose}
                  className="btn-touch-secondary flex-1 sm:flex-none"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleSubmitSingle}
                  disabled={loading}
                  className="btn-touch-primary flex-1 sm:flex-none"
                >
                  {loading ? 'Guardando...' : 'Guardar Lectura'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
