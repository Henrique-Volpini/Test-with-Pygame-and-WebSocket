import {bindPrimaryAction, byId} from "../shared/runtime.js";

const OPENABLE_VIEWS = new Set(["main", "lobby", "game"]);
const RESOLUTION_PATTERN = /^(\d+)x(\d+)$/;
const DEFAULT_SETTINGS = Object.freeze({
    width: 1280,
    height: 960,
    fullscreen: false,
});
const GAMEPLAY_KEYS = new Set(["KeyW", "KeyA", "KeyS", "KeyD", "KeyV", "KeyB"]);
const FOCUSABLE_SELECTOR = [
    "button:not([disabled])",
    "select:not([disabled])",
    "input:not([disabled])",
    "[href]",
    "[tabindex]:not([tabindex='-1'])",
].join(",");

function integerOr(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0
        ? Math.round(number)
        : fallback;
}

function resolutionKey(width, height) {
    return `${integerOr(width, DEFAULT_SETTINGS.width)}x${integerOr(
        height,
        DEFAULT_SETTINGS.height,
    )}`;
}

function parseResolution(value) {
    const match = RESOLUTION_PATTERN.exec(String(value || ""));
    if (!match) {
        return null;
    }

    const width = Number(match[1]);
    const height = Number(match[2]);
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
        return null;
    }
    return {width, height};
}

function normalizeResolutionEntry(entry) {
    if (typeof entry === "string") {
        const resolution = parseResolution(entry.toLowerCase().replace(/\s/g, ""));
        return resolution ? {...resolution, available: true} : null;
    }

    if (Array.isArray(entry) && entry.length >= 2) {
        const width = integerOr(entry[0], 0);
        const height = integerOr(entry[1], 0);
        return width > 0 && height > 0 ? {width, height, available: true} : null;
    }

    if (!entry || typeof entry !== "object") {
        return null;
    }

    const width = integerOr(entry.width, 0);
    const height = integerOr(entry.height, 0);
    if (width <= 0 || height <= 0) {
        return null;
    }

    const explicitlyUnavailable = (
        entry.available === false ||
        entry.supported === false ||
        entry.enabled === false
    );
    return {width, height, available: !explicitlyUnavailable};
}

function normalizeView(view) {
    const value = String(view || "").toLowerCase();
    if (value === "game" || value === "partida") {
        return "game";
    }
    if (value === "lobby" || value === "sala") {
        return "lobby";
    }
    if (value === "host" || value === "menu_host") {
        return "host";
    }
    if (value === "connect" || value === "menu_connect") {
        return "connect";
    }
    return "main";
}

function displayBounds() {
    const display = window.screen || {};
    const availableWidth = window.screen ? window.screen.availWidth : window.innerWidth;
    const availableHeight = window.screen ? window.screen.availHeight : window.innerHeight;
    return {
        x: Number.isFinite(Number(display.availLeft))
            ? Math.round(Number(display.availLeft))
            : 0,
        y: Number.isFinite(Number(display.availTop))
            ? Math.round(Number(display.availTop))
            : 0,
        width: integerOr(availableWidth, integerOr(window.innerWidth, 1280)),
        height: integerOr(availableHeight, integerOr(window.innerHeight, 960)),
    };
}

export function createSettings({callBridge, onVisibilityChange, getCurrentView}) {
    const overlay = byId("settings-overlay");
    const dialog = byId("settings-dialog");
    const closeButton = byId("settings-close");
    const exitButton = byId("settings-exit");
    const applyButton = byId("settings-apply");
    const resolutionSelect = byId("settings-resolution");
    const windowedInput = byId("settings-windowed");
    const fullscreenInput = byId("settings-fullscreen");
    const status = byId("settings-status");
    const backdrop = overlay.querySelector(".settings-backdrop");
    const disposers = [];
    const state = {
        visible: false,
        busy: false,
        disposed: false,
        dirty: false,
        context: "main",
        previousFocus: null,
        inertRecords: [],
        operationRevision: 0,
        applied: {...DEFAULT_SETTINGS},
    };

    function listen(target, type, listener, options) {
        target.addEventListener(type, listener, options);
        disposers.push(() => target.removeEventListener(type, listener, options));
    }

    function notifyVisibility(visible) {
        if (typeof onVisibilityChange !== "function") {
            return;
        }
        try {
            onVisibilityChange(Boolean(visible));
        } catch (_error) {
            // O overlay continua funcional mesmo se um consumidor for desmontado.
        }
    }

    function setStatus(message = "", kind = "") {
        status.textContent = message;
        status.classList.toggle("is-success", kind === "success");
        status.classList.toggle("is-error", kind === "error");
    }

    function setBusy(busy) {
        state.busy = Boolean(busy);
        const disabledControls = [
            resolutionSelect,
            windowedInput,
            fullscreenInput,
            applyButton,
        ];
        if (
            state.busy
            && disabledControls.includes(document.activeElement)
        ) {
            closeButton.focus({preventScroll: true});
        }
        dialog.classList.toggle("is-busy", state.busy);
        dialog.setAttribute("aria-busy", String(state.busy));
        resolutionSelect.disabled = state.busy;
        windowedInput.disabled = state.busy;
        fullscreenInput.disabled = state.busy;
        applyButton.disabled = state.busy || !state.dirty;
    }

    function selectedDraft() {
        const resolution = parseResolution(resolutionSelect.value) || {
            width: state.applied.width,
            height: state.applied.height,
        };
        return {
            ...resolution,
            fullscreen: fullscreenInput.checked,
        };
    }

    function updateDirtyState({announce = true} = {}) {
        const draft = selectedDraft();
        state.dirty = (
            draft.width !== state.applied.width ||
            draft.height !== state.applied.height ||
            draft.fullscreen !== state.applied.fullscreen
        );
        applyButton.classList.toggle("has-pending-settings", state.dirty);
        applyButton.disabled = state.busy || !state.dirty;
        if (announce) {
            setStatus(state.dirty ? "Alterações prontas para aplicar." : "");
        }
    }

    function chooseResolution(width, height) {
        const key = resolutionKey(width, height);
        const exact = [...resolutionSelect.options].find((option) => option.value === key);
        if (exact) {
            exact.disabled = false;
            resolutionSelect.value = exact.value;
            return;
        }

        const enabledOptions = [...resolutionSelect.options].filter((option) => !option.disabled);
        const options = enabledOptions.length > 0
            ? enabledOptions
            : [...resolutionSelect.options];
        let nearest = options[0];
        let nearestDistance = Number.POSITIVE_INFINITY;
        for (const option of options) {
            const parsed = parseResolution(option.value);
            if (!parsed) {
                continue;
            }
            const distance = Math.abs(parsed.width - width) + Math.abs(parsed.height - height);
            if (distance < nearestDistance) {
                nearest = option;
                nearestDistance = distance;
            }
        }
        if (nearest) {
            resolutionSelect.value = nearest.value;
        }
    }

    function updateAvailableResolutions(entries, activeWidth, activeHeight) {
        if (!Array.isArray(entries) || entries.length === 0) {
            return;
        }

        const availableByKey = new Map();
        for (const entry of entries) {
            const normalized = normalizeResolutionEntry(entry);
            if (!normalized) {
                continue;
            }
            availableByKey.set(
                resolutionKey(normalized.width, normalized.height),
                normalized.available,
            );
        }
        if (availableByKey.size === 0) {
            return;
        }

        const activeKey = resolutionKey(activeWidth, activeHeight);
        const bounds = displayBounds();
        for (const option of resolutionSelect.options) {
            const parsed = parseResolution(option.value);
            const fitsDisplay = Boolean(
                parsed &&
                parsed.width <= bounds.width &&
                parsed.height <= bounds.height
            );
            option.disabled = (
                option.value !== activeKey &&
                (availableByKey.get(option.value) !== true || !fitsDisplay)
            );
        }
    }

    function windowSettingsFrom(value) {
        if (!value || typeof value !== "object") {
            return null;
        }

        for (const key of ["window_settings", "display_settings", "window"]) {
            const nested = value[key];
            if (nested && typeof nested === "object") {
                return nested;
            }
        }

        if (
            Object.prototype.hasOwnProperty.call(value, "fullscreen") ||
            Array.isArray(value.resolutions)
        ) {
            return value;
        }
        return null;
    }

    function applySettingsSnapshot(value, {announce = false} = {}) {
        const settings = windowSettingsFrom(value);
        if (!settings) {
            return false;
        }
        if (settings.ok === false) {
            if (announce) {
                setStatus(settings.error || "Não foi possível alterar a exibição.", "error");
            }
            return false;
        }

        const width = integerOr(settings.width, state.applied.width);
        const height = integerOr(settings.height, state.applied.height);
        const fullscreen = typeof settings.fullscreen === "boolean"
            ? settings.fullscreen
            : state.applied.fullscreen;

        updateAvailableResolutions(settings.resolutions, width, height);
        state.applied = {width, height, fullscreen};
        chooseResolution(width, height);
        windowedInput.checked = !fullscreen;
        fullscreenInput.checked = fullscreen;
        state.dirty = false;
        applyButton.classList.remove("has-pending-settings");
        applyButton.disabled = true;
        if (announce) {
            setStatus("Configurações de exibição aplicadas.", "success");
        }
        return true;
    }

    function focusableElements() {
        return [...dialog.querySelectorAll(FOCUSABLE_SELECTOR)].filter((element) => (
            !element.disabled &&
            element.getAttribute("aria-hidden") !== "true" &&
            element.getClientRects().length > 0
        ));
    }

    function lockBackground() {
        state.inertRecords = [];
        for (const screen of document.querySelectorAll("#viewport > .screen")) {
            state.inertRecords.push({element: screen, inert: Boolean(screen.inert)});
            screen.inert = true;
        }
    }

    function unlockBackground() {
        for (const record of state.inertRecords) {
            if (record.element.isConnected) {
                record.element.inert = record.inert;
            }
        }
        state.inertRecords = [];
    }

    function setContext(view) {
        state.context = normalizeView(view);
        const labels = {
            game: "Fechar configurações e voltar ao jogo",
            lobby: "Fechar configurações e voltar à sala",
            main: "Fechar configurações e voltar ao menu",
        };
        closeButton.setAttribute(
            "aria-label",
            labels[state.context] || "Fechar configurações",
        );
    }

    async function refreshWindowSettings() {
        const revision = ++state.operationRevision;
        setBusy(true);
        setStatus("Consultando a exibição atual...");
        const result = await callBridge("get_window_settings");
        if (state.disposed || revision !== state.operationRevision) {
            return;
        }

        setBusy(false);
        if (!applySettingsSnapshot(result)) {
            setStatus("Não foi possível consultar a janela do jogo.", "error");
            return;
        }
        setStatus("");
    }

    function open(trigger = null) {
        if (state.disposed || state.visible) {
            return;
        }

        const currentView = typeof getCurrentView === "function"
            ? getCurrentView()
            : state.context;
        setContext(currentView);
        state.previousFocus = trigger instanceof HTMLElement
            ? trigger
            : (
                document.activeElement instanceof HTMLElement
                    ? document.activeElement
                    : null
            );
        lockBackground();
        state.visible = true;
        overlay.hidden = false;
        overlay.setAttribute("aria-hidden", "false");
        notifyVisibility(true);
        window.requestAnimationFrame(() => {
            if (state.visible) {
                closeButton.focus({preventScroll: true});
            }
        });
        void refreshWindowSettings();
    }

    function close({restoreFocus = true} = {}) {
        if (!state.visible) {
            return;
        }

        state.visible = false;
        overlay.hidden = true;
        overlay.setAttribute("aria-hidden", "true");
        unlockBackground();
        setBusy(false);
        setStatus("");
        notifyVisibility(false);

        const previousFocus = state.previousFocus;
        state.previousFocus = null;
        if (
            restoreFocus &&
            previousFocus &&
            previousFocus.isConnected &&
            typeof previousFocus.focus === "function"
        ) {
            previousFocus.focus({preventScroll: true});
        }
    }

    async function applyWindowSettings() {
        if (state.busy) {
            return;
        }
        const draft = selectedDraft();
        const revision = ++state.operationRevision;
        setBusy(true);
        setStatus("Aplicando configuração de exibição...");
        const result = await callBridge("apply_window_settings",
            draft.width,
            draft.height,
            draft.fullscreen,
            displayBounds(),
        );
        if (state.disposed || revision !== state.operationRevision) {
            return;
        }

        setBusy(false);
        if (!applySettingsSnapshot(result, {announce: true})) {
            setStatus(result?.error || "Não foi possível aplicar esta resolução.", "error");
        }
    }

    async function toggleFullscreen() {
        if (state.busy || state.disposed) {
            return;
        }
        if (state.visible && state.dirty) {
            setStatus(
                "Aplique ou descarte as alterações antes de usar F11.",
                "error",
            );
            return;
        }
        const revision = ++state.operationRevision;
        setBusy(true);
        if (state.visible) {
            setStatus("Alternando o modo de exibição...");
        }
        const result = await callBridge("toggle_fullscreen", displayBounds());
        if (state.disposed || revision !== state.operationRevision) {
            return;
        }

        setBusy(false);
        if (!applySettingsSnapshot(result, {announce: state.visible})) {
            if (state.visible) {
                setStatus(result?.error || "Não foi possível alternar a tela cheia.", "error");
            }
        }
    }

    function trapFocus(event) {
        const focusable = focusableElements();
        if (focusable.length === 0) {
            event.preventDefault();
            dialog.focus({preventScroll: true});
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement;
        if (event.shiftKey && (active === first || !dialog.contains(active))) {
            event.preventDefault();
            last.focus({preventScroll: true});
        } else if (!event.shiftKey && (active === last || !dialog.contains(active))) {
            event.preventDefault();
            first.focus({preventScroll: true});
        }
    }

    function onOpenKeydownCapture(event) {
        if (!state.visible) {
            return;
        }

        if (event.code === "Escape") {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (!event.repeat) {
                close();
            }
            return;
        }
        if (event.code === "F11") {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (!event.repeat) {
                void toggleFullscreen();
            }
            return;
        }
        if (event.code === "Tab") {
            trapFocus(event);
            return;
        }
        if (GAMEPLAY_KEYS.has(event.code)) {
            event.stopPropagation();
        }
    }

    function onGlobalKeydown(event) {
        if (state.visible) {
            event.stopImmediatePropagation();
            return;
        }
        if (event.defaultPrevented) {
            return;
        }

        if (event.code === "F11") {
            event.preventDefault();
            if (!event.repeat) {
                void toggleFullscreen();
            }
            return;
        }
        if (event.code !== "Escape" || event.repeat) {
            return;
        }

        const currentView = normalizeView(
            typeof getCurrentView === "function" ? getCurrentView() : state.context,
        );
        if (!OPENABLE_VIEWS.has(currentView)) {
            return;
        }
        event.preventDefault();
        open();
    }

    listen(document, "keydown", onOpenKeydownCapture, true);
    listen(document, "keydown", onGlobalKeydown);
    listen(overlay, "keydown", (event) => event.stopPropagation());
    listen(resolutionSelect, "change", () => updateDirtyState());
    listen(windowedInput, "change", () => updateDirtyState());
    listen(fullscreenInput, "change", () => updateDirtyState());
    disposers.push(bindPrimaryAction(closeButton, close));
    disposers.push(bindPrimaryAction(backdrop, close));
    disposers.push(bindPrimaryAction(applyButton, () => {
        void applyWindowSettings();
    }));
    disposers.push(bindPrimaryAction(exitButton, () => {
        void callBridge("close_window");
    }));

    setContext("main");
    applySettingsSnapshot({
        ...DEFAULT_SETTINGS,
        resolutions: [...resolutionSelect.options].map((option) => option.value),
    });

    return {
        open,
        close,
        setContext,
        toggleFullscreen,
        applySnapshot(snapshot) {
            if (!state.dirty) {
                applySettingsSnapshot(snapshot);
            }
        },
        get isOpen() {
            return state.visible;
        },
        dispose() {
            if (state.disposed) {
                return;
            }
            state.disposed = true;
            state.operationRevision += 1;
            close({restoreFocus: false});
            while (disposers.length > 0) {
                disposers.pop()();
            }
        },
    };
}
