import React, { useState } from 'react';
import { X, Plus, Droplets, Waves, Check } from 'lucide-react';
import { createTank } from '../api';

export default function TankManagementModal({
  isOpen,
  onClose,
  onTankCreated
}) {
  const [name, setName] = useState('');
  const [tankType, setTankType] = useState('reef');
  const [volumeLiters, setVolumeLiters] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
      const newTank = await createTank({
        name: name.trim(),
        tank_type: tankType,
        volume_liters: parseFloat(volumeLiters),
        notes: notes.trim() || undefined
      });
      triggerHaptic();
      onTankCreated(newTank);
      onClose();
    } catch (err) {
      setError(err.message || 'Error al crear acuario');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center shadow-neon-cyan">
              <Waves className="w-5 h-5" />
            </div>
            <h3 className="font-extrabold text-white text-base sm:text-lg">Crear Nuevo Acuario</h3>
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
            <div className="grid grid-cols-3 gap-2">
              {[
                { type: 'reef', label: '🪸 Arrecife', desc: 'Corales y peces' },
                { type: 'freshwater_planted', label: '🌿 Plantado', desc: 'Aquascaping CO2' },
                { type: 'freshwater_community', label: '🐟 Dulce', desc: 'Comunitario' },
              ].map((item) => (
                <button
                  key={item.type}
                  type="button"
                  onClick={() => {
                    triggerHaptic();
                    setTankType(item.type);
                  }}
                  className={`min-h-[56px] p-2 rounded-xl border text-center transition flex flex-col justify-center items-center active:scale-95 ${
                    tankType === item.type
                      ? 'bg-cyan-500/25 border-cyan-400 text-white shadow-neon-cyan ring-2 ring-cyan-400/50'
                      : 'bg-marine-950 border-marine-800 text-slate-400 hover:text-white'
                  }`}
                >
                  <span className="text-xs font-black">{item.label}</span>
                  <span className="text-[10px] text-slate-400 mt-0.5 font-medium">{item.desc}</span>
                </button>
              ))}
            </div>
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
              <span>{loading ? 'Creando...' : 'Crear Acuario'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
