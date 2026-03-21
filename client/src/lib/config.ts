/**
 * Runtime config. Reads from env vars at build time or falls back to defaults.
 */
export const API_URL =
  (typeof process !== "undefined" && process.env?.API_URL) ||
  "http://localhost:8000";

export const WS_URL =
  (typeof process !== "undefined" && process.env?.WS_URL) ||
  "ws://localhost:8000";
