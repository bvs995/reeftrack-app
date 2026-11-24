import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getAuthToken,
  setAuthToken,
  loginUser as apiLogin,
  registerUser as apiRegister,
  refreshSession,
  logoutUser as apiLogout,
  fetchUserProfile,
  updateUserProfile as apiUpdateProfile,
  verifyEmailToken as apiVerifyEmail,
  resendVerificationEmail as apiResendVerification
} from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getAuthToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login'); // 'login' | 'register'

  // Cargar usuario activo intentando recuperar sesión con cookie HttpOnly (P1.8)
  useEffect(() => {
    let isMounted = true;

    const initAuth = async () => {
      try {
        const session = await refreshSession();
        if (session && session.user && isMounted) {
          setToken(session.access_token);
          setUser(session.user);
        }
      } catch (err) {
        console.warn('Sin sesión previa activa:', err);
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

  const logout = useCallback(async () => {
    await apiLogout();
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (profileData) => {
    const updated = await apiUpdateProfile(profileData);
    setUser(updated);
    return updated;
  }, []);

  const verifyEmail = useCallback(async (verifyToken) => {
    const data = await apiVerifyEmail(verifyToken);
    if (data.access_token) {
      setAuthToken(data.access_token);
      setToken(data.access_token);
    }
    if (data.user) {
      setUser(data.user);
    } else {
      setUser((prev) => (prev ? { ...prev, email_verified: true, is_active: true } : prev));
    }
    return data;
  }, []);

  const resendVerification = useCallback(async (targetEmail) => {
    return await apiResendVerification(targetEmail);
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
    isAdmin: Boolean(user?.is_admin),
    isActive: Boolean(user?.is_active ?? true),
    loading,
    unitPreference: user?.unit_preference || 'liters',
    subscriptionTier: user?.subscription_tier || 'free',
    login,
    register,
    logout,
    updateProfile,
    verifyEmail,
    resendVerification,
    setUser,
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
