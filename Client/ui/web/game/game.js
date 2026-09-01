import {
    bindPrimaryAction,
    byId,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    VIEWPORT_RESIZE_EVENT,
} from "../shared/runtime.js";

const TILE_SIZE = 32;
const CAMERA_SPEED = 600;
const CAMERA_MARGIN = 256;
const MIN_ZOOM = 1;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.1;
const BUILD_INFO_SHOW_DELAY_MS = 320;
const BUILD_INFO_SWITCH_DELAY_MS = 70;
const BUILD_INFO_HIDE_DELAY_MS = 110;
const DEFAULT_TICK_INTERVAL_MS = 10000;
const RESOURCE_NAMES = ["gold", "wood", "food"];

export function createGame({callBridge, viewport}) {
    const gameScreen = byId("game-screen");
    const buildMenu = byId("build-menu");
    const buildPanel = byId("build-panel");
    const buildPanelToggle = byId("build-panel-toggle");
    const buildInfo = byId("build-info");
    const buildInfoCategory = byId("build-info-category");
    const buildInfoName = byId("build-info-name");
    const buildInfoRequirement = byId("build-info-requirement");
    const buildInfoDescription = byId("build-info-description");
    const buildInfoStatus = byId("build-info-status");
    const buildCostFree = byId("build-cost-free");
    const gameTick = byId("game-tick");
    const tickCountdownValue = byId("tick-countdown-value");
    const tickProgress = byId("tick-progress");
    const tickCycleNumber = byId("tick-cycle-number");
    const buildCosts = Object.fromEntries(RESOURCE_NAMES.map((resource) => [
        resource,
        {
            root: byId(`build-cost-${resource}`),
            value: byId(`build-cost-${resource}-value`),
        },
    ]));
    const canvas = byId("world-canvas");
    const context = canvas.getContext("2d", {alpha: true});
    const disposers = [];
    let buildInfoShowTimer = null;
    let buildInfoHideTimer = null;
    let inspectedBuildButton = null;

    if (!context) {
        throw new Error("Não foi possível inicializar o canvas do jogo.");
    }
    context.imageSmoothingEnabled = false;

    const state = {
        visible: false,
        matrix: null,
        worldWidth: 0,
        worldHeight: 0,
        resources: {
            gold: 500,
            wood: 500,
            food: 500,
        },
        cameraX: 0,
        cameraY: 0,
        zoom: 1,
        viewportWidth: LOGICAL_WIDTH,
        viewportHeight: LOGICAL_HEIGHT,
        selectedTile: null,
        buildOpen: false,
        interactionLocked: false,
        heldKeys: new Set(),
        focusedSpawnKey: null,
        tickIntervalMs: DEFAULT_TICK_INTERVAL_MS,
        tickRemainingAtSyncMs: DEFAULT_TICK_INTERVAL_MS,
        tickSyncedAtMs: performance.now(),
        tickNumber: 0,
        displayedTickTenths: null,
        displayedTickProgress: null,
        displayedTickNumber: null,
    };

    const tileImages = {
        grass: byId("asset-grass"),
        town_center: byId("asset-town-center"),
        lumberjack_cabin: byId("asset-lumberjack-cabin"),
        madeireiro: byId("asset-lumberjack-cabin"),
        small_forest: byId("asset-small-forest"),
        mountain: byId("asset-mountain"),
        mine: byId("asset-mine"),
        city: byId("asset-city"),
        water: byId("asset-water"),
        medium_forest: byId("asset-medium-forest"),
        big_forest: byId("asset-big-forest"),
    };
    const selectedImage = byId("asset-selected");

    function listen(target, type, listener, options) {
        target.addEventListener(type, listener, options);
        disposers.push(() => target.removeEventListener(type, listener, options));
    }

    function syncCanvasResolution() {
        const width = Math.max(1, Math.round(state.viewportWidth));
        const height = Math.max(1, Math.round(state.viewportHeight));

        if (canvas.width !== width) {
            canvas.width = width;
        }
        if (canvas.height !== height) {
            canvas.height = height;
        }
        context.imageSmoothingEnabled = false;
    }

    function handleViewportResize(event) {
        const nextWidth = Number(event.detail?.logicalWidth);
        const nextHeight = Number(event.detail?.logicalHeight);
        if (
            !Number.isInteger(nextWidth) ||
            !Number.isInteger(nextHeight) ||
            nextWidth < 1 ||
            nextHeight < 1
        ) {
            return;
        }

        const centerX = state.cameraX + state.viewportWidth / (2 * state.zoom);
        const centerY = state.cameraY + state.viewportHeight / (2 * state.zoom);
        const dimensionsChanged = (
            nextWidth !== state.viewportWidth ||
            nextHeight !== state.viewportHeight
        );

        state.viewportWidth = nextWidth;
        state.viewportHeight = nextHeight;
        syncCanvasResolution();

        if (dimensionsChanged && state.worldWidth > 0 && state.worldHeight > 0) {
            state.cameraX = centerX - state.viewportWidth / (2 * state.zoom);
            state.cameraY = centerY - state.viewportHeight / (2 * state.zoom);
            clampCamera();
        }
    }

    syncCanvasResolution();
    listen(viewport, VIEWPORT_RESIZE_EVENT, handleViewportResize);

    function clearBuildInfoTimers() {
        if (buildInfoShowTimer !== null) {
            window.clearTimeout(buildInfoShowTimer);
            buildInfoShowTimer = null;
        }
        if (buildInfoHideTimer !== null) {
            window.clearTimeout(buildInfoHideTimer);
            buildInfoHideTimer = null;
        }
    }

    function buildCost(button, resource) {
        const property = `cost${resource[0].toUpperCase()}${resource.slice(1)}`;
        return Math.max(0, Number(button.dataset[property]) || 0);
    }

    function refreshBuildInfoCosts(button) {
        let isFree = true;
        let isAffordable = true;

        for (const resource of RESOURCE_NAMES) {
            const cost = buildCost(button, resource);
            const available = Number(state.resources[resource]) || 0;
            const costUi = buildCosts[resource];
            const isUnaffordable = cost > available;

            costUi.root.hidden = cost === 0;
            costUi.value.textContent = String(cost);
            costUi.root.classList.toggle("is-unaffordable", isUnaffordable);
            isFree = isFree && cost === 0;
            isAffordable = isAffordable && !isUnaffordable;
        }

        buildCostFree.hidden = !isFree;
        buildInfoStatus.classList.toggle("is-unavailable", !isAffordable);
        if (isFree) {
            buildInfoStatus.textContent = "SEM CUSTO";
        } else if (isAffordable) {
            buildInfoStatus.textContent = "DISPONÍVEL";
        } else {
            buildInfoStatus.textContent = "RECURSOS INSUFICIENTES";
        }
    }

    function showBuildInfo(button) {
        if (inspectedBuildButton && inspectedBuildButton !== button) {
            inspectedBuildButton.classList.remove("is-inspected");
            inspectedBuildButton.removeAttribute("aria-describedby");
        }

        inspectedBuildButton = button;
        buildInfoCategory.textContent = button.dataset.category || "CONSTRUÇÃO";
        buildInfoName.textContent = button.dataset.name || button.dataset.tile;
        buildInfoDescription.textContent = button.dataset.description || "";
        buildInfoRequirement.textContent = button.dataset.requirement || "";
        buildInfoRequirement.hidden = !button.dataset.requirement;
        refreshBuildInfoCosts(button);

        button.classList.add("is-inspected");
        button.setAttribute("aria-describedby", "build-info");
        buildInfo.classList.add("is-visible");
        buildInfo.setAttribute("aria-hidden", "false");
    }

    function scheduleBuildInfo(button, immediate = false) {
        if (buildInfoHideTimer !== null) {
            window.clearTimeout(buildInfoHideTimer);
            buildInfoHideTimer = null;
        }
        if (buildInfoShowTimer !== null) {
            window.clearTimeout(buildInfoShowTimer);
        }

        if (inspectedBuildButton === button && buildInfo.classList.contains("is-visible")) {
            refreshBuildInfoCosts(button);
            buildInfoShowTimer = null;
            return;
        }

        if (immediate) {
            buildInfoShowTimer = null;
            showBuildInfo(button);
            return;
        }

        const delay = buildInfo.classList.contains("is-visible")
            ? BUILD_INFO_SWITCH_DELAY_MS
            : BUILD_INFO_SHOW_DELAY_MS;
        buildInfoShowTimer = window.setTimeout(() => {
            buildInfoShowTimer = null;
            showBuildInfo(button);
        }, delay);
    }

    function hideBuildInfo() {
        clearBuildInfoTimers();
        buildInfo.classList.remove("is-visible");
        buildInfo.setAttribute("aria-hidden", "true");
        if (inspectedBuildButton) {
            inspectedBuildButton.classList.remove("is-inspected");
            inspectedBuildButton.removeAttribute("aria-describedby");
            inspectedBuildButton = null;
        }
    }

    function scheduleBuildInfoHide() {
        if (buildInfoShowTimer !== null) {
            window.clearTimeout(buildInfoShowTimer);
            buildInfoShowTimer = null;
        }
        if (buildInfoHideTimer !== null) {
            window.clearTimeout(buildInfoHideTimer);
        }
        buildInfoHideTimer = window.setTimeout(() => {
            buildInfoHideTimer = null;
            if (
                inspectedBuildButton &&
                (
                    inspectedBuildButton.matches(":hover") ||
                    document.activeElement === inspectedBuildButton
                )
            ) {
                return;
            }
            hideBuildInfo();
        }, BUILD_INFO_HIDE_DELAY_MS);
    }

    function setBuildVisibility() {
        const panelOpen = state.visible && state.buildOpen;

        // O contêiner permanece montado durante a partida para que o CSS possa
        // animá-lo até a borda inferior; somente a aba fica exposta ao fechar.
        buildMenu.hidden = !state.visible;
        buildMenu.classList.toggle("is-open", panelOpen);
        buildMenu.setAttribute("aria-hidden", String(!state.visible));
        buildPanel.setAttribute("aria-hidden", String(!panelOpen));
        buildPanel.inert = !panelOpen;
        buildPanelToggle.setAttribute("aria-expanded", String(panelOpen));
        buildPanelToggle.setAttribute(
            "aria-label",
            panelOpen ? "Fechar menu de construções" : "Abrir menu de construções",
        );

        if (!panelOpen) {
            hideBuildInfo();
        }
    }

    function setVisible(visible) {
        state.visible = Boolean(visible);
        gameScreen.hidden = !state.visible;
        if (!state.visible) {
            state.heldKeys.clear();
            state.buildOpen = false;
        }
        setBuildVisibility();
    }

    function setInteractionLocked(locked) {
        state.interactionLocked = Boolean(locked);
        if (state.interactionLocked) {
            state.heldKeys.clear();
            hideBuildInfo();
        }
    }

    function updateResourceHud() {
        byId("gold-value").textContent = String(state.resources.gold);
        byId("wood-value").textContent = String(state.resources.wood);
        byId("food-value").textContent = String(state.resources.food);
        if (inspectedBuildButton && buildInfo.classList.contains("is-visible")) {
            refreshBuildInfoCosts(inspectedBuildButton);
        }
    }

    function applyTickSnapshot(snapshot) {
        const intervalMs = snapshot.tick_interval_ms;
        const remainingMs = snapshot.tick_remaining_ms;
        const tickNumber = snapshot.tick_number;

        if (Number.isFinite(intervalMs) && intervalMs > 0) {
            state.tickIntervalMs = intervalMs;
        }
        if (Number.isFinite(remainingMs) && remainingMs >= 0) {
            state.tickRemainingAtSyncMs = Math.min(
                state.tickIntervalMs,
                remainingMs,
            );
            state.tickSyncedAtMs = performance.now();
        }
        if (Number.isInteger(tickNumber) && tickNumber >= 0) {
            state.tickNumber = tickNumber;
        }
    }

    function updateTickHud(now) {
        const elapsedMs = Math.max(0, now - state.tickSyncedAtMs);
        const remainingMs = Math.max(
            0,
            state.tickRemainingAtSyncMs - elapsedMs,
        );
        const remainingTenths = Math.ceil(remainingMs / 100);
        const progress = Math.max(
            0,
            Math.min(1, remainingMs / state.tickIntervalMs),
        );
        const progressPercent = Math.round(progress * 100);

        if (remainingTenths !== state.displayedTickTenths) {
            const seconds = (remainingTenths / 10).toFixed(1).replace(".", ",");
            tickCountdownValue.textContent = seconds;
            gameTick.setAttribute(
                "aria-label",
                `Próximo ciclo do jogo em ${seconds} segundos`,
            );
            state.displayedTickTenths = remainingTenths;
        }
        tickProgress.style.setProperty("--tick-progress", String(progress));
        if (progressPercent !== state.displayedTickProgress) {
            tickProgress.setAttribute("aria-valuenow", String(progressPercent));
            state.displayedTickProgress = progressPercent;
        }
        if (state.tickNumber !== state.displayedTickNumber) {
            tickCycleNumber.textContent = `CICLO ${state.tickNumber + 1}`;
            state.displayedTickNumber = state.tickNumber;
        }
    }

    function applySnapshot(snapshot) {
        if (!snapshot || typeof snapshot !== "object") {
            return;
        }

        applyTickSnapshot(snapshot);
        updateTickHud(performance.now());

        if (Array.isArray(snapshot.matrix)) {
            state.matrix = snapshot.matrix;
        }

        const width = Number(snapshot.width);
        const height = Number(snapshot.height);
        if (Number.isInteger(width) && width >= 0) {
            state.worldWidth = width;
        } else if (state.matrix && state.matrix[0]) {
            state.worldWidth = state.matrix[0].length;
        }
        if (Number.isInteger(height) && height >= 0) {
            state.worldHeight = height;
        } else if (state.matrix) {
            state.worldHeight = state.matrix.length;
        }

        const spawnPosition = snapshot.spawn_position;
        if (
            Array.isArray(spawnPosition) &&
            spawnPosition.length === 2 &&
            spawnPosition.every(Number.isInteger)
        ) {
            const [spawnX, spawnY] = spawnPosition;
            const spawnKey = `${spawnX},${spawnY}`;
            if (state.focusedSpawnKey !== spawnKey) {
                state.focusedSpawnKey = spawnKey;
                state.cameraX = (
                    (spawnX + 0.5) * TILE_SIZE - state.viewportWidth / (2 * state.zoom)
                );
                state.cameraY = (
                    (spawnY + 0.5) * TILE_SIZE - state.viewportHeight / (2 * state.zoom)
                );
                clampCamera();
            }
        } else if (spawnPosition === null) {
            state.focusedSpawnKey = null;
        }

        if (snapshot.resources && typeof snapshot.resources === "object") {
            for (const resource of ["gold", "wood", "food"]) {
                if (Object.prototype.hasOwnProperty.call(snapshot.resources, resource)) {
                    state.resources[resource] = snapshot.resources[resource];
                }
            }
            updateResourceHud();
        }
    }

    async function buildTile(tile) {
        if (state.interactionLocked || !state.selectedTile) {
            return;
        }
        await callBridge(
            "build_tile",
            state.selectedTile.x,
            state.selectedTile.y,
            tile,
        );
    }

    function logicalPoint(clientX, clientY) {
        const rect = viewport.getBoundingClientRect();
        if (
            clientX < rect.left ||
            clientY < rect.top ||
            clientX >= rect.right ||
            clientY >= rect.bottom
        ) {
            return null;
        }

        return {
            x: Math.max(0, Math.min(state.viewportWidth - 1, Math.trunc(
                (clientX - rect.left) * state.viewportWidth / rect.width,
            ))),
            y: Math.max(0, Math.min(state.viewportHeight - 1, Math.trunc(
                (clientY - rect.top) * state.viewportHeight / rect.height,
            ))),
        };
    }

    function selectTile(point) {
        if (!state.matrix || state.worldWidth <= 0 || state.worldHeight <= 0) {
            return;
        }

        const worldX = state.cameraX + point.x / state.zoom;
        const worldY = state.cameraY + point.y / state.zoom;
        const tileX = Math.floor(worldX / TILE_SIZE);
        const tileY = Math.floor(worldY / TILE_SIZE);

        if (
            tileX < 0 ||
            tileY < 0 ||
            tileX >= state.worldWidth ||
            tileY >= state.worldHeight
        ) {
            return;
        }

        if (
            state.selectedTile &&
            state.selectedTile.x === tileX &&
            state.selectedTile.y === tileY
        ) {
            state.buildOpen = !state.buildOpen;
        } else {
            state.selectedTile = {x: tileX, y: tileY};
            state.buildOpen = true;
        }
        setBuildVisibility();
    }

    function clampCamera() {
        if (state.worldWidth <= 0 || state.worldHeight <= 0) {
            return;
        }

        const visibleWidth = state.viewportWidth / state.zoom;
        const visibleHeight = state.viewportHeight / state.zoom;
        const maxX = state.worldWidth * TILE_SIZE - visibleWidth + CAMERA_MARGIN;
        const maxY = state.worldHeight * TILE_SIZE - visibleHeight + CAMERA_MARGIN;

        state.cameraX = Math.max(-CAMERA_MARGIN, Math.min(state.cameraX, maxX));
        state.cameraY = Math.max(-CAMERA_MARGIN, Math.min(state.cameraY, maxY));
    }

    function updateCamera(deltaSeconds) {
        const movement = CAMERA_SPEED * deltaSeconds / state.zoom;

        if (state.heldKeys.has("KeyA")) {
            state.cameraX -= movement;
        }
        if (state.heldKeys.has("KeyD")) {
            state.cameraX += movement;
        }
        if (state.heldKeys.has("KeyW")) {
            state.cameraY -= movement;
        }
        if (state.heldKeys.has("KeyS")) {
            state.cameraY += movement;
        }

        clampCamera();
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

    function imageIsReady(image) {
        return image && image.complete && image.naturalWidth > 0;
    }

    function drawWorld() {
        context.clearRect(0, 0, state.viewportWidth, state.viewportHeight);

        if (!state.matrix || state.worldWidth <= 0 || state.worldHeight <= 0) {
            return;
        }

        const scaledSize = Math.max(1, Math.ceil(TILE_SIZE * state.zoom));
        const startX = Math.max(0, Math.floor(state.cameraX / TILE_SIZE) - 1);
        const startY = Math.max(0, Math.floor(state.cameraY / TILE_SIZE) - 1);
        const endX = Math.min(
            state.worldWidth,
            Math.ceil((state.cameraX + state.viewportWidth / state.zoom) / TILE_SIZE) + 1,
        );
        const endY = Math.min(
            state.worldHeight,
            Math.ceil((state.cameraY + state.viewportHeight / state.zoom) / TILE_SIZE) + 1,
        );

        for (let y = startY; y < endY; y += 1) {
            const row = state.matrix[y];
            if (!Array.isArray(row)) {
                continue;
            }

            for (let x = startX; x < endX; x += 1) {
                const image = tileImages[tileName(row[x])] || tileImages.grass;
                if (!imageIsReady(image)) {
                    continue;
                }

                const screenX = Math.trunc((x * TILE_SIZE - state.cameraX) * state.zoom);
                const screenY = Math.trunc((y * TILE_SIZE - state.cameraY) * state.zoom);
                context.drawImage(image, screenX, screenY, scaledSize, scaledSize);
            }
        }

        if (state.selectedTile && imageIsReady(selectedImage)) {
            const {x, y} = state.selectedTile;
            if (x >= 0 && y >= 0 && x < state.worldWidth && y < state.worldHeight) {
                const screenX = Math.trunc((x * TILE_SIZE - state.cameraX) * state.zoom);
                const screenY = Math.trunc((y * TILE_SIZE - state.cameraY) * state.zoom);
                context.drawImage(selectedImage, screenX, screenY, scaledSize, scaledSize);
            }
        }
    }

    listen(canvas, "pointerdown", (event) => {
        if (event.button !== 0 || !state.visible || state.interactionLocked) {
            return;
        }

        const point = logicalPoint(event.clientX, event.clientY);
        if (point) {
            event.preventDefault();
            selectTile(point);
        }
    });

    listen(gameScreen, "wheel", (event) => {
        if (!state.visible || state.interactionLocked || event.deltaY === 0) {
            return;
        }

        const point = logicalPoint(event.clientX, event.clientY);
        if (!point) {
            return;
        }

        event.preventDefault();
        const oldZoom = state.zoom;
        const direction = event.deltaY < 0 ? 1 : -1;
        const nextZoom = Math.max(
            MIN_ZOOM,
            Math.min(MAX_ZOOM, Math.round((oldZoom + direction * ZOOM_STEP) * 10) / 10),
        );

        if (nextZoom === oldZoom) {
            return;
        }

        const worldX = state.cameraX + point.x / oldZoom;
        const worldY = state.cameraY + point.y / oldZoom;
        state.zoom = nextZoom;
        state.cameraX = worldX - point.x / nextZoom;
        state.cameraY = worldY - point.y / nextZoom;
        clampCamera();
    }, {passive: false});

    listen(document, "keydown", (event) => {
        if (!state.visible) {
            return;
        }

        if (
            event.code === "Escape" &&
            (
                buildInfo.classList.contains("is-visible") ||
                buildInfoShowTimer !== null
            )
        ) {
            event.preventDefault();
            hideBuildInfo();
            return;
        }

        if (state.interactionLocked) {
            return;
        }

        if (event.code === "Escape" && state.buildOpen) {
            event.preventDefault();
            state.buildOpen = false;
            setBuildVisibility();
            return;
        }

        if (["KeyW", "KeyA", "KeyS", "KeyD"].includes(event.code)) {
            event.preventDefault();
            state.heldKeys.add(event.code);
            return;
        }

        const noModifiers = !event.ctrlKey && !event.metaKey && !event.altKey;
        if (
            !state.buildOpen ||
            !state.selectedTile ||
            event.repeat ||
            !noModifiers
        ) {
            return;
        }

        if (event.code === "KeyV") {
            event.preventDefault();
            void buildTile("town_center");
        } else if (event.code === "KeyB") {
            event.preventDefault();
            void buildTile("small_forest");
        }
    });

    listen(document, "keyup", (event) => {
        state.heldKeys.delete(event.code);
    });

    listen(window, "blur", () => state.heldKeys.clear());

    disposers.push(bindPrimaryAction(buildPanelToggle, () => {
        if (!state.visible || state.interactionLocked) {
            return;
        }
        state.buildOpen = !state.buildOpen;
        setBuildVisibility();
    }));

    for (const button of document.querySelectorAll(".build-button")) {
        listen(button, "pointerenter", () => scheduleBuildInfo(button));
        listen(button, "pointerleave", scheduleBuildInfoHide);
        listen(button, "pointercancel", scheduleBuildInfoHide);
        listen(button, "focus", () => scheduleBuildInfo(button, true));
        listen(button, "blur", scheduleBuildInfoHide);
        disposers.push(bindPrimaryAction(button, () => {
            void buildTile(button.dataset.tile);
        }));
    }

    updateResourceHud();
    updateTickHud(performance.now());

    let previousFrameTime = performance.now();
    let animationFrameId = null;
    function frame(time) {
        const deltaSeconds = Math.min(
            0.1,
            Math.max(0, (time - previousFrameTime) / 1000),
        );
        previousFrameTime = time;

        if (state.visible) {
            updateTickHud(time);
            if (!state.interactionLocked) {
                updateCamera(deltaSeconds);
            }
            drawWorld();
        }

        animationFrameId = window.requestAnimationFrame(frame);
    }
    animationFrameId = window.requestAnimationFrame(frame);

    return {
        applySnapshot,
        setVisible,
        setInteractionLocked,
        dispose() {
            hideBuildInfo();
            if (animationFrameId !== null) {
                window.cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
            while (disposers.length > 0) {
                disposers.pop()();
            }
            state.heldKeys.clear();
        },
    };
}
