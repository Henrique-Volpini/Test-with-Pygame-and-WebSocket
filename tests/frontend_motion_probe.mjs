import {spawn} from "node:child_process";
import {mkdir, mkdtemp, rm, writeFile} from "node:fs/promises";
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
            throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        }
        return result.result.value;
    }

    close() {
        this.socket.close();
    }
}

function bootstrapScript(reducedMotion) {
    return `(() => {
        // Advance presentation time without sleeping through entire game cycles.
        let clockOffset = 0;
        const originalNow = performance.now.bind(performance);
        const originalFrame = window.requestAnimationFrame.bind(window);
        performance.now = () => originalNow() + clockOffset;
        window.requestAnimationFrame = (callback) => originalFrame((time) => callback(time + clockOffset));
        window.__advanceUiClock = (milliseconds) => { clockOffset += milliseconds; };
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
    await session.call("Emulation.setDeviceMetricsOverride", {width: 1280, height: 720, deviceScaleFactor: 1, mobile: false});
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

async function auditExploration(session) {
    return session.evaluate(`(async () => {
        const pause = (ms = 160) => new Promise((done) => setTimeout(done, ms));
        const assert = (ok, message) => { if (!ok) throw new Error(message); };
        const byId = (id) => document.getElementById(id);
        const snapshot = window.__motionSnapshot;
        const owner = snapshot.player_id;
        snapshot.matrix = snapshot.matrix.map((row, y) => row.map((tile, x) => (
            x <= 4 && y <= 4 ? {tile: "grass", dono: null, territorio: owner}
                : x <= 5 && y <= 5 ? {tile: "grass", preview: true} : null
        )));
        snapshot.matrix[3][4].territorio = null;
        snapshot.matrix[3][3].territorio = "enemy";
        snapshot.troops[0] = {...snapshot.troops[0], kind: "pioneer", target: null, status: "idle", hp: 10, max_hp: 10};
        snapshot.army = {...snapshot.army, pioneer: 1, pioneer_cap: 8, land: 0};
        snapshot.exploration_orders = [];
        snapshot.command_buildings = [{
            x: 2, y: 2, type: "town_center", owner, is_mine: true, queue: [],
            can_recruit: true, unavailable_reason: null,
        }];
        snapshot.matrix[2][2] = {tile: "town_center", dono: owner, territorio: owner};
        snapshot.matrix[2][3] = {tile: "city", dono: owner, territorio: owner};
        snapshot.world_revision += 1;
        const calls = [];
        let acknowledgeExplore = null;
        window.pywebview.api.explore_tile = (unitId, x, y) => {
            calls.push({action: "explore", unitId, x, y});
            return new Promise((done) => { acknowledgeExplore = done; });
        };
        for (const [method, action] of [["claim_tile", "claim"], ["build_tile", "build"], ["recruit_troop", "recruit"], ["command_troop", "move"]]) {
            window.pywebview.api[method] = async (...args) => { calls.push({action, args}); return {ok: true}; };
        }
        await pause();
        const canvas = byId("world-canvas");
        const clickTile = (x, y, type = "pointerdown") => {
            const rect = byId("viewport").getBoundingClientRect();
            canvas.dispatchEvent(new PointerEvent(type, {
                button: type === "contextmenu" ? 2 : 0, bubbles: true,
                clientX: rect.left + ((x + 0.5) * 32 + 256) * rect.width / canvas.width,
                clientY: rect.top + ((y + 0.5) * 32 + 256) * rect.height / canvas.height,
            }));
        };
        assert(!byId("territory-legend").hidden, "Ajuda inicial deve aparecer brevemente.");
        window.__advanceUiClock(12500);
        await pause();
        assert(byId("territory-legend").hidden, "Ajuda deve desaparecer automaticamente.");
        byId("map-help-toggle").click();
        assert(!byId("territory-legend").hidden, "Ajuda deve poder reabrir.");
        byId("map-help-close").click();
        assert(byId("territory-legend").hidden, "Ajuda deve poder fechar.");
        const samplePixel = (x, y) => [...canvas.getContext("2d").getImageData(x * 32 + 259, y * 32 + 259, 1, 1).data];
        const fogPixel = samplePixel(6, 5);
        const previewPixel = samplePixel(5, 4);
        const knownPixel = samplePixel(4, 3);
        assert(fogPixel[0] === 20 && fogPixel[1] === 28 && fogPixel[2] === 40, "Tile distante deve ser opaco.");
        assert(previewPixel.join() !== fogPixel.join(), "Prévia precisa mostrar terreno sob a névoa.");
        assert(previewPixel.slice(0, 3).reduce((a, b) => a + b, 0) < knownPixel.slice(0, 3).reduce((a, b) => a + b, 0), "Prévia deve ser mais escura que terreno explorado.");
        clickTile(4, 4);
        assert(byId("troop-selection-title").textContent === "Pioneiro", "Tipo da unidade incorreto.");
        assert(byId("pioneer-explore-button").disabled, "Não explorar tile já conhecido.");
        byId("troop-selection-close").click();
        assert(byId("troop-selection").hidden, "Botão fechar deve encerrar seleção.");
        clickTile(4, 4);
        clickTile(2, 2);
        assert(byId("troop-selection").hidden && byId("build-menu").classList.contains("is-command"), "Clique no centro deve fechar pioneiro e abrir recrutamento.");
        clickTile(4, 4);
        clickTile(3, 2);
        assert(byId("troop-selection").hidden && byId("build-menu").classList.contains("is-open"), "Clique numa cidade deve fechar pioneiro.");
        clickTile(4, 4);
        clickTile(6, 4);
        assert(byId("pioneer-explore-button").disabled, "Não explorar fora de alcance.");
        clickTile(5, 4);
        assert(!byId("pioneer-explore-button").disabled, "Prévia adjacente deve ser explorável.");
        assert(byId("pioneer-claim-button").disabled, "Não reivindicar prévia.");
        assert(!byId("build-menu").classList.contains("is-open"), "Escolher alvo do pioneiro não deve abrir a bandeja de construção.");
        const beforeMove = calls.length;
        clickTile(5, 4, "contextmenu");
        assert(calls.length === beforeMove, "Não mover para prévia ainda oculta.");
        const button = byId("pioneer-explore-button");
        await pause(220);
        const box = button.getBoundingClientRect();
        const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
        assert(hit === button || button.contains(hit), "Botão explorar precisa receber cliques reais.");
        button.click();
        button.click();
        assert(calls.length === 1, "Não enviar duas ações durante confirmação.");
        clickTile(6, 4);
        acknowledgeExplore({ok: true});
        snapshot.exploration_orders = [{unit_id: snapshot.troops[0].id, x: 5, y: 4, remaining_ticks: 1, total_ticks: 1, waiting_for_start: true}];
        snapshot.troops[0].status = "exploring";
        snapshot.resources.gold -= 20;
        snapshot.world_revision += 1;
        await pause();
        assert(byId("pioneer-target").textContent.includes("(6, 4)"), "Confirmação deve preservar alvo mais recente.");
        assert(byId("troop-status").textContent.includes("Inicia em"), "Ordem aceita deve aguardar próximo ciclo.");
        window.__advanceUiClock(6000);
        await pause();
        assert(!byId("action-feedback").textContent.includes("confirmação demorou"), "Ordem aceita não deve expirar como pendência.");
        assert(snapshot.matrix[4][5].preview, "Aceitar ordem não revela tile.");
        const buildButton = document.querySelector('.build-button[data-tile="city"]');
        clickTile(3, 4);
        buildButton.click();
        clickTile(3, 4, "contextmenu");
        assert(calls.length === 1, "Pioneiro ocupado não pode construir ou mover.");
        byId("troop-selection-close").click();
        snapshot.exploration_orders[0].waiting_for_start = false;
        snapshot.tick_number += 1;
        snapshot.tick_remaining_ms = 10000;
        snapshot.world_revision += 1;
        await pause();
        clickTile(4, 4);
        assert(byId("troop-status").textContent.includes("Explorando (5, 4)"), "Exploração deve continuar com painel fechado.");
        assert(snapshot.matrix[4][5].preview, "Primeira borda apenas inicia ciclo completo.");
        assert(byId("pioneer-explore-button").disabled && byId("pioneer-claim-button").disabled, "Pioneiro continua ocupado por todo o ciclo.");
        snapshot.matrix[4][5] = {tile: "grass", dono: null, territorio: null};
        snapshot.matrix[4][6] = {tile: "small_forest", preview: true};
        snapshot.exploration_orders = [];
        snapshot.troops[0].status = "idle";
        snapshot.tick_number += 1;
        snapshot.tick_remaining_ms = 10000;
        snapshot.world_revision += 1;
        await pause();
        assert(byId("action-feedback").textContent.includes("Tile (5, 4) explorado"), "Conclusão deve informar o tile revelado.");
        clickTile(5, 4);
        assert(byId("pioneer-explore-button").disabled, "Tile revelado não pode ser explorado novamente.");
        assert(!byId("pioneer-claim-button").disabled, "Tile neutro explorado deve permitir reivindicação.");
        buildButton.click();
        assert(calls.length === 1, "Não construir em território neutro.");
        byId("pioneer-claim-button").click();
        assert(calls[1].action === "claim" && calls[1].args[1] === 5, "Alvo de reivindicação incorreto.");
        snapshot.matrix[4][5].territorio = owner;
        snapshot.resources.wood -= 30;
        snapshot.resources.food -= 10;
        snapshot.world_revision += 1;
        await pause();
        assert(byId("pioneer-claim-button").disabled, "Não reivindicar próprio território.");
        buildButton.click();
        assert(calls[2].action === "build" && calls[2].args[0] === 5, "Construir ao lado de pioneiro livre no território próprio.");
        clickTile(3, 3);
        assert(byId("pioneer-claim-button").disabled, "Não reivindicar território inimigo.");
        buildButton.click();
        assert(calls.length === 3, "Não construir no território inimigo.");
        clickTile(4, 4);
        buildButton.click();
        assert(calls.length === 3, "Pioneiro sobre o tile não conta como adjacente.");
        snapshot.last_action_error = {action: "explorar_tile", code: "out_of_range", message: "Fora do alcance do pioneiro.", revision: 1};
        await pause();
        assert(byId("action-feedback").textContent === "Fora do alcance do pioneiro.", "Erro do servidor deve aparecer em português.");
        snapshot.last_action_error = null;
        clickTile(2, 2);
        assert(byId("command-recruit-kind").textContent === "Pioneiro", "Centro urbano deve recrutar pioneiros.");
        assert(byId("command-recruit-cost").textContent === "60 ouro", "Custo do pioneiro incorreto.");
        byId("command-recruit-button").click();
        assert(calls[3].action === "recruit" && calls[3].args[0] === 2, "Recrutamento deve usar o centro selecionado.");
        await pause(300);
        const recruitPanel = byId("command-panel");
        assert(recruitPanel.scrollHeight <= recruitPanel.clientHeight + 1, "Painel de recrutamento deve caber em 1280×720.");
        // Capture a realistic new settlement, its terrain preview and the compact unit panel.
        snapshot.width = 50;
        snapshot.height = 36;
        snapshot.spawn_position = [25, 18];
        const terrain = (x, y) => x >= 28 ? "water" : (x + y) % 4 === 0 ? "small_forest" : "grass";
        snapshot.matrix = Array.from({length: 36}, (_, y) => Array.from({length: 50}, (_, x) => {
            const distance = Math.max(Math.abs(x - 25), Math.abs(y - 18));
            if (distance > 3) return null;
            if (distance > 2) return {tile: terrain(x, y), preview: true};
            return {tile: distance <= 1 ? x === 25 && y === 18 ? "town_center" : "city" : terrain(x, y), dono: distance <= 1 ? owner : null, territorio: distance <= 1 ? owner : null};
        }));
        snapshot.troops[0] = {...snapshot.troops[0], x: 27, y: 18};
        snapshot.command_buildings = [{...snapshot.command_buildings[0], x: 25, y: 18}];
        snapshot.world_revision += 1;
        await pause(3600);
        const rect = byId("viewport").getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        for (let i = 0; i < 15; i += 1) byId("game-screen").dispatchEvent(new WheelEvent("wheel", {deltaY: -100, clientX: centerX, clientY: centerY, bubbles: true, cancelable: true}));
        const clickRelative = (offsetX) => canvas.dispatchEvent(new PointerEvent("pointerdown", {button: 0, bubbles: true, clientX: centerX + offsetX * 32 * 2.5 * rect.width / canvas.width, clientY: centerY}));
        clickRelative(2);
        clickRelative(3);
        window.__advanceUiClock(13000);
        await pause(250);
        assert(!byId("troop-selection").hidden, "Painel deve aparecer na captura final.");
        assert(byId("troop-selection").scrollHeight <= byId("troop-selection").clientHeight + 1, "Painel pioneiro deve caber em 1280×720.");
        const finalPanel = byId("troop-selection").getBoundingClientRect();
        assert(finalPanel.bottom <= 720 && finalPanel.right <= 1280, "Painel não deve sair da tela.");
        return {fogPixel, previewPixel, knownPixel, calls, temporaryHelp: true, closeButtonAndBuildings: true, explorationFullCycle: true, previewNotExplored: true, viewport: [innerWidth, innerHeight]};
    })()`);
}

async function auditLobbyPreview(session) {
    return session.evaluate(`(async () => {
        const pause = () => new Promise((done) => setTimeout(done, 160));
        const assert = (ok, message) => { if (!ok) throw new Error(message); };
        window.__motionSnapshot = {
            screen: "lobby",
            lobby: {
                matrix: Array.from({length: 32}, () => Array(32).fill("grass")), width: 32, height: 32, size: 32, seed: 123, world_revision: 5,
                is_host: true, generating: false, code: "TEST123", status: "Sala pronta",
                map_params: {land: 60, mountains: 10, forests: 35},
                players: [{id: "probe-player", name: "Pioneiro", is_host: true, is_self: true}],
                player_count: 1,
            },
        };
        await pause();
        const byId = (id) => document.getElementById(id);
        assert(!byId("lobby-screen").hidden, "Lobby deve aparecer.");
        assert(byId("lobby-map-empty").hidden, "Lobby deve mostrar a prévia completa do mapa.");
        assert(!byId("lobby-start").disabled, "Mapa pronto deve permitir iniciar.");
        byId("lobby-seed-input").value = "124";
        byId("lobby-seed-input").dispatchEvent(new Event("input", {bubbles: true}));
        assert(byId("lobby-start").disabled, "Configuração alterada deve exigir aplicar.");
        const calls = [];
        window.pywebview.api.configure_lobby = async (seed, size, params) => {
            calls.push({seed, size, params});
            return {ok: true};
        };
        byId("lobby-apply").click();
        await Promise.resolve();
        await Promise.resolve();
        window.__motionSnapshot.lobby.seed = 124;
        window.__motionSnapshot.lobby.world_revision += 1;
        await pause();
        assert(calls.length === 1, "Aplicar configuração deve enviar uma ordem.");
        assert(!byId("lobby-start").disabled, "Nova revisão deve limpar configuração pendente.");
        assert(byId("lobby-map-empty").hidden, "Prévia deve continuar visível depois de configurar.");
        return {visibleMap: true, configurationAcknowledged: true, calls};
    })()`);
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
    const explorationSession = await openProbePage(false);
    try {
        results["exploration-territory-pioneer"] = await auditExploration(explorationSession);
        const screenshot = await explorationSession.call("Page.captureScreenshot", {format: "png"});
        await mkdir(resolve(projectRoot, "artifacts"), {recursive: true});
        await writeFile(resolve(projectRoot, "artifacts", "exploration-ui.png"), Buffer.from(screenshot.data, "base64"));
        results["lobby-map-preview"] = await auditLobbyPreview(explorationSession);
    } finally {
        explorationSession.close();
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
