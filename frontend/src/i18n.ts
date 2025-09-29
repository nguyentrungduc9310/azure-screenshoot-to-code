import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files directly
import enTranslation from '../public/locales/en/translation.json';
import deTranslation from '../public/locales/de/translation.json';
import frTranslation from '../public/locales/fr/translation.json';
import jaTranslation from '../public/locales/ja/translation.json';
import koTranslation from '../public/locales/ko/translation.json';
import ruTranslation from '../public/locales/ru/translation.json';
import zhTranslation from '../public/locales/zh/translation.json';

const resources = {
  en: { translation: enTranslation },
  de: { translation: deTranslation },
  fr: { translation: frTranslation },
  ja: { translation: jaTranslation },
  ko: { translation: koTranslation },
  ru: { translation: ruTranslation },
  zh: { translation: zhTranslation }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    debug: false, // Disable debug in production
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
