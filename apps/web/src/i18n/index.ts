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
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
