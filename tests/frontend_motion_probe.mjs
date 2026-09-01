import {spawn} from "node:child_process";
import {mkdtemp, rm} from "node:fs/promises";
import {createServer} from "node:net";
import {tmpdir} from "node:os";
import {basename, dirname, resolve, sep} from "node:path";
import {fileURLToPath} from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

async function availablePort() {
    const probe = createServer();
    await new Promise((resolveListen, rejectListen) => {
        probe.once("error", rejectListen);
        probe.listen(0, "127.0.0.1", resolveListen);
    });
    const address = probe.address();
    await new Promise((resolveClose, rejectClose) => {
        probe.close((error) => error ? rejectClose(error) : resolveClose());
    });
    return address.port;
}

const webPort = await availablePort();
const debugPort = await availablePort();

function delay(milliseconds) {
    return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

async function waitForJson(url, timeoutMs = 8000) {
    const deadline = Date.now() + timeoutMs;
    let lastError = null;
    while (Date.now() < deadline) {
        try {
            const response = await fetch(url);
            if (response.ok) {
                return response.json();
            }
        } catch (error) {
            lastError = error;
        }
        await delay(80);
    }
    throw lastError || new Error(`Timeout ao acessar ${url}`);
}

async function waitForHttp(url, timeoutMs = 8000) {
    const deadline = Date.now() + timeoutMs;
    let lastError = null;
    while (Date.now() < deadline) {
        try {
            const response = await fetch(url);
            if (response.ok) {
                return;
            }
        } catch (error) {
            lastError = error;
        }
        await delay(80);
    }
    throw lastError || new Error(`Timeout ao acessar ${url}`);
}

async function removeTemporaryProfile(path) {
    const resolvedPath = resolve(path);
    const temporaryRoot = `${resolve(tmpdir())}${sep}`;
    if (
        !resolvedPath.startsWith(temporaryRoot) ||
        !basename(resolvedPath).startsWith("tcc-motion-probe-")
    ) {
        throw new Error(`Perfil temporário fora do diretório esperado: ${resolvedPath}`);
    }
    for (let attempt = 0; attempt < 12; attempt += 1) {
        try {
            await rm(resolvedPath, {recursive: true, force: true});
            return;
        } catch (error) {
            if (!new Set(["EBUSY", "EPERM", "ENOTEMPTY"]).has(error.code)) {
                throw error;
            }
            await delay(150);
        }
    }
}

class CdpSession {
    constructor(url) {
        this.socket = new WebSocket(url);
        this.nextId = 1;
        this.pending = new Map();
    }

    async open() {
        await new Promise((resolveOpen, rejectOpen) => {
            this.socket.addEventListener("open", resolveOpen, {once: true});
            this.socket.addEventListener("error", rejectOpen, {once: true});
        });
        this.socket.addEventListener("message", (event) => {
            const message = JSON.parse(event.data);
            if (!message.id || !this.pending.has(message.id)) {
                return;
            }
            const {resolveCall, rejectCall} = this.pending.get(message.id);
            this.pending.delete(message.id);
            if (message.error) {
                rejectCall(new Error(message.error.message));
            } else {
                resolveCall(message.result);
            }
        });
    }

    call(method, params = {}) {
        const id = this.nextId;
        this.nextId += 1;
        return new Promise((resolveCall, rejectCall) => {
            this.pending.set(id, {resolveCall, rejectCall});
            this.socket.send(JSON.stringify({id, method, params}));
        });
    }

    async evaluate(expression) {
        const result = await this.call("Runtime.evaluate", {
            expression,
            awaitPromise: true,
            returnByValue: true,
        });
        if (result.exceptionDetails) {
            throw new Error(result.exceptionDetails.text);
        }
        return result.result.value;
    }

    close() {
        this.socket.close();
    }
}

function bootstrapScript(reducedMotion) {
    return `(() => {
        const originalMatchMedia = window.matchMedia.bind(window);
        window.matchMedia = (query) => query.includes("prefers-reduced-motion")
            ? {
                matches: ${reducedMotion},
                media: query,
                onchange: null,
                addEventListener() {},
                removeEventListener() {},
                addListener() {},
                removeListener() {},
                dispatchEvent() { return true; },
            }
            : originalMatchMedia(query);

        const width = 24;
        const height = 16;
        const matrix = Array.from({length: height}, () => Array(width).fill("grass"));
        matrix[8][8] = "guard_house";
        window.__motionSnapshot = {
            screen: "game",
            world_revision: 1,
            width,
            height,
            matrix,
            resources: {gold: 500, wood: 500, food: 500},
            spawn_position: [4, 4],
            player_id: "probe-player",
            troops: [{
                id: "troop-probe",
                owner: "probe-player",
                is_mine: true,
                kind: "land",
                x: 4,
                y: 4,
                hp: 12,
                max_hp: 12,
                target: [20, 4],
                status: "moving",
            }],
            command_buildings: [{
                x: 8,
                y: 8,
                type: "guard_house",
                owner: "probe-player",
                is_mine: true,
                queue: [{
                    id: "recruit-probe",
                    unit_kind: "land",
                    remaining_ticks: 2,
                    total_ticks: 2,
                    cost_gold: 75,
                    waiting_for_start: true,
                }],
                can_recruit: true,
                unavailable_reason: null,
            }],
            army: {land: 1, boat: 0, land_cap: 24, boat_cap: 12},
            tick_interval_ms: 10000,
            tick_remaining_ms: 8000,
            tick_number: 3,
        };
        window.pywebview = {
            api: {
                async get_snapshot() {
                    return structuredClone(window.__motionSnapshot);
                },
            },
        };
        window.__setMotionDestination = (x) => {
            window.__motionSnapshot = structuredClone(window.__motionSnapshot);
            window.__motionSnapshot.world_revision += 1;
            window.__motionSnapshot.troops[0].x = x;
        };

        const originalClearRect = CanvasRenderingContext2D.prototype.clearRect;
        CanvasRenderingContext2D.prototype.clearRect = function(...args) {
            if (this.canvas && this.canvas.id === "world-canvas") {
                window.__troopRects = [];
                window.__motionTrailStrokes = 0;
            }
            return originalClearRect.apply(this, args);
        };
        const originalFillRect = CanvasRenderingContext2D.prototype.fillRect;
        CanvasRenderingContext2D.prototype.fillRect = function(x, y, width, height) {
            const color = String(this.fillStyle).toLowerCase().replaceAll(" ", "");
            if (
                this.canvas && this.canvas.id === "world-canvas" &&
                (color === "#d9ad55" || color === "rgb(217,173,85)")
            ) {
                window.__troopRects ||= [];
                window.__troopRects.push({x, y, width, height});
            }
            return originalFillRect.call(this, x, y, width, height);
        };
        const originalStroke = CanvasRenderingContext2D.prototype.stroke;
        CanvasRenderingContext2D.prototype.stroke = function(...args) {
            if (
                this.canvas && this.canvas.id === "world-canvas" &&
                String(this.strokeStyle).toLowerCase() === "#ffe29a"
            ) {
                window.__motionTrailStrokes = (window.__motionTrailStrokes || 0) + 1;
            }
            return originalStroke.apply(this, args);
        };
    })();`;
}

async function openProbePage(reducedMotion) {
    const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, {
        method: "PUT",
    }).then((response) => response.json());
    const session = new CdpSession(target.webSocketDebuggerUrl);
    await session.open();
    await session.call("Page.enable");
    await session.call("Runtime.enable");
    await session.call("Page.addScriptToEvaluateOnNewDocument", {
        source: bootstrapScript(reducedMotion),
    });
    await session.call("Page.navigate", {
        url: `http://127.0.0.1:${webPort}/Client/index.html`,
    });

    const deadline = Date.now() + 8000;
    while (Date.now() < deadline) {
        const ready = await session.evaluate(`Boolean(
            document.querySelector("#world-canvas") &&
            window.__troopRects &&
            window.__troopRects.length
        )`);
        if (ready) {
            return session;
        }
        await delay(50);
    }
    session.close();
    throw new Error("Canvas da partida não ficou pronto.");
}

async function sampleMotion(session, destinationX, sampleDurationMs) {
    return session.evaluate(`(async () => {
        const centroid = () => {
            const rectangles = window.__troopRects || [];
            if (!rectangles.length) return null;
            return rectangles.reduce(
                (sum, rectangle) => sum + rectangle.x + rectangle.width / 2,
                0,
            ) / rectangles.length;
        };
        const baseline = centroid();
        window.__setMotionDestination(${destinationX});
        const startDeadline = performance.now() + 1200;
        while (!window.__motionTrailStrokes && performance.now() < startDeadline) {
            await new Promise((resolveDelay) => setTimeout(resolveDelay, 10));
        }
        const first = centroid();
        const samples = [];
        let sawTrail = Boolean(window.__motionTrailStrokes);
        const startedAt = performance.now();
        while (performance.now() - startedAt < ${sampleDurationMs}) {
            samples.push(centroid());
            sawTrail ||= Boolean(window.__motionTrailStrokes);
            await new Promise((resolveDelay) => setTimeout(resolveDelay, 50));
        }
        return {baseline, first, samples: samples.filter(Number.isFinite), sawTrail};
    })()`);
}

function assertMovement(label, result, tileDistance) {
    if (!Number.isFinite(result.baseline) || !Number.isFinite(result.first)) {
        throw new Error(`${label}: a tropa não foi detectada no canvas.`);
    }
    const expectedDelta = tileDistance * 32;
    const delta = result.samples.map((x) => x - result.baseline);
    const finalDelta = delta.at(-1);
    const sawIntermediate = delta.some((value) => (
        value > Math.min(12, expectedDelta * 0.18) &&
        value < expectedDelta - Math.min(12, expectedDelta * 0.18)
    ));
    if (Math.abs(result.first - result.baseline) > 12) {
        throw new Error(`${label}: primeiro frame já saltou ${result.first - result.baseline}px.`);
    }
    if (!sawIntermediate) {
        throw new Error(`${label}: não houve posição intermediária entre snapshots.`);
    }
    if (Math.abs(finalDelta - expectedDelta) > 8) {
        throw new Error(`${label}: terminou em ${finalDelta}px; esperado ${expectedDelta}px.`);
    }
    if (!result.sawTrail) {
        throw new Error(`${label}: deslocamento não desenhou trilha visual.`);
    }
    return {
        firstDelta: Math.round((result.first - result.baseline) * 10) / 10,
        intermediateFrames: delta.filter((value) => value > 8 && value < expectedDelta - 8).length,
        finalDelta: Math.round(finalDelta * 10) / 10,
        sawTrail: result.sawTrail,
    };
}

async function auditQueueTiming(session) {
    const result = await session.evaluate(`(async () => {
        const delay = (milliseconds) => new Promise(
            (resolveDelay) => setTimeout(resolveDelay, milliseconds),
        );
        const canvas = document.querySelector("#world-canvas");
        const viewport = document.querySelector("#viewport");
        const rect = viewport.getBoundingClientRect();
        const logicalX = (8.5 * 32) + 256;
        const logicalY = (8.5 * 32) + 256;
        canvas.dispatchEvent(new PointerEvent("pointerdown", {
            button: 0,
            bubbles: true,
            clientX: rect.left + logicalX * rect.width / canvas.width,
            clientY: rect.top + logicalY * rect.height / canvas.height,
        }));
        await delay(120);

        const row = () => document.querySelector(".command-queue-slot:not(.is-empty)");
        const time = () => row()?.querySelector(".command-queue-time");
        const progress = () => Number.parseFloat(
            row()?.style.getPropertyValue("--queue-progress") || "-1",
        );
        const waitingText = time()?.textContent || "";
        const waitingProgress = progress();
        await delay(280);
        const waitingProgressLater = progress();
        const recruitTime = document.querySelector("#command-recruit-time")?.textContent || "";
        const recruitMessage = document.querySelector("#command-recruit-message")?.textContent || "";

        window.__motionSnapshot = structuredClone(window.__motionSnapshot);
        window.__motionSnapshot.world_revision += 1;
        window.__motionSnapshot.tick_remaining_ms = 10000;
        window.__motionSnapshot.tick_number += 1;
        window.__motionSnapshot.command_buildings[0].queue[0].waiting_for_start = false;
        const activeDeadline = performance.now() + 1200;
        while (!time()?.textContent.includes("2 ticks restantes") && performance.now() < activeDeadline) {
            await delay(20);
        }
        const activeText = time()?.textContent || "";
        const activeProgress = progress();

        window.__motionSnapshot = structuredClone(window.__motionSnapshot);
        window.__motionSnapshot.world_revision += 1;
        window.__motionSnapshot.tick_remaining_ms = 10000;
        window.__motionSnapshot.tick_number += 1;
        window.__motionSnapshot.command_buildings[0].queue[0].remaining_ticks = 1;
        const advancedDeadline = performance.now() + 1200;
        while (progress() !== 0.5 && performance.now() < advancedDeadline) {
            await delay(20);
        }
        return {
            waitingText,
            waitingProgress,
            waitingProgressLater,
            recruitTime,
            recruitMessage,
            activeText,
            activeProgress,
            advancedProgress: progress(),
            timeFits: time() ? time().scrollHeight <= time().clientHeight + 1 : false,
        };
    })()`);

    if (
        !result.waitingText.includes("Aguardando próximo ciclo") ||
        !result.waitingText.includes("Produção: 2 ticks")
    ) {
        throw new Error(`fila: estado inicial incorreto: ${result.waitingText}`);
    }
    if (result.waitingProgress !== 0 || result.waitingProgressLater !== 0) {
        throw new Error("fila: houve progresso fracionário antes do início.");
    }
    if (
        !result.activeText.includes("2 ticks restantes") ||
        !result.activeText.includes("próximo avanço em") ||
        result.activeProgress !== 0 ||
        result.advancedProgress !== 0.5
    ) {
        throw new Error(`fila: avanço em degraus inválido: ${JSON.stringify(result)}`);
    }
    if (
        result.recruitTime !== "2 ticks completos · 20 s" ||
        !result.recruitMessage.includes("ciclo global atual terminar") ||
        !result.timeFits
    ) {
        throw new Error(`fila: informação ou layout inválido: ${JSON.stringify(result)}`);
    }
    return result;
}

const temporaryProfile = await mkdtemp(resolve(tmpdir(), "tcc-motion-probe-"));
const server = spawn("python", ["-m", "http.server", String(webPort), "--bind", "127.0.0.1"], {
    cwd: projectRoot,
    stdio: "ignore",
});
const browser = spawn(edgePath, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${temporaryProfile}`,
    "about:blank",
], {stdio: "ignore"});
let browserSession = null;

try {
    const version = await waitForJson(`http://127.0.0.1:${debugPort}/json/version`);
    browserSession = new CdpSession(version.webSocketDebuggerUrl);
    await browserSession.open();
    await waitForHttp(`http://127.0.0.1:${webPort}/Client/index.html`);
    const results = {};
    for (const scenario of [
        {label: "normal-3-tiles", reduced: false, destination: 7, duration: 3700},
        {label: "reduced-3-tiles", reduced: true, destination: 7, duration: 1300},
        {label: "catchup-6-tiles", reduced: false, destination: 10, duration: 3700},
    ]) {
        const session = await openProbePage(scenario.reduced);
        try {
            const sample = await sampleMotion(session, scenario.destination, scenario.duration);
            results[scenario.label] = assertMovement(
                scenario.label,
                sample,
                scenario.destination - 4,
            );
        } finally {
            session.close();
        }
    }
    const queueSession = await openProbePage(false);
    try {
        results["global-tick-queue"] = await auditQueueTiming(queueSession);
    } finally {
        queueSession.close();
    }
    console.log(JSON.stringify(results, null, 2));
} finally {
    if (browserSession) {
        await browserSession.call("Browser.close").catch(() => {});
        browserSession.close();
    } else {
        browser.kill();
    }
    server.kill();
    await delay(350);
    await removeTemporaryProfile(temporaryProfile);
}
