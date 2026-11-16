import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import esES from "./es-ES.json";

i18n.use(initReactI18next).init({
  resources: {
    "es-ES": {
      translation: esES,
    },
  },
  lng: "es-ES",
  fallbackLng: "es-ES",
  // A key missing at run time shows readable Spanish, never the raw key; development still sees which key it was.
  parseMissingKeyHandler: (key: string, defaultValue?: string) => {
    if (defaultValue) return defaultValue;
    if (import.meta.env.DEV) console.warn(`[i18n] missing key: ${key}`);
    return (esES as Record<string, string>)["common.text_unavailable"] ?? "";
  },
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
