/**
 * Contrato de la API de ReparaTrack y cliente HTTP del navegador.
 *
 * Las rutas son relativas (`/api/v1/...`) a propósito: en desarrollo el proxy de
 * Astro las reenvía a FastAPI y en producción se sirven desde el mismo origen.
 */

export const API_PREFIX = "/api/v1";

/**
 * Error con la forma del envelope de la API: `{ error: { code, message, details } }`.
 */
export class ApiError extends Error {
  constructor(message, { status = 0, code = "network_error", details = {} } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * Ejecuta una petición a la API y devuelve el JSON.
 *
 * @param {string} path Ruta posterior a `/api/v1`, por ejemplo `/customers?q=ana`.
 * @param {RequestInit & { timeout?: number }} [options]
 * @returns {Promise<any>}
 */
export async function apiFetch(path, options = {}) {
  const { timeout = 15000, headers, body, ...rest } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  const isForm = body instanceof FormData;

  try {
    const response = await fetch(`${API_PREFIX}${path}`, {
      ...rest,
      body,
      signal: controller.signal,
      headers: {
        accept: "application/json",
        ...(body !== undefined && !isForm ? { "content-type": "application/json" } : {}),
        ...headers,
      },
    });

    const text = await response.text();
    const payload = text ? safeJson(text) : null;

    if (!response.ok) {
      const envelope = payload && payload.error ? payload.error : {};
      throw new ApiError(envelope.message || `La API respondió ${response.status}.`, {
        status: response.status,
        code: envelope.code || "http_error",
        details: envelope.details || {},
      });
    }

    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error?.name === "AbortError") {
      throw new ApiError("La API tardó demasiado en responder.", { code: "timeout" });
    }
    throw new ApiError("No se pudo conectar con la API. ¿Está corriendo el backend?", {
      code: "network_error",
    });
  } finally {
    clearTimeout(timer);
  }
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Atajo para enviar un cuerpo JSON. */
export function postJson(path, payload, options = {}) {
  return apiFetch(path, { method: "POST", body: JSON.stringify(payload), ...options });
}

/** Atajo para actualizaciones parciales. */
export function patchJson(path, payload, options = {}) {
  return apiFetch(path, { method: "PATCH", body: JSON.stringify(payload), ...options });
}

/* ------------------------------------------------------------------------- */
/* Estados del servicio (RN-05): claves en inglés, etiquetas en español.      */
/* ------------------------------------------------------------------------- */

export const STATUSES = [
  { key: "RECEIVED", label: "Recibido", tone: "neutral" },
  { key: "DIAGNOSING", label: "En diagnóstico", tone: "info" },
  { key: "AWAITING_APPROVAL", label: "Esperando aprobación", tone: "warning" },
  { key: "AWAITING_PART", label: "Esperando repuesto", tone: "orange" },
  { key: "IN_REPAIR", label: "En reparación", tone: "violet" },
  { key: "NOT_REPARABLE", label: "No reparable", tone: "stone" },
  { key: "REJECTED", label: "Rechazado", tone: "danger" },
  { key: "READY_FOR_PICKUP", label: "Listo para entrega", tone: "success" },
  { key: "DELIVERED", label: "Entregado", tone: "teal" },
  { key: "ABANDONED", label: "Abandonado", tone: "muted" },
];

export const STATUS_KEYS = STATUSES.map((status) => status.key);

export const STATUS_LABELS = Object.fromEntries(
  STATUSES.map((status) => [status.key, status.label]),
);

/** Estados que cierran el ciclo de vida del servicio. */
export const TERMINAL_STATUSES = ["DELIVERED", "ABANDONED"];

/** Estados que mantienen el equipo en el taller (todo menos los terminales). */
export const ACTIVE_STATUSES = STATUSES.filter(
  (status) => !TERMINAL_STATUSES.includes(status.key),
).map((status) => status.key);

/** Etiqueta legible de cualquier estado, incluso si la API agrega uno nuevo. */
export function statusLabel(status, fallback = "") {
  return STATUS_LABELS[status] || fallback || status || "Sin estado";
}

/** Reglas de abandono (RN-07 / RN-10) y su umbral en días. */
export const ABANDONMENT_RULES = {
  "RN-07": { threshold: 180, label: "180 días listo para entrega" },
  "RN-10": { threshold: 30, label: "30 días esperando aprobación" },
};

/** Catálogos administrables: slug de la API -> nombre visible. */
export const CATALOGS = [
  { slug: "device-types", label: "Tipos de dispositivo", singular: "tipo de dispositivo" },
  { slug: "brands", label: "Marcas", singular: "marca" },
  { slug: "components", label: "Componentes", singular: "componente" },
  { slug: "operation-types", label: "Tipos de operación", singular: "tipo de operación" },
];

/** Motivos de bloqueo de una transición, traducidos para la UI. */
export const BLOCKED_REASONS = {
  details_required:
    "Registrá al menos una operación antes de pasar a listo para entrega.",
  threshold_not_reached:
    "Todavía no se cumplió el umbral de días de la regla de abandono.",
  confirmation_required: "Esta transición requiere confirmación explícita.",
};
