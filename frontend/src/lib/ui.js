/**
 * Interacciones de UI sin dependencias: toasts, diálogo de confirmación y
 * estados de carga para botones.
 */

let toastRoot;
let confirmRoot;

function ensureToastRoot() {
  if (toastRoot && document.body.contains(toastRoot)) return toastRoot;
  toastRoot = document.getElementById("toast-root");
  if (!toastRoot) {
    toastRoot = document.createElement("div");
    toastRoot.id = "toast-root";
    toastRoot.className = "toast-root";
    toastRoot.setAttribute("aria-live", "polite");
    toastRoot.setAttribute("aria-atomic", "true");
    document.body.appendChild(toastRoot);
  }
  return toastRoot;
}

/**
 * Muestra una notificación efímera.
 *
 * @param {string} message
 * @param {{ tone?: "success" | "error" | "info", duration?: number }} [options]
 */
export function toast(message, { tone = "info", duration = 5200 } = {}) {
  const root = ensureToastRoot();
  const element = document.createElement("div");
  element.className = `toast toast--${tone}`;
  element.setAttribute("role", tone === "error" ? "alert" : "status");

  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("class", "toast__icon");
  icon.innerHTML =
    tone === "error"
      ? '<path d="M12 8v5m0 3.5v.5M10.3 4.3 2.6 17.6A2 2 0 0 0 4.3 20.6h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
      : tone === "success"
        ? '<path d="m5 13 4.2 4.2L19 6.5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>'
        : '<path d="M12 8v.5M12 11.5V16m9-4a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>';

  const text = document.createElement("p");
  text.className = "toast__text";
  text.textContent = message;

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast__close";
  close.setAttribute("aria-label", "Cerrar notificación");
  close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
  close.addEventListener("click", () => dismiss());

  element.append(icon, text, close);
  root.appendChild(element);

  let timer = setTimeout(dismiss, duration);

  function dismiss() {
    clearTimeout(timer);
    element.classList.add("toast--out");
    element.addEventListener("transitionend", () => element.remove(), { once: true });
    setTimeout(() => element.remove(), 400);
  }

  element.addEventListener("mouseenter", () => clearTimeout(timer));
  element.addEventListener("focusin", () => clearTimeout(timer));

  return dismiss;
}

/**
 * Diálogo modal de confirmación basado en `<dialog>`.
 *
 * @param {{ title: string, body?: string, confirmLabel?: string, cancelLabel?: string, danger?: boolean }} options
 * @returns {Promise<boolean>}
 */
export function confirmAction({
  title,
  body = "",
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  danger = false,
}) {
  ensureConfirmRoot();

  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "modal";
    dialog.setAttribute("aria-labelledby", "modal-title");

    const form = document.createElement("form");
    form.method = "dialog";
    form.className = "modal__panel";

    const heading = document.createElement("h2");
    heading.className = "modal__title";
    heading.id = "modal-title";
    heading.textContent = title;

    const paragraph = document.createElement("p");
    paragraph.className = "modal__body";
    paragraph.textContent = body;

    const actions = document.createElement("div");
    actions.className = "modal__actions";

    const cancel = document.createElement("button");
    cancel.type = "submit";
    cancel.value = "cancel";
    cancel.className = "btn btn--ghost";
    cancel.textContent = cancelLabel;

    const accept = document.createElement("button");
    accept.type = "submit";
    accept.value = "confirm";
    accept.className = `btn ${danger ? "btn--danger" : "btn--primary"}`;
    accept.textContent = confirmLabel;

    actions.append(cancel, accept);
    form.append(heading, paragraph, actions);
    dialog.append(form);
    confirmRoot.appendChild(dialog);

    let result = false;
    accept.addEventListener("click", () => {
      result = true;
    });

    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(result);
    });

    dialog.showModal();
    cancel.focus();
  });
}

function ensureConfirmRoot() {
  if (confirmRoot && document.body.contains(confirmRoot)) return confirmRoot;
  confirmRoot = document.getElementById("confirm-root");
  if (!confirmRoot) {
    confirmRoot = document.createElement("div");
    confirmRoot.id = "confirm-root";
    document.body.appendChild(confirmRoot);
  }
  return confirmRoot;
}

/** Bloquea un botón y muestra un indicador mientras corre una petición. */
export function setBusy(button, busy, busyLabel = "Guardando…") {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.disabled = true;
    button.classList.add("is-busy");
    button.textContent = busyLabel;
  } else {
    button.disabled = false;
    button.classList.remove("is-busy");
    if (button.dataset.label) {
      button.textContent = button.dataset.label;
      delete button.dataset.label;
    }
  }
}

/** Muestra un mensaje de error dentro de un contenedor con `role="alert"`. */
export function showFormError(container, message) {
  if (!container) return;
  container.textContent = message;
  container.hidden = !message;
}

/** Formatea el detalle de un error de validación de la API. */
export function describeApiError(error) {
  if (!error) return "Ocurrió un error inesperado.";
  if (error.code === "validation_error" && error.details?.errors?.length) {
    const first = error.details.errors[0];
    return `${error.message} (${first.field || "campo"}: ${first.message})`;
  }
  if (error.code === "equipment_source_invalid") {
    return "Elegí un equipo existente o cargá uno nuevo, pero no ambos.";
  }
  return error.message || "Ocurrió un error inesperado.";
}
