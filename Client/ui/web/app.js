(() => {
    "use strict";

    const LOGICAL_WIDTH = 1280;
    const LOGICAL_HEIGHT = 960;
    const TILE_SIZE = 32;
    const CAMERA_SPEED = 600;
    const CAMERA_MARGIN = 256;
    const MIN_ZOOM = 1;
    const MAX_ZOOM = 2.5;
    const ZOOM_STEP = 0.1;
    const SNAPSHOT_INTERVAL_MS = 50;

    const byId = (id) => document.getElementById(id);

    const viewport = byId("viewport");
    const menuScreen = byId("menu-screen");
    const gameScreen = byId("game-screen");
    const mainMenu = byId("main-menu");
    const hostMenu = byId("host-menu");
    const connectMenu = byId("connect-menu");
    const buildMenu = byId("build-menu");
    const canvas = byId("world-canvas");
    const context = canvas.getContext("2d", {alpha: false});

    context.imageSmoothingEnabled = false;

    const state = {
        view: "main",
        worldRevision: -1,
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
        selectedTile: null,
        buildOpen: false,
        heldKeys: new Set(),
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

    let bridgeReady = false;
    let snapshotTimer = null;

    function fitViewport() {
        const availableWidth = Math.max(1, window.innerWidth);
        const availableHeight = Math.max(1, window.innerHeight);
        const scale = Math.min(
            availableWidth / LOGICAL_WIDTH,
            availableHeight / LOGICAL_HEIGHT,
        );
        const renderWidth = Math.max(1, Math.trunc(LOGICAL_WIDTH * scale));
        const renderHeight = Math.max(1, Math.trunc(LOGICAL_HEIGHT * scale));
        const offsetX = Math.floor((availableWidth - renderWidth) / 2);
        const offsetY = Math.floor((availableHeight - renderHeight) / 2);

        viewport.style.left = `${offsetX}px`;
        viewport.style.top = `${offsetY}px`;
        viewport.style.transform = `scale(${renderWidth / LOGICAL_WIDTH}, ${renderHeight / LOGICAL_HEIGHT})`;
    }

    function setBuildVisibility() {
        buildMenu.hidden = state.view !== "game" || !state.buildOpen;
    }

    function setView(view) {
        if (!["main", "host", "connect", "game"].includes(view)) {
            return;
        }

        state.view = view;
        menuScreen.hidden = view === "game";
        gameScreen.hidden = view !== "game";
        mainMenu.hidden = view !== "main";
        hostMenu.hidden = view !== "host";
        connectMenu.hidden = view !== "connect";
        setBuildVisibility();

        if (view !== "host") {
            byId("world-size-input").blur();
        }
        if (view !== "connect") {
            byId("game-code-input").blur();
        }

        if (view !== "game") {
            state.heldKeys.clear();
        }
    }

    function createTextField(inputId, displayId, placeholder, allowedCharacter, limit, handlers = {}) {
        const input = byId(inputId);
        const display = byId(displayId);

        function refresh() {
            if (document.activeElement === input) {
                display.textContent = `${input.value}|`;
            } else {
                display.textContent = input.value || placeholder;
            }
        }

        function clear() {
            input.value = "";
            refresh();
        }

        function focus() {
            input.focus({preventScroll: true});
            refresh();
        }

        input.addEventListener("focus", refresh);
        input.addEventListener("blur", refresh);
        input.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) {
                event.preventDefault();
            }
        });
        input.addEventListener("paste", (event) => event.preventDefault());
        input.addEventListener("drop", (event) => event.preventDefault());
        input.addEventListener("keydown", (event) => {
            if (event.code === "F11") {
                return;
            }

            event.preventDefault();
            if (event.repeat) {
                return;
            }

            if (event.key === "Enter") {
                if (handlers.confirm) {
                    handlers.confirm(input.value);
                }
                return;
            }

            if (event.key === "Escape") {
                if (handlers.cancel) {
                    handlers.cancel();
                }
                return;
            }

            if (event.key === "Backspace") {
                input.value = input.value.slice(0, -1);
                refresh();
                return;
            }

            if (event.ctrlKey || event.metaKey || event.altKey || event.key.length !== 1) {
                return;
            }

            const character = event.key.toUpperCase();
            if (allowedCharacter.test(character) && input.value.length < limit) {
                input.value += character;
                refresh();
            }
        });

        return {
            input,
            clear,
            focus,
            blur: () => input.blur(),
            get value() {
                return input.value;
            },
        };
    }

    const worldSizeField = createTextField(
        "world-size-input",
        "world-size-display",
        "TAMANHO DO MUNDO",
        /^[0-9]$/,
        3,
    );

    const gameCodeField = createTextField(
        "game-code-input",
        "game-code-display",
        "CÓDIGO",
        /^[0-9A-Z]$/,
        7,
        {
            confirm: (value) => void connectGame(value),
            cancel: () => setView("main"),
        },
    );

    menuScreen.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) {
            return;
        }
        if (state.view === "host" && !byId("world-size-field").contains(event.target)) {
            worldSizeField.blur();
        } else if (
            state.view === "connect" &&
            !byId("game-code-field").contains(event.target)
        ) {
            gameCodeField.blur();
        }
    });

    async function callBridge(method, ...args) {
        if (!bridgeReady) {
            return null;
        }

        const api = window.pywebview && window.pywebview.api;
        if (!api || typeof api[method] !== "function") {
            return null;
        }

        try {
            return await api[method](...args);
        } catch (_error) {
            return null;
        }
    }

    function normalizeRemoteScreen(screen) {
        const value = String(screen || "").toLowerCase();

        if (value === "game" || value === "partida") {
            return "game";
        }
        if (value === "host" || value === "menu_host" || value === "menu_hostear") {
            return "host";
        }
        if (value === "connect" || value === "menu_connect" || value === "menu_conectar") {
            return "connect";
        }
        return "main";
    }

    function applyRemoteScreen(screen) {
        const remoteView = normalizeRemoteScreen(screen);

        if (remoteView === "game") {
            setView("game");
        } else if (remoteView === "host" || remoteView === "connect") {
            setView(remoteView);
        } else if (state.view === "game") {
            setView("main");
        }
    }

    function applySnapshot(snapshot) {
        if (!snapshot || typeof snapshot !== "object") {
            return;
        }

        if (Object.prototype.hasOwnProperty.call(snapshot, "world_revision")) {
            state.worldRevision = snapshot.world_revision;
        }

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

        if (snapshot.resources && typeof snapshot.resources === "object") {
            for (const resource of ["gold", "wood", "food"]) {
                if (Object.prototype.hasOwnProperty.call(snapshot.resources, resource)) {
                    state.resources[resource] = snapshot.resources[resource];
                }
            }
            updateResourceHud();
        }

        applyRemoteScreen(snapshot.screen);
    }

    async function pollSnapshot() {
        if (!bridgeReady) {
            return;
        }

        const snapshot = await callBridge("get_snapshot", state.worldRevision);
        applySnapshot(snapshot);

        if (bridgeReady) {
            snapshotTimer = window.setTimeout(pollSnapshot, SNAPSHOT_INTERVAL_MS);
        }
    }

    function startBridge() {
        if (bridgeReady) {
            return;
        }
        bridgeReady = true;
        void pollSnapshot();
    }

    async function hostGame() {
        worldSizeField.blur();
        const rawValue = worldSizeField.value;

        if (!/^[0-9]+$/.test(rawValue)) {
            return;
        }

        const value = Number(rawValue);
        if (!Number.isInteger(value) || value < 1 || value > 200) {
            return;
        }

        await callBridge("host_game", value);
    }

    async function connectGame(code) {
        const result = await callBridge("connect_game", String(code).toUpperCase());
        if (result && result.ok === false) {
            gameCodeField.clear();
            gameCodeField.focus();
        }
    }

    async function buildTile(tile) {
        if (!state.selectedTile) {
            return;
        }
        await callBridge(
            "build_tile",
            state.selectedTile.x,
            state.selectedTile.y,
            tile,
        );
    }

    function onPrimaryPointerDown(element, action) {
        element.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) {
                return;
            }
            event.preventDefault();
            action(event);
        });
        element.addEventListener("click", (event) => {
            if (event.detail !== 0) {
                return;
            }
            event.preventDefault();
            action(event);
        });
    }

    onPrimaryPointerDown(byId("host-button"), () => {
        worldSizeField.clear();
        setView("host");
        window.requestAnimationFrame(() => worldSizeField.focus());
    });

    onPrimaryPointerDown(byId("connect-button"), () => {
        gameCodeField.clear();
        setView("connect");
        window.requestAnimationFrame(() => gameCodeField.focus());
    });

    onPrimaryPointerDown(byId("exit-button"), () => {
        void callBridge("close_window");
    });

    onPrimaryPointerDown(byId("fullscreen-button"), () => {
        void callBridge("toggle_fullscreen");
    });

    onPrimaryPointerDown(byId("start-host-button"), () => {
        void hostGame();
    });

    for (const button of document.querySelectorAll(".build-button")) {
        onPrimaryPointerDown(button, () => {
            void buildTile(button.dataset.tile);
        });
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
            x: Math.max(0, Math.min(LOGICAL_WIDTH - 1, Math.trunc(
                (clientX - rect.left) * LOGICAL_WIDTH / rect.width,
            ))),
            y: Math.max(0, Math.min(LOGICAL_HEIGHT - 1, Math.trunc(
                (clientY - rect.top) * LOGICAL_HEIGHT / rect.height,
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

    canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || state.view !== "game") {
            return;
        }

        const point = logicalPoint(event.clientX, event.clientY);
        if (point) {
            event.preventDefault();
            selectTile(point);
        }
    });

    function clampCamera() {
        if (state.worldWidth <= 0 || state.worldHeight <= 0) {
            return;
        }

        const visibleWidth = LOGICAL_WIDTH / state.zoom;
        const visibleHeight = LOGICAL_HEIGHT / state.zoom;
        const maxX = state.worldWidth * TILE_SIZE - visibleWidth + CAMERA_MARGIN;
        const maxY = state.worldHeight * TILE_SIZE - visibleHeight + CAMERA_MARGIN;

        state.cameraX = Math.max(-CAMERA_MARGIN, Math.min(state.cameraX, maxX));
        state.cameraY = Math.max(-CAMERA_MARGIN, Math.min(state.cameraY, maxY));
    }

    gameScreen.addEventListener("wheel", (event) => {
        if (state.view !== "game" || event.deltaY === 0) {
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

    function noModifiers(event) {
        return !event.ctrlKey && !event.metaKey && !event.altKey;
    }

    document.addEventListener("keydown", (event) => {
        if (event.code === "F11") {
            event.preventDefault();
            if (!event.repeat) {
                void callBridge("toggle_fullscreen");
            }
            return;
        }

        if (state.view === "main" && event.code === "KeyF" && noModifiers(event)) {
            event.preventDefault();
            if (!event.repeat) {
                void callBridge("toggle_fullscreen");
            }
            return;
        }

        if (state.view !== "game") {
            return;
        }

        if (["KeyW", "KeyA", "KeyS", "KeyD"].includes(event.code)) {
            event.preventDefault();
            state.heldKeys.add(event.code);
            return;
        }

        if (!state.buildOpen || !state.selectedTile || event.repeat || !noModifiers(event)) {
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

    document.addEventListener("keyup", (event) => {
        state.heldKeys.delete(event.code);
    });

    window.addEventListener("blur", () => state.heldKeys.clear());

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
        context.fillStyle = "#000";
        context.fillRect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT);

        if (!state.matrix || state.worldWidth <= 0 || state.worldHeight <= 0) {
            return;
        }

        const scaledSize = Math.max(1, Math.trunc(TILE_SIZE * state.zoom));
        const startX = Math.max(0, Math.floor(state.cameraX / TILE_SIZE) - 1);
        const startY = Math.max(0, Math.floor(state.cameraY / TILE_SIZE) - 1);
        const endX = Math.min(
            state.worldWidth,
            Math.ceil((state.cameraX + LOGICAL_WIDTH / state.zoom) / TILE_SIZE) + 1,
        );
        const endY = Math.min(
            state.worldHeight,
            Math.ceil((state.cameraY + LOGICAL_HEIGHT / state.zoom) / TILE_SIZE) + 1,
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

    function updateResourceHud() {
        byId("gold-value").textContent = `Gold: ${state.resources.gold}`;
        byId("wood-value").textContent = `Wood: ${state.resources.wood}`;
        byId("food-value").textContent = `Food: ${state.resources.food}`;
    }

    let previousFrameTime = performance.now();
    function frame(time) {
        const deltaSeconds = Math.min(0.1, Math.max(0, (time - previousFrameTime) / 1000));
        previousFrameTime = time;

        if (state.view === "game") {
            updateCamera(deltaSeconds);
            drawWorld();
        }

        window.requestAnimationFrame(frame);
    }

    viewport.addEventListener("contextmenu", (event) => event.preventDefault());
    viewport.addEventListener("dragstart", (event) => event.preventDefault());
    window.addEventListener("resize", fitViewport);
    window.addEventListener("pywebviewready", startBridge, {once: true});

    fitViewport();
    updateResourceHud();
    setView("main");
    window.requestAnimationFrame(frame);

    window.addEventListener("pagehide", () => {
        if (snapshotTimer !== null) {
            window.clearTimeout(snapshotTimer);
            snapshotTimer = null;
        }
        bridgeReady = false;
    });
})();
