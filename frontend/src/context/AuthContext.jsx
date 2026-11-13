import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getAuthToken,
  setAuthToken,
  loginUser as apiLogin,
  registerUser as apiRegister,
  fetchUserProfile,
  updateUserProfile as apiUpdateProfile
} from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getAuthToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login'); // 'login' | 'register'

  // Cargar usuario activo si existe token guardado
  useEffect(() => {
    let isMounted = true;

    const initAuth = async () => {
      const storedToken = getAuthToken();
      if (!storedToken) {
        if (isMounted) setLoading(false);
        return;
      }

      try {
        const userData = await fetchUserProfile();
        if (isMounted) {
          setUser(userData);
        }
      } catch (err) {
        console.warn('Sesión previa inválida o expirada:', err);
        setAuthToken(null);
        if (isMounted) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    initAuth();

    // Escuchar eventos de sesión no autorizada (401)
    const handleUnauthorized = () => {
      setAuthToken(null);
      setToken(null);
      setUser(null);
      setIsAuthModalOpen(true);
      setAuthModalTab('login');
    };

    window.addEventListener('aquapulse:unauthorized', handleUnauthorized);
    return () => {
      isMounted = false;
      window.removeEventListener('aquapulse:unauthorized', handleUnauthorized);
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await apiLogin(email, password);
    setToken(data.access_token);
    setUser(data.user);
    setIsAuthModalOpen(false);
    return data.user;
  }, []);

  const register = useCallback(async (email, password, fullName) => {
    const data = await apiRegister(email, password, fullName);
    setToken(data.access_token);
    setUser(data.user);
    setIsAuthModalOpen(false);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (profileData) => {
    const updated = await apiUpdateProfile(profileData);
    setUser(updated);
    return updated;
  }, []);

  const loginDemo = useCallback(async () => {
    return await login('demo@aquapulse.io', 'demo123');
  }, [login]);

  const openAuthModal = useCallback((tab = 'login') => {
    setAuthModalTab(tab);
    setIsAuthModalOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => {
    setIsAuthModalOpen(false);
  }, []);

  const value = {
    token,
    user,
    isAuthenticated: Boolean(user && token),
    loading,
    unitPreference: user?.unit_preference || 'liters',
    subscriptionTier: user?.subscription_tier || 'free',
    login,
    register,
    logout,
    updateProfile,
    loginDemo,
    isAuthModalOpen,
    authModalTab,
    openAuthModal,
    closeAuthModal,
    setAuthModalTab
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe ser utilizado dentro de un AuthProvider');
  }
  return context;
}
