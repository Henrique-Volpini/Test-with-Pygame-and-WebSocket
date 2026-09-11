import {bindPrimaryAction, byId} from "../shared/runtime.js";

const MIN_WORLD_SIZE = 1;
const MAX_WORLD_SIZE = 200;
const MAX_SEED = 2147483647;
const DEFAULT_MAP_PARAMS = Object.freeze({
    land: 50,
    mountains: 50,
    forests: 50,
});
const MAP_PARAM_LABELS = Object.freeze({
    land: ["Muito mar", "Mais mar", "Equilibrado", "Mais terra", "Muita terra"],
    mountains: ["Nenhuma", "Raras", "Equilibradas", "Muitas", "Extremas"],
    forests: ["Nenhuma", "Esparsas", "Equilibradas", "Densas", "Selvagens"],
});

const TILE_PALETTES = {
    grass: ["#69844c", "#708a50", "#607943"],
    water: ["#39778b", "#347084", "#417e90"],
    mountain: ["#77786e", "#838379", "#696b64"],
    small_forest: ["#3d6737", "#355d32", "#456f3b"],
    medium_forest: ["#31592f", "#2d512b", "#386234"],
    big_forest: ["#274a28", "#234324", "#2d512b"],
    town_center: ["#a67545", "#8e5f38", "#bb8850"],
    city: ["#98684f", "#875945", "#aa7659"],
    mine: ["#9b7a42", "#866636", "#af8c4c"],
    lumberjack_cabin: ["#9c603b", "#895132", "#ae7047"],
    madeireiro: ["#9c603b", "#895132", "#ae7047"],
};

const STATUS_LABELS = {
    ready: "SALA ABERTA",
    open: "SALA ABERTA",
    waiting: "AGUARDANDO",
    generating: "GERANDO MAPA",
    starting: "INICIANDO",
    connected: "CONECTADO",
    disconnected: "DESCONECTADO",
    error: "ERRO NA SALA",
};

export function createLobby({callBridge, requestView}) {
    const screen = byId("lobby-screen");
    const shell = byId("lobby-shell");
    const code = byId("lobby-code");
    const copyCodeButton = byId("lobby-copy-code");
    const status = byId("lobby-status");
    const role = byId("lobby-role");
    const mapFrame = byId("lobby-map-frame");
    const canvas = byId("lobby-map-canvas");
    const mapEmpty = byId("lobby-map-empty");
    const mapEmptyTitle = mapEmpty.querySelector("strong");
    const mapEmptyDescription = mapEmpty.querySelector("small");
    const mapSize = byId("lobby-map-size");
    const mapRevision = byId("lobby-map-revision");
    const worldTuning = byId("lobby-world-tuning");
    const mapParamInputs = {
        land: byId("lobby-land-input"),
        mountains: byId("lobby-mountains-input"),
        forests: byId("lobby-forests-input"),
    };
    const mapParamOutputs = {
        land: byId("lobby-land-output"),
        mountains: byId("lobby-mountains-output"),
        forests: byId("lobby-forests-output"),
    };
    const compositionOutputs = {
        water: byId("lobby-water-share"),
        plains: byId("lobby-plains-share"),
        forest: byId("lobby-forest-share"),
        mountain: byId("lobby-mountain-share"),
    };
    const config = byId("lobby-config");
    const configAuthority = byId("lobby-config-authority");
    const seedField = byId("lobby-seed-field");
    const seedInput = byId("lobby-seed-input");
    const seedHint = byId("lobby-seed-hint");
    const copySeedButton = byId("lobby-copy-seed");
    const sizeInput = byId("lobby-size-input");
    const sizeHint = byId("lobby-size-hint");
    const applyButton = byId("lobby-apply");
    const regenerateButton = byId("lobby-regenerate");
    const lockedMessage = byId("lobby-config-locked");
    const playerList = byId("lobby-player-list");
    const playerCount = byId("lobby-player-count");
    const leaveButton = byId("lobby-leave");
    const startButton = byId("lobby-start");
    const startButtonHint = startButton.querySelector("small");
    const waiting = byId("lobby-waiting");
    const errorBox = byId("lobby-error");
    const context = canvas.getContext("2d", {alpha: false});
    const disposers = [];
    const feedbackTimers = new Map();

    if (!context) {
        throw new Error("Não foi possível inicializar a prévia do mapa.");
    }
    context.imageSmoothingEnabled = false;

    const state = {
        visible: false,
        isHost: false,
        busy: false,
        generating: false,
        status: "",
        serverError: false,
        code: "",
        seed: "",
        size: 0,
        seedDirty: false,
        sizeDirty: false,
        params: {...DEFAULT_MAP_PARAMS},
        composition: null,
        paramsDirty: false,
        lastDrawnRevision: null,
        lastMap: null,
        redrawFrame: null,
        lastPlayerSignature: "",
        localError: "",
    };

    function listen(target, type, listener, options) {
        target.addEventListener(type, listener, options);
        disposers.push(() => target.removeEventListener(type, listener, options));
    }

    function normalizeSnapshot(snapshot) {
        if (!snapshot || typeof snapshot !== "object") {
            return null;
        }
        if (snapshot.lobby && typeof snapshot.lobby === "object") {
            return snapshot.lobby;
        }
        return snapshot;
    }

    function normalizePercentage(value) {
        const normalized = Number(value);
        if (!Number.isFinite(normalized) || normalized < 0 || normalized > 100) {
            return null;
        }
        return Math.round(normalized);
    }

    function normalizeMapParams(value, fallback = null) {
        if (!value || typeof value !== "object") {
            return fallback ? {...fallback} : null;
        }
        const normalized = {
            land: normalizePercentage(value.land),
            mountains: normalizePercentage(value.mountains),
            forests: normalizePercentage(value.forests),
        };
        if (Object.values(normalized).some((item) => item === null)) {
            return fallback ? {...fallback} : null;
        }
        return normalized;
    }

    function interpolateSetting(value, low, middle, high) {
        if (value <= 50) {
            return low + ((middle - low) * value) / 50;
        }
        return middle + ((high - middle) * (value - 50)) / 50;
    }

    function roundComposition(values) {
        const keys = ["water", "plains", "forest", "mountain"];
        const total = keys.reduce((sum, key) => sum + Math.max(0, Number(values[key]) || 0), 0);
        if (total <= 0) {
            return {water: 0, plains: 100, forest: 0, mountain: 0};
        }

        const scaled = Object.fromEntries(keys.map((key) => [
            key,
            (Math.max(0, Number(values[key]) || 0) * 100) / total,
        ]));
        const rounded = Object.fromEntries(keys.map((key) => [key, Math.floor(scaled[key])]));
        let remaining = 100 - keys.reduce((sum, key) => sum + rounded[key], 0);
        const priority = [...keys].sort((left, right) => (
            (scaled[right] - Math.floor(scaled[right]))
            - (scaled[left] - Math.floor(scaled[left]))
        ));
        for (let index = 0; remaining > 0; index += 1, remaining -= 1) {
            rounded[priority[index % priority.length]] += 1;
        }
        return rounded;
    }

    function estimateComposition(params) {
        const water = interpolateSetting(params.land, 50, 29, 5);
        const land = 100 - water;
        const mountainWithinLand = interpolateSetting(params.mountains, 0, 3, 25);
        const mountain = (land * mountainWithinLand) / 100;
        const landAfterMountains = land - mountain;
        const forestWithinRemaining = interpolateSetting(params.forests, 0, 20, 45);
        const forest = (landAfterMountains * forestWithinRemaining) / 100;
        const plains = landAfterMountains - forest;
        return roundComposition({water, plains, forest, mountain});
    }

    function normalizeMapComposition(value) {
        if (!value || typeof value !== "object") {
            return null;
        }
        const normalized = {
            water: value.water,
            plains: value.plains ?? value.plain ?? value.grass,
            forest: value.forest ?? value.forests,
            mountain: value.mountain ?? value.mountains,
        };
        if (Object.values(normalized).some((item) => (
            !Number.isFinite(Number(item)) || Number(item) < 0 || Number(item) > 100
        ))) {
            return null;
        }
        return roundComposition(normalized);
    }

    function readMapParams() {
        return normalizeMapParams(
            Object.fromEntries(Object.entries(mapParamInputs).map(([key, input]) => [key, input.value])),
            state.params,
        );
    }

    function renderMapSettings(params, composition = null) {
        const normalizedParams = normalizeMapParams(params, DEFAULT_MAP_PARAMS);
        const normalizedComposition = normalizeMapComposition(composition)
            || estimateComposition(normalizedParams);
        state.params = normalizedParams;
        state.composition = normalizedComposition;

        for (const [key, input] of Object.entries(mapParamInputs)) {
            const value = normalizedParams[key];
            const labelIndex = Math.min(4, Math.max(0, Math.round(value / 25)));
            const label = MAP_PARAM_LABELS[key][labelIndex];
            input.value = String(value);
            input.style.setProperty("--range-progress", `${value}%`);
            input.setAttribute("aria-valuetext", label);
            mapParamOutputs[key].value = label;
            mapParamOutputs[key].textContent = label;
        }
        for (const [key, output] of Object.entries(compositionOutputs)) {
            output.textContent = `${normalizedComposition[key]}%`;
        }
    }

    function tileName(cell) {
        if (typeof cell === "string") {
            return cell;
        }
        if (cell && typeof cell === "object" && typeof cell.tile === "string") {
            return cell.tile;
        }
        return "grass";
    }

    function tileColor(name, x, y) {
        const palette = TILE_PALETTES[name] || TILE_PALETTES.grass;
        const variation = Math.abs((x * 17 + y * 31 + x * y * 3) % palette.length);
        return palette[variation];
    }

    function syncCanvasResolution() {
        const cssWidth = mapFrame.clientWidth;
        const cssHeight = mapFrame.clientHeight;
        if (cssWidth < 2 || cssHeight < 2) {
            return false;
        }

        const pixelRatio = Math.min(
            2,
            Math.max(1, Number(window.devicePixelRatio) || 1),
        );
        const targetWidth = Math.max(1, Math.round(cssWidth * pixelRatio));
        const targetHeight = Math.max(1, Math.round(cssHeight * pixelRatio));
        if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
            canvas.width = targetWidth;
            canvas.height = targetHeight;
            context.imageSmoothingEnabled = false;
        }
        return true;
    }

    function drawMap(matrix, width, height, revision) {
        state.lastMap = {matrix, width, height, revision};
        if (!Array.isArray(matrix) || matrix.length === 0 || width <= 0 || height <= 0) {
            return false;
        }
        if (!syncCanvasResolution()) {
            return false;
        }

        const drawWidth = canvas.width;
        const drawHeight = canvas.height;
        const cellSize = Math.min(drawWidth / width, drawHeight / height);
        const worldWidth = cellSize * width;
        const worldHeight = cellSize * height;
        const offsetX = (drawWidth - worldWidth) / 2;
        const offsetY = (drawHeight - worldHeight) / 2;

        context.fillStyle = "#0d110c";
        context.fillRect(0, 0, drawWidth, drawHeight);

        for (let y = 0; y < height; y += 1) {
            const row = matrix[y];
            if (!Array.isArray(row)) {
                continue;
            }
            for (let x = 0; x < width; x += 1) {
                const left = Math.floor(offsetX + x * cellSize);
                const top = Math.floor(offsetY + y * cellSize);
                const right = Math.ceil(offsetX + (x + 1) * cellSize);
                const bottom = Math.ceil(offsetY + (y + 1) * cellSize);
                context.fillStyle = tileColor(tileName(row[x]), x, y);
                context.fillRect(left, top, Math.max(1, right - left), Math.max(1, bottom - top));
            }
        }

        if (cellSize >= 8) {
            context.strokeStyle = "rgba(235, 220, 179, 0.08)";
            context.lineWidth = 1;
            context.beginPath();
            for (let x = 0; x <= width; x += 1) {
                const position = Math.round(offsetX + x * cellSize) + 0.5;
                context.moveTo(position, offsetY);
                context.lineTo(position, offsetY + worldHeight);
            }
            for (let y = 0; y <= height; y += 1) {
                const position = Math.round(offsetY + y * cellSize) + 0.5;
                context.moveTo(offsetX, position);
                context.lineTo(offsetX + worldWidth, position);
            }
            context.stroke();
        }

        context.strokeStyle = "rgba(238, 204, 126, 0.36)";
        context.lineWidth = 2;
        context.strokeRect(
            Math.floor(offsetX) + 1,
            Math.floor(offsetY) + 1,
            Math.max(0, Math.ceil(worldWidth) - 2),
            Math.max(0, Math.ceil(worldHeight) - 2),
        );

        state.lastDrawnRevision = revision;
        mapEmpty.hidden = true;
        mapFrame.setAttribute("aria-busy", "false");
        return true;
    }

    function scheduleMapDraw() {
        if (state.redrawFrame !== null || !state.lastMap) {
            return;
        }
        state.redrawFrame = window.requestAnimationFrame(() => {
            state.redrawFrame = null;
            if (!state.visible || !state.lastMap) {
                return;
            }
            const {matrix, width, height, revision} = state.lastMap;
            drawMap(matrix, width, height, revision);
        });
    }

    function displayError(message) {
        state.localError = String(message || "");
        const paragraph = errorBox.querySelector("p");
        paragraph.textContent = state.localError || "Não foi possível concluir a ação.";
        errorBox.hidden = !state.localError;
    }

    function setBusy(busy) {
        state.busy = Boolean(busy);
        shell.setAttribute("aria-busy", String(state.busy));
        updateAuthorityUi();
        updateStatus(state.status, state.serverError, state.generating);
    }

    function showGenerationOverlay(generating) {
        mapEmptyTitle.textContent = generating
            ? "Gerando outro território"
            : "Preparando o terreno";
        mapEmptyDescription.textContent = generating
            ? "Atualizando a prévia para todos os jogadores."
            : "O mapa aparecerá assim que estiver pronto.";
        mapEmpty.hidden = false;
        mapFrame.setAttribute("aria-busy", "true");
    }

    function updateAuthorityUi() {
        const controlsLocked = !state.isHost || state.busy || state.generating;
        const hasPendingConfiguration = (
            state.seedDirty || state.sizeDirty || state.paramsDirty
        );

        role.textContent = state.isHost ? "DONO DA SALA" : "CONVIDADO";
        role.classList.toggle("is-host", state.isHost);
        config.classList.toggle("is-guest", !state.isHost);
        configAuthority.textContent = state.isHost ? "SEU CONTROLE" : "SÓ O DONO";
        configAuthority.classList.toggle("is-host", state.isHost);
        seedInput.readOnly = controlsLocked;
        sizeInput.disabled = controlsLocked;
        applyButton.disabled = controlsLocked;
        regenerateButton.disabled = controlsLocked;
        for (const input of Object.values(mapParamInputs)) {
            input.disabled = controlsLocked;
        }
        worldTuning.classList.toggle("is-locked", controlsLocked);
        worldTuning.setAttribute("aria-disabled", String(controlsLocked));
        seedField.classList.toggle("is-locked", !state.isHost);
        lockedMessage.hidden = state.isHost;
        startButton.hidden = !state.isHost;
        startButton.disabled = (
            state.busy || state.generating || hasPendingConfiguration
        );
        startButton.classList.toggle(
            "has-pending-config",
            hasPendingConfiguration,
        );
        startButton.title = hasPendingConfiguration
            ? "Aplique ou regenere o mapa antes de iniciar."
            : "";
        if (startButtonHint) {
            startButtonHint.textContent = hasPendingConfiguration
                ? "Aplique as alterações primeiro"
                : "Levar todos para o reino";
        }
        waiting.hidden = state.isHost;
    }

    function updateStatus(rawStatus, hasError, generating = false) {
        const normalized = String(rawStatus || "waiting").toLowerCase();
        let label = STATUS_LABELS[normalized];
        if (generating) {
            label = "GERANDO MAPA";
        } else if (hasError || normalized.includes("desconect")) {
            label = "ERRO NA SALA";
        } else if (!label) {
            label = "SALA ABERTA";
        }
        const isBusy = state.busy || generating || normalized === "generating" || normalized === "starting";
        const isError = hasError || normalized === "error" || normalized.includes("desconect");

        status.lastChild.textContent = ` ${label}`;
        status.classList.toggle("is-online", !isBusy && !isError);
        status.classList.toggle("is-busy", isBusy);
        status.classList.toggle("is-error", isError);
    }

    function playerInitial(name) {
        const text = String(name || "?").trim();
        return (text[0] || "?").toUpperCase();
    }

    function renderPlayers(players, declaredCount) {
        const safePlayers = Array.isArray(players) ? players : [];
        const count = Number.isInteger(Number(declaredCount))
            ? Math.max(0, Number(declaredCount))
            : safePlayers.length;
        const signature = JSON.stringify(safePlayers.map((player) => [
            player && player.id,
            player && player.name,
            Boolean(player && player.is_self),
            Boolean(player && player.is_host),
        ]));

        playerCount.textContent = String(count);
        playerCount.setAttribute(
            "aria-label",
            `${count} ${count === 1 ? "jogador online" : "jogadores online"}`,
        );

        if (signature === state.lastPlayerSignature) {
            return;
        }
        state.lastPlayerSignature = signature;
        playerList.replaceChildren();

        if (safePlayers.length === 0) {
            const empty = document.createElement("li");
            empty.className = "lobby-player-empty";
            empty.textContent = "Aguardando jogadores...";
            playerList.appendChild(empty);
            return;
        }

        for (const player of safePlayers) {
            if (!player || typeof player !== "object") {
                continue;
            }
            const item = document.createElement("li");
            const avatar = document.createElement("span");
            const copy = document.createElement("span");
            const name = document.createElement("strong");
            const detail = document.createElement("small");

            item.className = "lobby-player";
            item.classList.toggle("is-self", Boolean(player.is_self));
            avatar.className = "lobby-player-avatar";
            avatar.setAttribute("aria-hidden", "true");
            avatar.textContent = playerInitial(player.name);
            copy.className = "lobby-player-copy";
            name.textContent = String(player.name || "Jogador");
            detail.textContent = player.is_self ? "Você · conectado" : "Conectado à sala";
            copy.append(name, detail);
            item.append(avatar, copy);

            if (player.is_host) {
                const badge = document.createElement("span");
                badge.className = "lobby-player-badge";
                badge.textContent = "DONO";
                item.appendChild(badge);
            }
            playerList.appendChild(item);
        }
    }

    function normalizeSeed(value) {
        const raw = String(value ?? "").trim();
        if (!/^[0-9]+$/.test(raw)) {
            return null;
        }
        const seed = Number(raw);
        if (!Number.isSafeInteger(seed) || seed < 0 || seed > MAX_SEED) {
            return null;
        }
        return seed;
    }

    function normalizeSize(value) {
        const size = Number(String(value ?? "").trim());
        if (!Number.isInteger(size) || size < MIN_WORLD_SIZE || size > MAX_WORLD_SIZE) {
            return null;
        }
        return size;
    }

    function validateConfiguration() {
        const seed = normalizeSeed(seedInput.value);
        const size = normalizeSize(sizeInput.value);
        const params = readMapParams();
        const seedValid = seed !== null;
        const sizeValid = size !== null;

        seedHint.classList.toggle("is-invalid", !seedValid);
        seedHint.textContent = seedValid
            ? "Seed + composição recriam este território."
            : `Digite uma seed entre 0 e ${MAX_SEED}.`;
        sizeHint.classList.toggle("is-invalid", !sizeValid);
        sizeHint.textContent = sizeValid
            ? "De 1 a 200 tiles por lado."
            : "O tamanho deve estar entre 1 e 200.";

        return seedValid && sizeValid ? {seed, size, params} : null;
    }

    function bridgeFailure(result, fallback) {
        if (result === false || result === null) {
            return fallback;
        }
        if (result && typeof result === "object" && result.ok === false) {
            return String(result.error || fallback);
        }
        return "";
    }

    async function configureLobby() {
        if (!state.isHost || state.busy) {
            return;
        }
        const values = validateConfiguration();
        if (!values) {
            return;
        }

        displayError("");
        setBusy(true);
        const result = await callBridge("configure_lobby", values.seed, values.size, values.params);
        const failure = bridgeFailure(result, "Não foi possível aplicar a seed e o tamanho escolhidos.");
        if (failure) {
            displayError(failure);
        } else {
            state.generating = true;
            const snapshot = normalizeSnapshot(result);
            if (snapshot && (snapshot.matrix || snapshot.lobby)) {
                applySnapshot(result);
            }
            updateAuthorityUi();
            updateStatus(state.status, state.serverError, state.generating);
            if (state.generating) {
                showGenerationOverlay(true);
            }
        }
        setBusy(false);
    }

    async function regenerateLobby() {
        if (!state.isHost || state.busy) {
            return;
        }
        const size = normalizeSize(sizeInput.value);
        if (size === null) {
            validateConfiguration();
            return;
        }
        const params = readMapParams();

        displayError("");
        setBusy(true);
        const result = await callBridge("regenerate_lobby", size, params);
        const failure = bridgeFailure(result, "Não foi possível criar outro mapa.");
        if (failure) {
            displayError(failure);
        } else {
            state.generating = true;
            const snapshot = normalizeSnapshot(result);
            if (snapshot && snapshot.matrix) {
                applySnapshot(result);
            }
            updateAuthorityUi();
            updateStatus(state.status, state.serverError, state.generating);
            if (state.generating) {
                showGenerationOverlay(true);
            }
        }
        setBusy(false);
    }

    async function startLobby() {
        if (
            !state.isHost
            || state.busy
            || state.generating
            || state.seedDirty
            || state.sizeDirty
            || state.paramsDirty
        ) {
            return;
        }

        displayError("");
        setBusy(true);
        const result = await callBridge("start_lobby");
        const failure = bridgeFailure(result, "Não foi possível iniciar a partida.");
        if (failure) {
            displayError(failure);
            setBusy(false);
            return;
        }
        // A troca de tela ocorre somente quando o snapshot autoritativo do
        // servidor informa que todos os jogadores entraram na partida.
    }

    async function leaveLobby() {
        if (state.busy) {
            return;
        }

        displayError("");
        setBusy(true);
        const result = await callBridge("leave_lobby");
        const failure = bridgeFailure(result, "A conexão com a sala já foi encerrada.");
        if (failure && result !== null) {
            displayError(failure);
            setBusy(false);
            return;
        }
        setBusy(false);
        requestView("main");
    }

    async function writeClipboard(text) {
        const value = String(text || "");
        if (!value) {
            return false;
        }

        try {
            if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
                await navigator.clipboard.writeText(value);
                return true;
            }
        } catch (_error) {
            // O fallback abaixo também funciona em WebViews sem permissão de clipboard.
        }

        const buffer = document.createElement("textarea");
        buffer.value = value;
        buffer.setAttribute("readonly", "");
        buffer.style.position = "fixed";
        buffer.style.left = "-9999px";
        buffer.style.opacity = "0";
        document.body.appendChild(buffer);
        buffer.select();
        let copied = false;
        try {
            copied = Boolean(document.execCommand && document.execCommand("copy"));
        } catch (_error) {
            copied = false;
        }
        buffer.remove();
        return copied;
    }

    async function copyWithFeedback(button, value) {
        const copied = await writeClipboard(value);
        const feedback = button.querySelector(".lobby-copy-feedback");
        const previousTimer = feedbackTimers.get(button);
        if (previousTimer) {
            window.clearTimeout(previousTimer);
        }
        feedback.textContent = copied ? "COPIADO" : "INDISPONÍVEL";
        button.classList.toggle("is-copied", copied);

        const timer = window.setTimeout(() => {
            feedbackTimers.delete(button);
            feedback.textContent = "COPIAR";
            button.classList.remove("is-copied");
        }, 1300);
        feedbackTimers.set(button, timer);
    }

    function applySnapshot(snapshot) {
        const lobby = normalizeSnapshot(snapshot);
        if (!lobby) {
            return;
        }

        const wasHost = state.isHost;
        const nextWorldRevision = lobby.world_revision ?? lobby.revision ?? 0;
        const width = Number.isInteger(Number(lobby.width))
            ? Number(lobby.width)
            : (Array.isArray(lobby.matrix) && Array.isArray(lobby.matrix[0]) ? lobby.matrix[0].length : 0);
        const height = Number.isInteger(Number(lobby.height))
            ? Number(lobby.height)
            : (Array.isArray(lobby.matrix) ? lobby.matrix.length : 0);
        const snapshotParams = normalizeMapParams(lobby.map_params);
        const snapshotComposition = normalizeMapComposition(lobby.map_composition);

        state.isHost = Boolean(lobby.is_host);
        state.generating = Boolean(lobby.generating);
        state.status = String(lobby.status || "");
        state.serverError = Boolean(lobby.error);
        state.code = String(lobby.code || "").toUpperCase();
        state.seed = String(lobby.seed ?? "");
        state.size = normalizeSize(lobby.size) || width || height || 0;
        const revisionChanged = state.lastDrawnRevision !== nextWorldRevision;
        if (revisionChanged && Array.isArray(lobby.matrix)) {
            state.seedDirty = false;
            state.sizeDirty = false;
            state.paramsDirty = false;
        }

        if (wasHost !== state.isHost) {
            state.seedDirty = false;
            state.sizeDirty = false;
            state.paramsDirty = false;
        }
        if (!state.seedDirty || !state.isHost) {
            seedInput.value = state.seed;
        }
        if (!state.sizeDirty || !state.isHost) {
            sizeInput.value = state.size > 0 ? String(state.size) : "";
        }
        if (!state.paramsDirty || !state.isHost) {
            renderMapSettings(snapshotParams || state.params, snapshotComposition);
        }

        code.textContent = state.code || "-------";
        mapSize.textContent = width > 0 && height > 0
            ? `${width} × ${height} TILES`
            : "— × — TILES";
        mapRevision.textContent = `MAPA ${nextWorldRevision || "—"}`;

        if (revisionChanged && Array.isArray(lobby.matrix)) {
            drawMap(lobby.matrix, width, height, nextWorldRevision);
        }
        if (state.generating || (state.lastDrawnRevision === null && !Array.isArray(lobby.matrix))) {
            showGenerationOverlay(state.generating);
        } else if (state.lastDrawnRevision !== null) {
            mapEmpty.hidden = true;
            mapFrame.setAttribute("aria-busy", "false");
        }

        updateAuthorityUi();
        updateStatus(state.status, state.serverError, state.generating);
        renderPlayers(lobby.players, lobby.player_count);

        if (lobby.error) {
            displayError(lobby.error);
            if (state.busy) {
                setBusy(false);
            }
        } else if (!state.localError) {
            errorBox.hidden = true;
        }
    }

    function show(visible = true) {
        const wasVisible = state.visible;
        state.visible = typeof visible === "string" ? visible === "lobby" : Boolean(visible);
        screen.hidden = !state.visible;
        if (state.visible && !wasVisible) {
            scheduleMapDraw();
        }
        if (!state.visible) {
            if (state.redrawFrame !== null) {
                window.cancelAnimationFrame(state.redrawFrame);
                state.redrawFrame = null;
            }
            seedInput.blur();
            sizeInput.blur();
            state.seedDirty = false;
            state.sizeDirty = false;
            state.paramsDirty = false;
            renderMapSettings(DEFAULT_MAP_PARAMS);
            state.generating = false;
            state.lastDrawnRevision = null;
            state.lastMap = null;
            state.lastPlayerSignature = "";
            setBusy(false);
            displayError("");
            showGenerationOverlay(false);
        }
    }

    listen(seedInput, "input", () => {
        state.seedDirty = true;
        seedInput.value = seedInput.value.replace(/[^0-9]/g, "").slice(0, 10);
        validateConfiguration();
        updateAuthorityUi();
    });
    listen(sizeInput, "input", () => {
        state.sizeDirty = true;
        validateConfiguration();
        updateAuthorityUi();
    });
    for (const input of Object.values(mapParamInputs)) {
        listen(input, "input", () => {
            if (!state.isHost || state.busy || state.generating) {
                return;
            }
            state.paramsDirty = true;
            renderMapSettings(readMapParams());
            updateAuthorityUi();
        });
    }
    listen(window, "resize", () => {
        if (state.visible && state.lastMap) {
            scheduleMapDraw();
        }
    });
    listen(seedInput, "keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            void configureLobby();
        }
    });
    listen(sizeInput, "keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            void configureLobby();
        }
    });

    disposers.push(bindPrimaryAction(copyCodeButton, () => {
        void copyWithFeedback(copyCodeButton, state.code);
    }));
    disposers.push(bindPrimaryAction(copySeedButton, () => {
        void copyWithFeedback(copySeedButton, seedInput.value || state.seed);
    }));
    disposers.push(bindPrimaryAction(applyButton, () => {
        void configureLobby();
    }));
    disposers.push(bindPrimaryAction(regenerateButton, () => {
        void regenerateLobby();
    }));
    disposers.push(bindPrimaryAction(startButton, () => {
        void startLobby();
    }));
    disposers.push(bindPrimaryAction(leaveButton, () => {
        void leaveLobby();
    }));

    renderMapSettings(DEFAULT_MAP_PARAMS);
    updateAuthorityUi();

    return {
        show,
        applySnapshot,
        dispose() {
            if (state.redrawFrame !== null) {
                window.cancelAnimationFrame(state.redrawFrame);
                state.redrawFrame = null;
            }
            for (const timer of feedbackTimers.values()) {
                window.clearTimeout(timer);
            }
            feedbackTimers.clear();
            while (disposers.length > 0) {
                disposers.pop()();
            }
        },
    };
}
