import React, { useState, useEffect } from 'react';
import { X, Check, Waves } from 'lucide-react';
// Asegúrate de tener updateTank exportado en tu archivo api.js
import { createTank, updateTank } from '../api';

export default function TankManagementModal({
  isOpen,
  onClose,
  onTankCreated,
  existingTank = null, // Prop nueva: Si le pasas un acuario, el modal cambia a modo "Edición"
  onTankUpdated = null
}) {
  const [name, setName] = useState('');
  const [tankType, setTankType] = useState('arrecife');
  const [volumeLiters, setVolumeLiters] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const normalizeTankType = (type) => {
    if (!type) return 'arrecife';
    const t = String(type).toLowerCase();
    if (t === 'reef') return 'arrecife';
    if (t === 'mixto') return 'mixed';
    if (t === 'peces_marinos') return 'marine_fish';
    if (t === 'freshwater_planted') return 'plantado';
    if (t === 'freshwater_community') return 'dulce';
    return t;
  };

  // Cargar datos automáticamente si estamos editando un acuario existente
  useEffect(() => {
    if (existingTank && isOpen) {
      setName(existingTank.name || '');
      setTankType(normalizeTankType(existingTank.tank_type || existingTank.type));
      setVolumeLiters(existingTank.volume_liters || '');
      setNotes(existingTank.notes || '');
    } else if (!existingTank && isOpen) {
      // Limpiar formulario si es creación nueva
      setName('');
      setTankType('arrecife');
      setVolumeLiters('');
      setNotes('');
    }
  }, [existingTank, isOpen]);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !volumeLiters || parseFloat(volumeLiters) <= 0) {
      setError('Por favor completa el nombre y un volumen válido en litros.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      if (existingTank) {
        // MODO EDICIÓN
        const payload = {
          name: name.trim(),
          tank_type: tankType,
          type: tankType,
          volume_liters: parseFloat(volumeLiters),
          notes: notes.trim() || undefined
        };
        const res = await updateTank(existingTank.id, payload);
        const mergedTank = {
          ...existingTank,
          ...payload,
          ...(typeof res === 'object' ? res : {}),
          id: existingTank.id,
          name: name.trim(),
          tank_type: tankType,
          type: tankType,
          volume_liters: parseFloat(volumeLiters)
        };
        triggerHaptic();
        if (onTankUpdated) onTankUpdated(mergedTank);
      } else {
        // MODO CREACIÓN
        const newTank = await createTank({
          name: name.trim(),
          tank_type: tankType,
          volume_liters: parseFloat(volumeLiters),
          notes: notes.trim() || undefined
        });
        triggerHaptic();
        if (onTankCreated) onTankCreated(newTank);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Error al procesar el acuario');
    } finally {
      setLoading(false);
    }
  };

  const isEditing = !!existingTank;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center shadow-neon-cyan">
              <Waves className="w-5 h-5" />
            </div>
            <h3 className="font-extrabold text-white text-base sm:text-lg">
              {isEditing ? 'Editar Acuario' : 'Crear Nuevo Acuario'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl bg-marine-800 text-slate-400 hover:text-white flex items-center justify-center transition active:scale-90"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mx-4 mt-3 p-3.5 rounded-2xl bg-coral-500/15 border border-coral-500/40 text-coral-300 text-xs font-semibold">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-4 sm:p-5 space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Nombre del Acuario
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej. Arrecife SPS 250L o Iwagumi Plantado"
              className="w-full min-h-[48px] bg-marine-950 border border-marine-700 focus:border-cyan-400 rounded-xl px-3.5 text-sm text-white focus:outline-none placeholder-slate-500 font-semibold shadow-inner"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Biotipo / Ecosistema
            </label>
            <select
              value={tankType}
              onChange={(e) => setTankType(e.target.value)}
              className="w-full min-h-[48px] bg-marine-950 border border-marine-700 focus:border-cyan-400 rounded-xl px-3.5 text-sm text-white focus:outline-none font-semibold shadow-inner cursor-pointer"
            >
              <option value="arrecife">Arrecife (Solo Corales)</option>
              <option value="mixed">Arrecife Mixto (Corales y Peces)</option>
              <option value="marine_fish">Solo Peces Marinos</option>
              <option value="plantado">Agua Dulce Plantado</option>
              <option value="dulce">Agua Dulce Estándar</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Volumen Neto (Litros de Agua)
            </label>
            <input
              type="number"
              step="1"
              required
              value={volumeLiters}
              onChange={(e) => setVolumeLiters(e.target.value)}
              placeholder="Ej. 280"
              className="w-full min-h-[48px] bg-marine-950 border border-marine-700 focus:border-cyan-400 rounded-xl px-3.5 text-sm text-white focus:outline-none placeholder-slate-500 font-semibold shadow-inner"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Equipamiento / Filtración
            </label>
            <textarea
              rows="2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Skimmer Deltec, Bombas Nero 5, Radion G6, Reactor de Medios..."
              className="w-full bg-marine-950 border border-marine-700 focus:border-cyan-400 rounded-xl p-3 text-xs text-white focus:outline-none placeholder-slate-500 font-medium"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-3 safe-bottom">
            <button
              type="button"
              onClick={onClose}
              className="btn-touch-secondary flex-1 sm:flex-none"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-touch-primary flex-1 sm:flex-none"
            >
              <Check className="w-5 h-5 stroke-[3]" />
              <span>{loading ? 'Guardando...' : (isEditing ? 'Guardar Cambios' : 'Crear Acuario')}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}