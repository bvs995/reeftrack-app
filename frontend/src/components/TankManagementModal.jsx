import React, { useState, useEffect } from 'react';
import { X, Check, Waves } from 'lucide-react';
import { createTank, updateTank } from '../api';
import { normalizeProfileKey } from '../utils/marineProfiles';

export default function TankManagementModal({
  isOpen,
  onClose,
  onTankCreated,
  existingTank = null, // Prop: Si le pasas un acuario, el modal cambia a modo "Edición"
  onTankUpdated = null
}) {
  const [name, setName] = useState('');
  const [tankType, setTankType] = useState('lps_reef');
  const [volumeLiters, setVolumeLiters] = useState('');
  const [dosingMethod, setDosingMethod] = useState('water_changes');
  const [lightingPar, setLightingPar] = useState('');
  const [flowProfile, setFlowProfile] = useState('moderate_indirect');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isMarine = ['fish_only', 'mixed_reef', 'lps_reef', 'sps_reef'].includes(tankType);
  const hasCoralEquipment = ['mixed_reef', 'lps_reef', 'sps_reef'].includes(tankType);

  // Cargar datos automáticamente si estamos editando un acuario existente
  useEffect(() => {
    if (existingTank && isOpen) {
      setName(existingTank.name || '');
      const rawKey = existingTank.reef_profile || existingTank.tank_type || existingTank.type;
      const nType = normalizeProfileKey(rawKey);
      setTankType(nType);
      setVolumeLiters(existingTank.volume_liters || '');
      setNotes(existingTank.notes || '');
      setDosingMethod(existingTank.dosing_method || 'water_changes');
      setLightingPar(existingTank.lighting_par !== null && existingTank.lighting_par !== undefined ? String(existingTank.lighting_par) : '');
      setFlowProfile(existingTank.flow_profile || (nType === 'sps_reef' ? 'high_turbulent' : 'moderate_indirect'));
    } else if (!existingTank && isOpen) {
      // Limpiar formulario si es creación nueva
      setName('');
      setTankType('lps_reef');
      setVolumeLiters('');
      setNotes('');
      setDosingMethod('water_changes');
      setLightingPar('');
      setFlowProfile('moderate_indirect');
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
      const payload = {
        name: name.trim(),
        tank_type: tankType,
        type: tankType,
        volume_liters: parseFloat(volumeLiters),
        reef_profile: isMarine ? tankType : null,
        dosing_method: hasCoralEquipment ? (dosingMethod || 'water_changes') : null,
        lighting_par: hasCoralEquipment && lightingPar !== '' ? parseInt(lightingPar, 10) : null,
        flow_profile: hasCoralEquipment ? (flowProfile || 'moderate_indirect') : null,
        notes: notes.trim() || undefined
      };

      if (existingTank) {
        // MODO EDICIÓN
        const res = await updateTank(existingTank.id, payload);
        const mergedTank = {
          ...existingTank,
          ...payload,
          ...(typeof res === 'object' ? res : {}),
          id: existingTank.id,
          name: name.trim(),
          tank_type: tankType,
          type: tankType,
          volume_liters: parseFloat(volumeLiters),
          reef_profile: payload.reef_profile,
          dosing_method: payload.dosing_method,
          lighting_par: payload.lighting_par,
          flow_profile: payload.flow_profile
        };
        triggerHaptic();
        if (onTankUpdated) onTankUpdated(mergedTank);
      } else {
        // MODO CREACIÓN
        const newTank = await createTank(payload);
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
      <div className="relative w-full max-w-md bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80 flex-shrink-0">
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
          <div className="mx-4 mt-3 p-3.5 rounded-2xl bg-coral-500/15 border border-coral-500/40 text-coral-300 text-xs font-semibold flex-shrink-0">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-4 sm:p-5 space-y-4 overflow-y-auto">
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
              Tipo de Acuario / Biotipo (6 Ecosistemas)
            </label>
            <select
              value={tankType}
              onChange={(e) => {
                const newT = e.target.value;
                setTankType(newT);
                if (newT === 'sps_reef' && flowProfile === 'moderate_indirect') {
                  setFlowProfile('high_turbulent');
                } else if (newT === 'lps_reef' && flowProfile === 'high_turbulent') {
                  setFlowProfile('moderate_indirect');
                }
              }}
              className="w-full min-h-[48px] bg-marine-950 border border-marine-700 focus:border-cyan-400 rounded-xl px-3.5 text-sm text-white focus:outline-none font-semibold shadow-inner cursor-pointer"
            >
              <option value="freshwater">1. Agua Dulce</option>
              <option value="planted">2. Plantado</option>
              <option value="fish_only">3. Solo Peces (Marino FOWLR)</option>
              <option value="mixed_reef">4. Arrecife Mixto (Blandos + LPS + SPS)</option>
              <option value="lps_reef">5. Arrecife LPS (Corales de Pólipo Largo)</option>
              <option value="sps_reef">6. Arrecife SPS (Corales de Pólipo Corto)</option>
            </select>
          </div>

          {/* Configuración de equipamiento coralino si aplica */}
          {hasCoralEquipment && (
            <div className="p-3.5 rounded-2xl bg-cyan-950/30 border border-cyan-500/20 space-y-3">
              <div className="text-[11px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                Parámetros de Equipamiento y Flujo
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                    Método de Dosificación
                  </label>
                  <select
                    value={dosingMethod}
                    onChange={(e) => setDosingMethod(e.target.value)}
                    className="w-full min-h-[42px] bg-slate-900/90 border border-cyan-500/30 focus:border-cyan-400 rounded-xl px-3 text-xs text-white focus:outline-none font-semibold"
                  >
                    <option value="water_changes">Cambios de Agua</option>
                    <option value="manual_dosing">Dosificación Manual</option>
                    <option value="peristaltic_balling">Balling / Peristálticas</option>
                    <option value="kalkwasser">Kalkwasser (Agua de Cal)</option>
                    <option value="calcium_reactor">Reactor de Calcio (CaRx)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                    Iluminación PAR (estimado)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="1000"
                    placeholder="Ej. 180"
                    value={lightingPar}
                    onChange={(e) => setLightingPar(e.target.value)}
                    className="w-full min-h-[42px] bg-slate-900/90 border border-cyan-500/30 focus:border-cyan-400 rounded-xl px-3 text-xs text-white focus:outline-none placeholder-slate-500 font-semibold"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                  Perfil de Flujo / Circulación
                </label>
                <select
                  value={flowProfile}
                  onChange={(e) => setFlowProfile(e.target.value)}
                  className="w-full min-h-[42px] bg-slate-900/90 border border-cyan-500/30 focus:border-cyan-400 rounded-xl px-3 text-xs text-white focus:outline-none font-semibold"
                >
                  <option value="low_moderate">Bajo a Moderado</option>
                  <option value="moderate_indirect">Moderado e Indirecto (Recomendado LPS)</option>
                  <option value="high_turbulent">Alto, Turbulento y Variable (Recomendado SPS)</option>
                </select>
              </div>
            </div>
          )}

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