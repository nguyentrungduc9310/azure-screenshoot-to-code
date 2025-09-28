// Default to false if set to anything other than "true" or unset
export const IS_RUNNING_ON_CLOUD =
  import.meta.env.VITE_IS_DEPLOYED === "true" || false;

// Auto-detect production environment (same domain as frontend)
const isProduction = window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1";

export const WS_BACKEND_URL = isProduction
  ? `wss://${window.location.host}/api`
  : import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:7001";

export const HTTP_BACKEND_URL = isProduction
  ? `${window.location.protocol}//${window.location.host}/api`
  : import.meta.env.VITE_HTTP_BACKEND_URL || "http://127.0.0.1:7001";

export const PICO_BACKEND_FORM_SECRET =
  import.meta.env.VITE_PICO_BACKEND_FORM_SECRET || null;
