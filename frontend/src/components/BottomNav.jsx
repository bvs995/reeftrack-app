import React from 'react';
import { useTranslation } from 'react-i18next';
import { LayoutDashboard, LineChart, Plus, Droplets, Settings } from 'lucide-react';

export default function BottomNav({ activeTab, onSelectTab, onOpenQuickLog }) {
  const { t } = useTranslation();

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const leftTabs = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { id: 'trends', label: t('nav.trends'), icon: LineChart },
  ];

  const rightTabs = [
    { id: 'water', label: t('nav.water'), icon: Droplets },
    { id: 'settings', label: t('nav.settings'), icon: Settings },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-marine-950/95 backdrop-blur-2xl border-t border-marine-800/90 px-2 sm:px-4 py-2 safe-bottom sm:hidden shadow-2xl">
      <div className="flex items-center justify-around relative">
        {/* Pestañas de la izquierda */}
        {leftTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                triggerHaptic();
                onSelectTab(tab.id);
              }}
              className={`min-h-[50px] min-w-[56px] flex flex-col items-center justify-center gap-1 transition-all active:scale-90 ${
                isActive
                  ? 'text-cyan-400 font-black'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5] drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]' : ''}`} />
              <span className="text-[10px] font-bold">{tab.label}</span>
            </button>
          );
        })}

        {/* Botón Flotante Central Grande Especial para Dedos Mojados */}
        <div className="relative -top-5">
          <button
            onClick={() => {
              triggerHaptic();
              onOpenQuickLog();
            }}
            className="w-13 h-13 sm:w-14 sm:h-14 p-3 rounded-2xl bg-gradient-to-tr from-cyan-500 via-cyan-400 to-emerald-400 text-marine-950 flex items-center justify-center shadow-neon-cyan active:scale-90 transition-all border-2 border-white/30"
            title={t('nav.quickLog')}
            aria-label={t('nav.quickLog')}
          >
            <Plus className="w-7 h-7 stroke-[3]" />
          </button>
        </div>

        {/* Pestañas de la derecha */}
        {rightTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                triggerHaptic();
                onSelectTab(tab.id);
              }}
              className={`min-h-[50px] min-w-[56px] flex flex-col items-center justify-center gap-1 transition-all active:scale-90 ${
                isActive
                  ? 'text-cyan-400 font-black'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5] drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]' : ''}`} />
              <span className="text-[10px] font-bold">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
