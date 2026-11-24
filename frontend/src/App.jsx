import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import DashboardTrends from './components/DashboardTrends';
import WaterChangesView from './components/WaterChangesView';
import SettingsView from './components/SettingsView';
import AdminDashboard from './components/AdminDashboard';
import QuickLogModal from './components/QuickLogModal';
import TankManagementModal from './components/TankManagementModal';
import NotificationModal from './components/NotificationModal';
import BottomNav from './components/BottomNav';
import ErrorBoundary from './components/ErrorBoundary';
import AuthModal from './components/AuthModal';
import { AuthProvider, useAuth } from './context/AuthContext';
import {
  fetchTanks,
  fetchTankParameters,
  fetchTankAnalytics,
  fetchPredictions
} from './api';
import {
  LayoutDashboard,
  LineChart,
  Droplets,
  Wrench,
  Settings,
  WifiOff,
  Sparkles,
  Lock,
  ShieldCheck
} from 'lucide-react';

function AppContent() {
  const { t } = useTranslation();
  const {
    user,
    isAuthenticated,
    loading: authLoading,
    isAuthModalOpen,
    closeAuthModal,
    openAuthModal,
    loginDemo
  } = useAuth();

  const [tanks, setTanks] = useState([]);
  const [activeTank, setActiveTank] = useState(null);
  const [parameters, setParameters] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window !== 'undefined') {
      if (window.location.pathname === '/admin') return 'admin';
      const paramTab = new URLSearchParams(window.location.search).get('tab');
      if (paramTab) return paramTab;
    }
    return 'trends';
  });

  const handleSelectTab = (tab) => {
    triggerHaptic();
    setActiveTab(tab);
    if (typeof window !== 'undefined') {
      if (tab === 'admin') {
        window.history.pushState(null, '', '/admin');
      } else if (window.location.pathname === '/admin') {
        window.history.pushState(null, '', `/?tab=${tab}`);
      }
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      if (window.location.pathname === '/admin') {
        setActiveTab('admin');
      } else {
        const pTab = new URLSearchParams(window.location.search).get('tab');
        setActiveTab(pTab || 'trends');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Abrir modal de autenticación o restablecimiento si la URL contiene parámetro
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const resetToken = params.get('reset_token') || params.get('token');
      const authParam = params.get('auth');
      if (resetToken) {
        openAuthModal('reset');
      } else if (authParam) {
        openAuthModal(authParam);
      }
    }
  }, [openAuthModal]);

  const [isQuickLogOpen, setIsQuickLogOpen] = useState(false);
  const [quickLogTank, setQuickLogTank] = useState(null);
  const [preselectedCode, setPreselectedCode] = useState(null);
  const [isNewTankOpen, setIsNewTankOpen] = useState(false);
  const [editingTank, setEditingTank] = useState(null);
  const [isNotificationModalOpen, setIsNotificationModalOpen] = useState(false);
  const [selectedCodeForChart, setSelectedCodeForChart] = useState(null);

  const [isOnline, setIsOnline] = useState(navigator.onLine);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  // Sincronización automática de cola offline de mediciones (PWA Fase 5)
  useEffect(() => {
    import('./utils/offlineQueue').then(({ flushOfflineQueue }) => {
      flushOfflineQueue();
    }).catch(() => {});
  }, [isAuthenticated]);

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

  // Recargar datos cuando cambia el usuario autenticado
  useEffect(() => {
    if (authLoading) return;
    if (isAuthenticated) {
      loadTanks();
    } else {
      setTanks([]);
      setActiveTank(null);
      setParameters([]);
      setAnalytics(null);
      setLoading(false);
    }
  }, [isAuthenticated, user?.id, authLoading]);

  useEffect(() => {
    if (activeTank && isAuthenticated) {
      loadTankDetails(activeTank.id);
    }
  }, [activeTank?.id, isAuthenticated]);

  const loadTanks = async () => {
    setLoading(true);
    try {
      const data = await fetchTanks();
      setTanks(data);
      if (data.length > 0) {
        setActiveTank(data[0]);
      } else {
        setActiveTank(null);
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

  const handleOpenQuickLog = (code = null, customTank = null) => {
    triggerHaptic();
    if (!isAuthenticated) {
      openAuthModal('login');
      return;
    }
    setPreselectedCode(code);
    setQuickLogTank(customTank || null);
    setIsQuickLogOpen(true);
  };

  const handleOpenEditTankModal = (tankToEdit = null) => {
    triggerHaptic();
    if (!isAuthenticated) {
      openAuthModal('login');
      return;
    }
    setEditingTank(tankToEdit || activeTank);
    setIsNewTankOpen(true);
  };

  const handleTankCreated = (newTank) => {
    setTanks((prev) => [...prev, newTank]);
    setActiveTank(newTank);
  };

  const handleTankUpdated = (updatedTank) => {
    // 1. Actualizar inmediatamente la lista de tanques
    setTanks((prev) => prev.map((t) => (t.id === updatedTank.id ? { ...t, ...updatedTank } : t)));

    // 2. Si el acuario editado es el activo, actualizar activeTank en tiempo real
    if (activeTank && activeTank.id === updatedTank.id) {
      setActiveTank((prev) => ({ ...prev, ...updatedTank }));
      loadTankDetails(updatedTank.id);
    }
  };

  const handleDataUpdated = () => {
    if (activeTank) {
      loadTankDetails(activeTank.id);
    }
  };

  return (
    <div className="h-[100dvh] w-full flex flex-col bg-slate-900 overflow-hidden font-sans selection:bg-cyan-500 selection:text-marine-950">
      {/* Offline Alert Banner */}
      {!isOnline && (
        <div className="bg-amber-500/20 text-amber-300 border-b border-amber-500/40 px-4 py-2 text-xs font-bold flex items-center justify-center gap-2">
          <WifiOff className="w-4 h-4" />
          <span>{t('app.offlineBanner')}</span>
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
        onOpenNewTankModal={() => {
          if (!isAuthenticated) {
            openAuthModal('login');
          } else {
            setEditingTank(null);
            setIsNewTankOpen(true);
          }
        }}
        onOpenEditTankModal={handleOpenEditTankModal}
        onOpenNotificationModal={() => setIsNotificationModalOpen(true)}
        onOpenSettings={() => handleSelectTab('settings')}
        onOpenAdmin={() => handleSelectTab('admin')}
        onRefresh={handleDataUpdated}
        loading={loading}
      />

      {/* Desktop Sub-Navigation Tabs */}
      <div className="hidden sm:block border-b border-marine-800/80 bg-marine-900/60 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-8">
          <button
            onClick={() => handleSelectTab('dashboard')}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'dashboard'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>{t('nav.dashboardTab')}</span>
          </button>

          <button
            onClick={() => handleSelectTab('trends')}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'trends'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LineChart className="w-4 h-4" />
            <span>{t('nav.trendsTab')}</span>
          </button>

          <button
            onClick={() => handleSelectTab('water')}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'water'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Wrench className="w-4 h-4" />
            <span>{t('nav.waterTab')}</span>
          </button>

          <button
            onClick={() => handleSelectTab('settings')}
            className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
              activeTab === 'settings'
                ? 'border-cyan-400 text-cyan-300 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Settings className="w-4 h-4" />
            <span>{t('nav.settingsTab')}</span>
          </button>

          {user?.is_admin && (
            <button
              onClick={() => handleSelectTab('admin')}
              className={`min-h-[48px] flex items-center gap-2 text-xs sm:text-sm font-extrabold border-b-2 transition-all ${
                activeTab === 'admin'
                  ? 'border-amber-400 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.6)]'
                  : 'border-transparent text-amber-400/80 hover:text-amber-300'
              }`}
            >
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <span>{t('admin.navLink')}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area con ErrorBoundary */}
      <main className="flex-1 overflow-y-auto p-4 relative">
        <ErrorBoundary>
          {!isAuthenticated && activeTab !== 'settings' && activeTab !== 'admin' ? (
            <div className="max-w-4xl mx-auto px-4 py-12 text-center">
              <div className="bg-marine-900/90 border border-marine-800 rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden">
                {/* LOGO ACTUALIZADO CON EL NOMBRE EXACTO */}
                <div className="flex justify-center mb-6 relative">
                  <img 
                    src="/logo-reef-icon.png" 
                    alt="AquaPulse Logo" 
                    onError={(e) => { e.currentTarget.src = '/logo-reef.png'; }}
                    className="w-20 h-20 rounded-2xl shadow-[0_0_15px_rgba(34,211,238,0.3)] object-cover" 
                  />
                </div>

                <h1 className="text-2xl font-bold text-white text-center mb-1">
                  AquaPulse Commercial Cloud
                </h1>
                <p className="text-sm text-slate-400 max-w-lg mx-auto mb-6">
                  {t('app.welcomeDesc')}
                </p>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <button
                    onClick={() => openAuthModal('login')}
                    className="px-6 py-3 rounded-2xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 font-black text-sm shadow-neon-cyan hover:brightness-110 active:scale-95 transition"
                  >
                    {t('app.loginBtn')}
                  </button>
                  <button
                    onClick={() => openAuthModal('register')}
                    className="px-6 py-3 rounded-2xl bg-marine-950 border border-marine-700 text-slate-200 font-bold text-sm hover:border-cyan-400 active:scale-95 transition"
                  >
                    {t('app.registerBtn')}
                  </button>
                  <button
                    onClick={loginDemo}
                    className="px-6 py-3 rounded-2xl bg-cyan-500/10 border border-cyan-500/40 text-cyan-300 font-bold text-sm hover:bg-cyan-500/20 active:scale-95 transition flex items-center justify-center gap-2"
                  >
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    <span>{t('app.demoBtn')}</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {activeTab === 'dashboard' && (
                <Dashboard
                  analytics={analytics}
                  activeTank={activeTank}
                  loading={loading}
                  onOpenQuickLog={handleOpenQuickLog}
                  onOpenWaterChange={() => handleSelectTab('water')}
                  onOpenEditTankModal={handleOpenEditTankModal}
                  onSelectTab={handleSelectTab}
                  onSelectParameterForChart={(code) => setSelectedCodeForChart(code)}
                  onMeasurementSaved={handleDataUpdated}
                />
              )}

              {activeTab === 'trends' && (
                <DashboardTrends
                  activeTank={activeTank}
                  acuarioActual={activeTank}
                  onOpenQuickLog={handleOpenQuickLog}
                  onOpenWaterChange={() => handleSelectTab('water')}
                />
              )}

              {activeTab === 'water' && activeTank && (
                <WaterChangesView
                  tank={activeTank}
                  analytics={analytics}
                  onWaterChangeLogged={handleDataUpdated}
                />
              )}

              {activeTab === 'settings' && (
                <SettingsView
                  onOpenAuthModal={openAuthModal}
                  onOpenAdmin={() => handleSelectTab('admin')}
                />
              )}

              {activeTab === 'admin' && (
                <AdminDashboard
                  onBackToDashboard={() => handleSelectTab('dashboard')}
                />
              )}
            </>
          )}
        </ErrorBoundary>

        {/* EL ESPACIADOR DEFINITIVO: Esto obligará al scroll a bajar muchísimo más */}
        <div className="h-64 w-full flex-shrink-0 text-transparent opacity-0">.</div>
      </main>

      {/* Mobile Bottom Navigation Bar */}
      <BottomNav
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        onOpenQuickLog={() => handleOpenQuickLog()}
      />

      {/* Quick Log Modal */}
      <QuickLogModal
        isOpen={isQuickLogOpen}
        onClose={() => {
          setIsQuickLogOpen(false);
          setQuickLogTank(null);
        }}
        tank={quickLogTank || activeTank}
        parameters={parameters}
        preselectedCode={preselectedCode}
        onSuccess={handleDataUpdated}
      />

      {/* Tank Creation / Edition Modal */}
      <TankManagementModal
        isOpen={isNewTankOpen}
        onClose={() => {
          setIsNewTankOpen(false);
          setEditingTank(null);
        }}
        existingTank={editingTank}
        onTankCreated={handleTankCreated}
        onTankUpdated={handleTankUpdated}
      />

      {/* Notification Reminders Settings Modal */}
      <NotificationModal
        isOpen={isNotificationModalOpen}
        onClose={() => setIsNotificationModalOpen(false)}
      />

      {/* Authentication Modal (Login / Register) */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={closeAuthModal}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
