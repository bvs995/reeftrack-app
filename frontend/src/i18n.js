import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import esTranslations from './locales/es.json';
import enTranslations from './locales/en.json';

const resources = {
  es: { translation: esTranslations },
  en: { translation: enTranslations }
};

i18n
  // Detecta el idioma del usuario (localStorage, navegador navigator.language)
  .use(LanguageDetector)
  // Pasa la instancia de i18n a react-i18next
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'es',
    supportedLngs: ['es', 'en'],
    nonExplicitSupportedLngs: true, // Maneja variantes como 'en-US' -> 'en', 'es-MX' -> 'es'
    load: 'languageOnly', // Carga solo 'en' o 'es'
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'aquapulse_language',
      caches: ['localStorage']
    },
    interpolation: {
      escapeValue: false // React ya protege contra XSS
    }
  });

export default i18n;
