import {createGame} from "./game/game.js";
import {createLobby} from "./lobby/lobby.js";
import {createMenu} from "./menu/menu.js";
import {createBridge} from "./shared/bridge.js";
import {byId, initializeViewport} from "./shared/runtime.js";

const SNAPSHOT_INTERVAL_MS = 50;
const APP_VIEWS = new Set(["main", "host", "connect", "lobby", "game"]);
const bridge = createBridge();

async function loadFragment(relativePath) {
    const url = new URL(relativePath, import.meta.url);
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Não foi possível carregar ${url.pathname}: HTTP ${response.status}`);
    }
    return response.text();
}

function normalizeRemoteScreen(screen) {
    const value = String(screen || "").toLowerCase();

    if (value === "game" || value === "partida") {
        return "game";
    }
    if (value === "lobby" || value === "sala") {
        return "lobby";
    }
    if (value === "host" || value === "menu_host" || value === "menu_hostear") {
        return "host";
    }
    if (value === "connect" || value === "menu_connect" || value === "menu_conectar") {
        return "connect";
    }
    return "main";
}

async function bootstrap() {
    const viewport = byId("viewport");
    const [menuMarkup, lobbyMarkup, gameMarkup] = await Promise.all([
        loadFragment("./menu/menu.html"),
        loadFragment("./lobby/lobby.html"),
        loadFragment("./game/game.html"),
    ]);

    viewport.innerHTML = `${menuMarkup}\n${lobbyMarkup}\n${gameMarkup}`;

    const disposeViewport = initializeViewport(viewport);
    const game = createGame({
        callBridge: bridge.call,
        viewport,
    });

    let currentView = "main";
    let worldRevision = -1;
    let lobbyWorldRevision = -1;
    let snapshotTimer = null;
    let pollingStarted = false;
    let disposed = false;
    let menu = null;
    let lobby = null;

    function setView(view) {
        if (!APP_VIEWS.has(view) || !menu) {
            return;
        }

        currentView = view;
        menu.show(view);
        lobby.show(view);
        game.setVisible(view === "game");
    }

    lobby = createLobby({
        callBridge: bridge.call,
        requestView: setView,
    });
    menu = createMenu({
        callBridge: bridge.call,
        requestView: setView,
    });
    setView("main");

    function applyRemoteScreen(screen) {
        const remoteView = normalizeRemoteScreen(screen);

        if (remoteView === "game") {
            setView("game");
        } else if (remoteView === "lobby") {
            setView("lobby");
        } else if (remoteView === "host" || remoteView === "connect") {
            setView(remoteView);
        } else if (currentView === "game") {
            setView("main");
        }
    }

    function applySnapshot(snapshot) {
        if (!snapshot || typeof snapshot !== "object") {
            return;
        }

        if (Object.prototype.hasOwnProperty.call(snapshot, "world_revision")) {
            if (snapshot.screen === "game") {
                worldRevision = snapshot.world_revision;
            }
        }
        if (snapshot.lobby && typeof snapshot.lobby === "object") {
            lobby.applySnapshot(snapshot.lobby);
            if (Object.prototype.hasOwnProperty.call(snapshot.lobby, "world_revision")) {
                lobbyWorldRevision = snapshot.lobby.world_revision;
            }
        } else if (snapshot.screen !== "game") {
            lobbyWorldRevision = -1;
        }

        menu.applySnapshot(snapshot);
        game.applySnapshot(snapshot);
        applyRemoteScreen(snapshot.screen);
    }

    async function pollSnapshot() {
        if (disposed || !bridge.isReady()) {
            return;
        }

        const snapshot = await bridge.call(
            "get_snapshot",
            worldRevision,
            lobbyWorldRevision,
        );
        if (disposed) {
            return;
        }
        applySnapshot(snapshot);
        snapshotTimer = window.setTimeout(pollSnapshot, SNAPSHOT_INTERVAL_MS);
    }

    function startPolling() {
        if (disposed || pollingStarted || !bridge.isReady()) {
            return;
        }
        pollingStarted = true;
        void pollSnapshot();
    }

    const stopWatchingBridge = bridge.onReady(startPolling);

    function dispose() {
        if (disposed) {
            return;
        }
        disposed = true;
        if (snapshotTimer !== null) {
            window.clearTimeout(snapshotTimer);
            snapshotTimer = null;
        }
        stopWatchingBridge();
        menu.dispose();
        lobby.dispose();
        game.dispose();
        disposeViewport();
        bridge.dispose();
    }

    window.addEventListener("pagehide", dispose, {once: true});
}

bootstrap().catch((error) => {
    bridge.dispose();
    console.error("Falha ao inicializar a interface do jogo.", error);
});
