/** Utilidades de formato en español neutro (fechas, días y textos cortos). */

const DATE = new Intl.DateTimeFormat("es", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const DATE_LONG = new Intl.DateTimeFormat("es", {
  weekday: "short",
  day: "2-digit",
  month: "long",
  year: "numeric",
});

const TIME = new Intl.DateTimeFormat("es", {
  hour: "2-digit",
  minute: "2-digit",
});

/** `2026-10-22T18:05:00` -> `22 oct 2026`. */
export function formatDate(value) {
  const date = toDate(value);
  return date ? DATE.format(date) : "—";
}

/** `2026-10-22T18:05:00` -> `jue, 22 de octubre de 2026`. */
export function formatDateLong(value) {
  const date = toDate(value);
  return date ? DATE_LONG.format(date) : "—";
}

/** `2026-10-22T18:05:00` -> `18:05`. */
export function formatTime(value) {
  const date = toDate(value);
  return date ? TIME.format(date) : "—";
}

/** Fecha y hora legibles: `22 oct 2026 · 18:05`. */
export function formatDateTime(value) {
  const date = toDate(value);
  return date ? `${DATE.format(date)} · ${TIME.format(date)}` : "—";
}

/** ISO corto para atributos `datetime`. */
export function isoDate(value) {
  const date = toDate(value);
  return date ? date.toISOString() : "";
}

/** "hace 3 días" / "hoy" / "hace 1 día". */
export function relativeDays(days) {
  const value = Number(days);
  if (!Number.isFinite(value)) return "—";
  if (value <= 0) return "hoy";
  if (value === 1) return "hace 1 día";
  return `hace ${value} días`;
}

/** "1 día" / "3 días" sin prefijo. */
export function pluralDays(days) {
  const value = Number(days) || 0;
  return value === 1 ? "1 día" : `${value} días`;
}

/** Convierte a fecha de forma defensiva (la API envía ISO sin zona). */
export function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Iniciales para avatares: "Ana María Ruiz" -> "AR". */
export function initials(name = "") {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

/** Recorta un texto largo respetando palabras. */
export function truncate(text, max = 120) {
  const value = String(text ?? "");
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1).trimEnd()}…`;
}

/** Valor seguro para pintar en HTML (evita `undefined`). */
export function display(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}
