/**
 * Acceso a la API desde el servidor de Astro (frontmatter de cada página).
 *
 * Usa una base absoluta porque `fetch` en Node no resuelve rutas relativas. En
 * desarrollo el valor por defecto apunta directo a FastAPI; se puede cambiar con
 * la variable de entorno `API_BASE_URL` (por ejemplo en un despliegue donde la
 * API vive en otro host).
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

function resolveBaseUrl() {
  const configured =
    (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.API_BASE_URL) ||
    process.env.API_BASE_URL ||
    DEFAULT_BASE_URL;
  return String(configured).replace(/\/+$/, "");
}

export const API_BASE_URL = resolveBaseUrl();

/**
 * Petición tolerante a fallos: nunca lanza, siempre devuelve un resultado
 * discriminado para que la página pueda mostrar un estado degradado amable.
 *
 * @param {string} path Ruta posterior a `/api/v1`.
 * @param {{ timeout?: number } & RequestInit} [options]
 * @returns {Promise<{ ok: true, data: any, status: number } | { ok: false, status: number, error: string, code: string, details: Record<string, any> }>}
 */
export async function serverFetch(path, options = {}) {
  const { timeout = 8000, headers, ...rest } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      ...rest,
      signal: controller.signal,
      headers: { accept: "application/json", ...headers },
    });

    const text = await response.text();
    const payload = text ? safeJson(text) : null;

    if (!response.ok) {
      const envelope = payload && payload.error ? payload.error : {};
      return {
        ok: false,
        status: response.status,
        error: envelope.message || `La API respondió ${response.status}.`,
        code: envelope.code || "http_error",
        details: envelope.details || {},
      };
    }

    return { ok: true, status: response.status, data: payload };
  } catch (error) {
    const aborted = error?.name === "AbortError";
    return {
      ok: false,
      status: 0,
      error: aborted
        ? "La API tardó demasiado en responder."
        : "No se pudo conectar con la API. Verificá que el backend esté corriendo en el puerto 8000.",
      code: aborted ? "timeout" : "network_error",
      details: {},
    };
  } finally {
    clearTimeout(timer);
  }
}

/** Envuelve una respuesta como arreglo, útil para listados. */
export function asList(result) {
  return result.ok && Array.isArray(result.data) ? result.data : [];
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
