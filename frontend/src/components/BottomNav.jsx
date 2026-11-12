import React from 'react';
import { LayoutDashboard, LineChart, Plus, Droplets } from 'lucide-react';

export default function BottomNav({ activeTab, onSelectTab, onOpenQuickLog }) {
  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'trends', label: 'Tendencias', icon: LineChart },
    { id: 'water', label: 'Cambios', icon: Droplets },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-marine-950/95 backdrop-blur-2xl border-t border-marine-800/90 px-3 py-2 safe-bottom sm:hidden shadow-2xl">
      <div className="flex items-center justify-around relative">
        {tabs.slice(0, 2).map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                triggerHaptic();
                onSelectTab(tab.id);
              }}
              className={`min-h-[52px] min-w-[64px] flex flex-col items-center justify-center gap-1 transition-all active:scale-90 ${
                isActive
                  ? 'text-cyan-400 font-black'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5] drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]' : ''}`} />
              <span className="text-[11px] font-bold">{tab.label}</span>
            </button>
          );
        })}

        {/* Botón Flotante Central Grande Especial para Dedos Mojados */}
        <div className="relative -top-6">
          <button
            onClick={() => {
              triggerHaptic();
              onOpenQuickLog();
            }}
            className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500 via-cyan-400 to-emerald-400 text-marine-950 flex items-center justify-center shadow-neon-cyan active:scale-90 transition-all border-2 border-white/30"
            title="Registrar Test Rápido"
            aria-label="Registrar Test Rápido"
          >
            <Plus className="w-8 h-8 stroke-[3]" />
          </button>
        </div>

        {tabs.slice(2).map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                triggerHaptic();
                onSelectTab(tab.id);
              }}
              className={`min-h-[52px] min-w-[64px] flex flex-col items-center justify-center gap-1 transition-all active:scale-90 ${
                isActive
                  ? 'text-cyan-400 font-black'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5] drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]' : ''}`} />
              <span className="text-[11px] font-bold">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
