import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import DashboardTrends from './components/DashboardTrends';
import TrendsView from './components/TrendsView';
import WaterChangesView from './components/WaterChangesView';
import QuickLogModal from './components/QuickLogModal';
import TankManagementModal from './components/TankManagementModal';
import NotificationModal from './components/NotificationModal';
import BottomNav from './components/BottomNav';
import ErrorBoundary from './components/ErrorBoundary';
import {
  fetchTanks,
  fetchTankParameters,
  fetchTankAnalytics,
  fetchPredictions
} from './api';
import { evaluateScheduledReminder } from './utils/notifications';
import {
  LayoutDashboard,
  LineChart,
  Droplets,
  WifiOff,
  Sparkles
} from 'lucide-react';

export default function App() {
  const [tanks, setTanks] = useState([]);
  const [activeTank, setActiveTank] = useState(null);
  const [parameters, setParameters] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window !== 'undefined') {
      const paramTab = new URLSearchParams(window.location.search).get('tab');
      if (paramTab) return paramTab;
    }
    return 'trends';
  });

  const [isQuickLogOpen, setIsQuickLogOpen] = useState(false);
  const [preselectedCode, setPreselectedCode] = useState(null);
  const [isNewTankOpen, setIsNewTankOpen] = useState(false);
  const [isNotificationModalOpen, setIsNotificationModalOpen] = useState(false);
  const [selectedCodeForChart, setSelectedCodeForChart] = useState(null);

  const [isOnline, setIsOnline] = useState(navigator.onLine);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  // Temporizador para evaluar recordatorios locales programados
  useEffect(() => {
    const checkReminder = async () => {
      try {
        const preds = await fetchPredictions();
        if (preds) {
          await evaluateScheduledReminder(preds);
        }
      } catch (e) {
        // Silencioso en segundo plano
      }
    };

    // Evaluar al cargar y luego cada 60 segundos
    checkReminder();
    const interval = setInterval(checkReminder, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    loadTanks();
  }, []);

  useEffect(() => {
    if (activeTank) {
      loadTankDetails(activeTank.id);
    }
  }, [activeTank?.id]);

  const loadTanks = async () => {
    setLoading(true);
    try {
      const data = await fetchTanks();
      setTanks(data);
      if (data.length > 0) {
        setActiveTank(data[0]);
      }
    } catch (err) {
      console.error('Error al cargar acuarios:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadTankDetails = async (tankId) => {
    setLoading(true);
    try {
      const [paramsData, analyticsData] = await Promise.all([
        fetchTankParameters(tankId),
        fetchTankAnalytics(tankId)
      ]);
      setParameters(paramsData);
      setAnalytics(analyticsData);
      if (!selectedCodeForChart && paramsData.length > 0) {
        setSelectedCodeForChart(paramsData[0].code);
      }
    } catch (err) {
      console.error('Error al cargar datos del acuario:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenQuickLog = (code = null) => {
    triggerHaptic();
    setPreselectedCode(code);
    setIsQuickLogOpen(true);
  };

  const handleTankCreated = (newTank) => {
    setTanks([...tanks, newTank]);
    setActiveTank(newTank);
  };

  const handleDataUpdated = () => {
    if (activeTank) {
      loadTankDetails(activeTank.id);
    }
  };

  return (
    <div className="min-h-screen bg-marine-950 flex flex-col font-sans selection:bg-cyan-500 selection:text-marine-950">
      {/* Offline Alert Banner */}
      {!isOnline && (
        <div className="bg-amber-500/20 text-amber-300 border-b border-amber-500/40 px-4 py-2 text-xs font-bold flex items-center justify-center gap-2">
          <WifiOff className="w-4 h-4" />
          <span>Modo Sin Conexión activo. Las lecturas se conservan en caché local.</span>
        </div>
      )}

      {/* Main Top Navigation */}
      <Navbar
        tanks={tanks}
        activeTank={activeTank}
        onSelectTank={(tank) => {
          setActiveTank(tank);
          setSelectedCodeForChart(null);
        }}
        onOpenNewTankModal={() => setIsNewTankOpen(true)}
        onOpenNotificationModal={() => setIsNotificationModalOpen(true)}
        onRefresh={handleDataUpdated}
        loading={loading}
      />

      {/* Desktop Sub-Navigation Tabs */}
      <div className="hidden sm:block border-b border-marine-800/80 bg-marine-900/60 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-8">
          <button
            onClick={() => {
              triggerHaptic();
              setActiveTab('dashboard');
            }}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'dashboard'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Dashboard & Biometría</span>
          </button>

          <button
            onClick={() => {
              triggerHaptic();
              setActiveTab('trends');
            }}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'trends'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LineChart className="w-4 h-4" />
            <span>Gráficas & Proyección de Consumo</span>
          </button>

          <button
            onClick={() => {
              triggerHaptic();
              setActiveTab('water');
            }}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'water'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Droplets className="w-4 h-4" />
            <span>Cambios de Agua & Dilución</span>
          </button>
        </div>
      </div>

      {/* Main Content Area con ErrorBoundary */}
      <main className="flex-1">
        <ErrorBoundary>
          {activeTab === 'dashboard' && (
            <Dashboard
              analytics={analytics}
              loading={loading}
              onOpenQuickLog={handleOpenQuickLog}
              onOpenWaterChange={() => setActiveTab('water')}
              onSelectTab={setActiveTab}
              onSelectParameterForChart={(code) => setSelectedCodeForChart(code)}
              onMeasurementSaved={handleDataUpdated}
            />
          )}

          {activeTab === 'trends' && (
            <DashboardTrends
              onOpenQuickLog={handleOpenQuickLog}
              onOpenWaterChange={() => setActiveTab('water')}
            />
          )}

          {activeTab === 'water' && activeTank && (
            <WaterChangesView
              tank={activeTank}
              analytics={analytics}
              onWaterChangeLogged={handleDataUpdated}
            />
          )}
        </ErrorBoundary>
      </main>

      {/* Mobile Bottom Navigation Bar */}
      <BottomNav
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onOpenQuickLog={() => handleOpenQuickLog()}
      />

      {/* Quick Log Modal */}
      <QuickLogModal
        isOpen={isQuickLogOpen}
        onClose={() => setIsQuickLogOpen(false)}
        tank={activeTank}
        parameters={parameters}
        preselectedCode={preselectedCode}
        onSuccess={handleDataUpdated}
      />

      {/* Tank Creation Modal */}
      <TankManagementModal
        isOpen={isNewTankOpen}
        onClose={() => setIsNewTankOpen(false)}
        onTankCreated={handleTankCreated}
      />

      {/* Notification Reminders Settings Modal */}
      <NotificationModal
        isOpen={isNotificationModalOpen}
        onClose={() => setIsNotificationModalOpen(false)}
      />
    </div>
  );
}
