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
const TROOP_HIT_RADIUS = 14;
const TROOP_EFFECT_LIMIT = 80;
const TROOP_EFFECT_DURATION_MS = {
    spawn: 520,
    damage: 380,
    death: 650,
};
const TROOP_MOTION_MIN_MS = 1800;
const TROOP_MOTION_MAX_MS = 3200;
const TROOP_MOTION_REDUCED_MIN_MS = 520;
const TROOP_MOTION_REDUCED_MAX_MS = 820;
const COMMAND_QUEUE_LIMIT = 5;
const RECRUIT_SPECS = {
    guard_house: {kind: "land", costGold: 75, totalTicks: 2},
    dock: {kind: "boat", costGold: 120, totalTicks: 3},
};
const LAND_FORMATION = [
    [-6, -5],
    [0, -7],
    [6, -5],
    [-8, 2],
    [0, 0],
    [8, 2],
    [-4, 7],
    [4, 7],
];
const TROOP_STACK_OFFSETS = [
    [-5, -5],
    [5, -5],
    [-5, 5],
    [5, 5],
];
const RESOURCE_NAMES = ["gold", "wood", "food"];

export function createGame({callBridge, viewport}) {
    const gameScreen = byId("game-screen");
    const buildMenu = byId("build-menu");
    const buildPanel = byId("build-panel");
    const buildPanelToggle = byId("build-panel-toggle");
    const buildPanelToggleLabel = byId("build-panel-toggle-label");
    const commandPanel = byId("command-panel");
    const commandPanelBack = byId("command-panel-back");
    const commandBuildingKicker = byId("command-building-kicker");
    const commandBuildingTitle = byId("command-building-title");
    const commandBuildingOwner = byId("command-building-owner");
    const commandBuildingIcon = byId("command-building-icon");
    const armyLandValue = byId("army-land-value");
    const armyBoatValue = byId("army-boat-value");
    const commandArmySummary = byId("command-army-summary");
    const commandQueue = byId("command-queue");
    const commandQueueCount = byId("command-queue-count");
    const commandCenterSummary = byId("command-center-summary");
    const commandRecruitSection = byId("command-recruit-section");
    const commandRecruitKind = byId("command-recruit-kind");
    const commandRecruitCost = byId("command-recruit-cost");
    const commandRecruitTime = byId("command-recruit-time");
    const commandRecruitButton = byId("command-recruit-button");
    const commandRecruitMessage = byId("command-recruit-message");
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
    const troopSelection = byId("troop-selection");
    const troopSelectionTitle = byId("troop-selection-title");
    const troopHealth = byId("troop-health");
    const troopHealthValue = byId("troop-health-value");
    const troopStatus = byId("troop-status");
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
    let commandQueueSignature = null;
    let commandQueueRows = new Map();
    const reducedMotionQuery = window.matchMedia
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;

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
        panelMode: "build",
        commandBuildings: [],
        selectedCommandBuildingKey: null,
        army: {
            land: 0,
            boat: 0,
            landCap: 24,
            boatCap: 12,
        },
        pendingRecruit: null,
        commandFeedback: null,
        lastActionErrorRevision: null,
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
        playerId: null,
        troops: [],
        troopOffsets: new Map(),
        troopMotions: new Map(),
        hasTroopSnapshot: false,
        selectedTroopId: null,
        pendingTroopTarget: null,
        troopEffects: [],
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
        guard_house: byId("asset-guard-house"),
        dock: byId("asset-dock"),
    };
    const selectedImage = byId("asset-selected");

    function listen(target, type, listener, options) {
        target.addEventListener(type, listener, options);
        disposers.push(() => target.removeEventListener(type, listener, options));
    }

    function prefersReducedMotion() {
        return Boolean(reducedMotionQuery?.matches);
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
        const commandOpen = (
            panelOpen &&
            state.panelMode === "command" &&
            Boolean(selectedCommandBuilding())
        );
        const catalogOpen = panelOpen && !commandOpen;

        // O contêiner permanece montado durante a partida para que o CSS possa
        // animá-lo até a borda inferior; somente a aba fica exposta ao fechar.
        buildMenu.hidden = !state.visible;
        buildMenu.classList.toggle("is-open", panelOpen);
        buildMenu.classList.toggle("is-command", commandOpen);
        buildMenu.setAttribute("aria-hidden", String(!state.visible));
        buildPanel.setAttribute("aria-hidden", String(!catalogOpen));
        buildPanel.inert = !catalogOpen;
        commandPanel.setAttribute("aria-hidden", String(!commandOpen));
        commandPanel.inert = !commandOpen;
        buildPanelToggle.setAttribute("aria-expanded", String(panelOpen));
        buildPanelToggle.setAttribute(
            "aria-controls",
            commandOpen ? "command-panel" : "build-panel",
        );
        buildPanelToggleLabel.textContent = commandOpen
            ? commandBuildingName(selectedCommandBuilding()?.type)
            : "Construções";
        buildPanelToggle.setAttribute(
            "aria-label",
            panelOpen ? "Fechar painel inferior" : "Abrir painel inferior",
        );

        if (!catalogOpen) {
            hideBuildInfo();
        }
    }

    function setVisible(visible) {
        state.visible = Boolean(visible);
        gameScreen.hidden = !state.visible;
        if (!state.visible) {
            state.heldKeys.clear();
            state.buildOpen = false;
            state.selectedTroopId = null;
            state.pendingTroopTarget = null;
            state.troopEffects = [];
            state.troopMotions.clear();
            state.hasTroopSnapshot = false;
            state.panelMode = "build";
            state.selectedCommandBuildingKey = null;
            state.pendingRecruit = null;
            state.commandFeedback = null;
            state.lastActionErrorRevision = null;
        }
        setBuildVisibility();
        updateTroopSelectionUi();
    }

    function setInteractionLocked(locked) {
        state.interactionLocked = Boolean(locked);
        if (state.interactionLocked) {
            state.heldKeys.clear();
            hideBuildInfo();
        }
        renderCommandPanel();
    }

    function updateResourceHud() {
        byId("gold-value").textContent = String(state.resources.gold);
        byId("wood-value").textContent = String(state.resources.wood);
        byId("food-value").textContent = String(state.resources.food);
        if (inspectedBuildButton && buildInfo.classList.contains("is-visible")) {
            refreshBuildInfoCosts(inspectedBuildButton);
        }
    }

    function commandBuildingKey(x, y) {
        return `${Math.trunc(x)},${Math.trunc(y)}`;
    }

    function commandBuildingName(type) {
        return {
            town_center: "Centro urbano",
            guard_house: "Casa da Guarda",
            dock: "Doca",
        }[type] || "Edifício";
    }

    function commandBuildingKickerText(type) {
        return {
            town_center: "CAPITAL DO DOMÍNIO",
            guard_house: "COMANDO TERRESTRE",
            dock: "COMANDO NAVAL",
        }[type] || "EDIFÍCIO DE COMANDO";
    }

    function normalizeQueueItem(rawItem) {
        if (!rawItem || typeof rawItem !== "object" || rawItem.id == null) {
            return null;
        }
        const totalTicks = Math.max(1, Math.trunc(Number(rawItem.total_ticks) || 1));
        return {
            id: String(rawItem.id),
            unitKind: rawItem.unit_kind === "boat" ? "boat" : "land",
            remainingTicks: Math.max(
                0,
                Math.min(totalTicks, Math.trunc(Number(rawItem.remaining_ticks) || 0)),
            ),
            totalTicks,
            costGold: Math.max(0, Math.trunc(Number(rawItem.cost_gold) || 0)),
            waitingForStart: Boolean(rawItem.waiting_for_start),
        };
    }

    function normalizeCommandBuilding(rawBuilding) {
        if (!rawBuilding || typeof rawBuilding !== "object") {
            return null;
        }
        const x = Number(rawBuilding.x);
        const y = Number(rawBuilding.y);
        const type = rawBuilding.type;
        if (
            !Number.isInteger(x) ||
            !Number.isInteger(y) ||
            !["town_center", "guard_house", "dock"].includes(type)
        ) {
            return null;
        }
        const queue = Array.isArray(rawBuilding.queue)
            ? rawBuilding.queue.map(normalizeQueueItem).filter(Boolean).slice(0, COMMAND_QUEUE_LIMIT)
            : [];
        return {
            x,
            y,
            key: commandBuildingKey(x, y),
            type,
            owner: rawBuilding.owner == null ? "" : String(rawBuilding.owner),
            isMine: Boolean(rawBuilding.is_mine),
            queue,
            canRecruit: Boolean(rawBuilding.can_recruit),
            unavailableReason: typeof rawBuilding.unavailable_reason === "string"
                ? rawBuilding.unavailable_reason
                : null,
        };
    }

    function normalizeArmy(rawArmy) {
        if (!rawArmy || typeof rawArmy !== "object") {
            return state.army;
        }
        const count = (value, fallback) => {
            const number = Number(value);
            return Number.isInteger(number) && number >= 0 ? number : fallback;
        };
        return {
            land: count(rawArmy.land, state.army.land),
            boat: count(rawArmy.boat, state.army.boat),
            landCap: count(rawArmy.land_cap, state.army.landCap),
            boatCap: count(rawArmy.boat_cap, state.army.boatCap),
        };
    }

    function selectedCommandBuilding() {
        if (state.selectedCommandBuildingKey === null) {
            return null;
        }
        return state.commandBuildings.find((building) => (
            building.key === state.selectedCommandBuildingKey
        )) || null;
    }

    function commandBuildingAt(x, y) {
        const key = commandBuildingKey(x, y);
        const exact = state.commandBuildings.find((building) => building.key === key);
        if (exact) {
            return exact;
        }
        // O centro ocupa 3x3; o backend identifica a estrutura por uma única
        // coordenada, mas qualquer um de seus nove tiles deve abrir o painel.
        if (tileName(state.matrix?.[y]?.[x]) !== "town_center") {
            return null;
        }
        return state.commandBuildings.find((building) => (
            building.type === "town_center" &&
            Math.abs(building.x - x) <= 2 &&
            Math.abs(building.y - y) <= 2
        )) || null;
    }

    function queueIdSignature(building) {
        return building?.queue.map((item) => item.id).join("|") || "";
    }

    function unavailableReasonText(reason, building) {
        const spec = RECRUIT_SPECS[building?.type];
        return {
            not_owner: "Este edifício pertence a outro jogador.",
            not_recruitment_building: "O centro urbano não recruta tropas.",
            queue_full: "A fila já possui 5 ordens.",
            army_cap_reached: spec?.kind === "boat"
                ? "Limite naval atingido."
                : "Limite terrestre atingido.",
            insufficient_gold: "Ouro insuficiente para esta ordem.",
        }[reason] || "Recrutamento indisponível neste momento.";
    }

    function rebuildCommandQueue(building) {
        const signature = building
            ? `${building.key}:${building.queue.map((item) => (
                `${item.id}:${item.unitKind}:${item.totalTicks}:${item.costGold}`
            )).join("|")}`
            : "";
        if (signature === commandQueueSignature) {
            return;
        }

        commandQueueSignature = signature;
        commandQueueRows = new Map();
        commandQueue.replaceChildren();
        for (let index = 0; index < COMMAND_QUEUE_LIMIT; index += 1) {
            const item = building?.queue[index] || null;
            const slot = document.createElement("li");
            slot.className = `command-queue-slot${item ? "" : " is-empty"}`;
            if (!item) {
                slot.textContent = `VAGA ${index + 1}`;
            } else {
                const position = document.createElement("span");
                position.className = "command-queue-position";
                position.textContent = `ORDEM ${index + 1}`;
                const unit = document.createElement("strong");
                unit.className = "command-queue-unit";
                unit.textContent = item.unitKind === "boat" ? "Embarcação" : "Tropa terrestre";
                const time = document.createElement("span");
                time.className = "command-queue-time";
                const progress = document.createElement("span");
                progress.className = "command-queue-progress";
                const progressFill = document.createElement("span");
                progress.append(progressFill);
                slot.append(position, unit, time, progress);
                commandQueueRows.set(item.id, {root: slot, time});
            }
            commandQueue.append(slot);
        }
    }

    function updateCommandQueueTiming(now = performance.now()) {
        const building = selectedCommandBuilding();
        if (
            state.commandFeedback &&
            now >= state.commandFeedback.expiresAt
        ) {
            state.commandFeedback = null;
            renderCommandPanel();
        }
        if (!building || building.type === "town_center") {
            return;
        }

        if (
            state.pendingRecruit &&
            now - state.pendingRecruit.sentAt > 2500
        ) {
            state.pendingRecruit = null;
            renderCommandPanel();
        }

        const elapsedMs = Math.max(0, now - state.tickSyncedAtMs);
        const tickRemainingMs = Math.max(
            0,
            state.tickRemainingAtSyncMs - elapsedMs,
        );
        const blocked = building.queue[0]?.remainingTicks === 0;
        let completionBoundaries = building.queue[0]?.waitingForStart ? 1 : 0;
        const secondsUntilBoundary = Math.max(0, Math.ceil(tickRemainingMs / 100) / 10)
            .toFixed(1)
            .replace(".", ",");

        building.queue.forEach((item, index) => {
            const row = commandQueueRows.get(item.id);
            if (!row) {
                return;
            }
            completionBoundaries += item.remainingTicks;
            const progress = Math.max(0, Math.min(
                1,
                (item.totalTicks - item.remainingTicks) / item.totalTicks,
            ));
            row.root.style.setProperty("--queue-progress", String(progress));
            row.root.classList.toggle("is-blocked", blocked);
            row.root.classList.toggle("is-waiting", index === 0 && item.waitingForStart);
            row.root.classList.toggle(
                "is-active",
                index === 0 && !item.waitingForStart && item.remainingTicks > 0,
            );

            if (blocked) {
                row.time.textContent = index === 0
                    ? "Aguardando espaço"
                    : `Fila bloqueada · Produção: ${item.totalTicks} ticks`;
                return;
            }
            if (index === 0 && item.waitingForStart) {
                row.time.textContent = `Aguardando próximo ciclo (${secondsUntilBoundary} s) · Produção: ${item.totalTicks} ticks`;
                return;
            }
            if (index === 0) {
                const label = item.remainingTicks === 1 ? "tick restante" : "ticks restantes";
                row.time.textContent = `${item.remainingTicks} ${label} · próximo avanço em ${secondsUntilBoundary} s`;
                return;
            }
            const boundaryLabel = completionBoundaries === 1 ? "ciclo" : "ciclos";
            row.time.textContent = `Na fila · Produção: ${item.totalTicks} ticks · ~${completionBoundaries} ${boundaryLabel}`;
        });
    }

    function renderCommandPanel() {
        const building = selectedCommandBuilding();
        if (!building) {
            commandQueueSignature = null;
            return;
        }

        const spec = RECRUIT_SPECS[building.type] || null;
        const isTownCenter = building.type === "town_center";
        const isPending = Boolean(
            state.pendingRecruit &&
            state.pendingRecruit.buildingKey === building.key &&
            performance.now() - state.pendingRecruit.sentAt <= 2500
        );
        const feedback = state.commandFeedback?.buildingKey === building.key
            ? state.commandFeedback
            : null;
        commandPanel.classList.toggle("is-enemy", !building.isMine);
        commandPanel.classList.toggle("is-town-center", isTownCenter);
        commandBuildingKicker.textContent = commandBuildingKickerText(building.type);
        commandBuildingTitle.textContent = commandBuildingName(building.type);
        commandBuildingOwner.textContent = building.isMine
            ? "Seu domínio"
            : `Domínio inimigo${building.owner ? ` · ${building.owner}` : ""}`;
        if (tileImages[building.type]) {
            commandBuildingIcon.src = tileImages[building.type].src;
        }
        armyLandValue.textContent = `${state.army.land} / ${state.army.landCap}`;
        armyBoatValue.textContent = `${state.army.boat} / ${state.army.boatCap}`;
        commandArmySummary.hidden = !building.isMine;
        commandCenterSummary.hidden = !isTownCenter;
        commandQueue.hidden = isTownCenter;
        commandQueueCount.hidden = isTownCenter;
        commandRecruitSection.hidden = isTownCenter;
        byId("command-queue-title").textContent = isTownCenter
            ? "Resumo do exército"
            : "Fila de recrutamento";
        commandQueueCount.textContent = `${building.queue.length} / ${COMMAND_QUEUE_LIMIT}`;
        rebuildCommandQueue(building);

        if (!spec) {
            updateCommandQueueTiming();
            return;
        }

        const kindName = spec.kind === "boat" ? "Embarcação" : "Tropa terrestre";
        const intervalSeconds = Math.round(state.tickIntervalMs / 1000);
        commandRecruitKind.textContent = kindName;
        commandRecruitCost.textContent = `${spec.costGold} ouro`;
        commandRecruitTime.textContent = `${spec.totalTicks} ticks completos · ${spec.totalTicks * intervalSeconds} s`;

        let reason = building.unavailableReason;
        if (!reason && !building.isMine) {
            reason = "not_owner";
        } else if (!reason && building.queue.length >= COMMAND_QUEUE_LIMIT) {
            reason = "queue_full";
        } else if (!reason && Number(state.resources.gold) < spec.costGold) {
            reason = "insufficient_gold";
        } else if (!reason && !building.canRecruit) {
            reason = "not_recruitment_building";
        }
        commandRecruitSection.classList.toggle(
            "is-unavailable",
            Boolean(reason || feedback),
        );
        commandRecruitButton.classList.toggle("is-pending", isPending);
        commandRecruitButton.disabled = Boolean(reason) || isPending || state.interactionLocked;
        commandRecruitButton.textContent = isPending
            ? "Enviando ordem…"
            : spec.kind === "boat" ? "Construir embarcação" : "Treinar tropa";
        commandRecruitMessage.textContent = feedback
            ? feedback.message
            : isPending
            ? "Aguardando confirmação do próximo estado."
            : reason
            ? unavailableReasonText(reason, building)
            : `Começa quando o ciclo global atual terminar; leva ${spec.totalTicks} ticks completos.`;
        updateCommandQueueTiming();
    }

    function applyActionErrorSnapshot(snapshot) {
        const error = snapshot.last_action_error;
        if (
            !error ||
            typeof error !== "object" ||
            error.action !== "recrutar_tropa" ||
            error.revision == null ||
            error.revision === state.lastActionErrorRevision
        ) {
            return;
        }
        state.lastActionErrorRevision = error.revision;
        const pendingBuildingKey = state.pendingRecruit?.buildingKey || null;
        state.pendingRecruit = null;
        const building = selectedCommandBuilding();
        if (!pendingBuildingKey || !building || building.key !== pendingBuildingKey) {
            return;
        }
        const knownCodes = new Set([
            "not_owner",
            "not_recruitment_building",
            "queue_full",
            "army_cap_reached",
            "insufficient_gold",
        ]);
        const fallbackMessage = typeof error.message === "string" && error.message.trim()
            ? error.message.trim()
            : "A ordem de recrutamento foi recusada.";
        state.commandFeedback = {
            buildingKey: building.key,
            message: knownCodes.has(error.code)
                ? unavailableReasonText(error.code, building)
                : fallbackMessage,
            expiresAt: performance.now() + 4000,
        };
    }

    function applyCommandSnapshot(snapshot) {
        if (snapshot.army && typeof snapshot.army === "object") {
            state.army = normalizeArmy(snapshot.army);
        }
        if (Array.isArray(snapshot.command_buildings)) {
            state.commandBuildings = snapshot.command_buildings
                .map(normalizeCommandBuilding)
                .filter(Boolean);
        }

        const building = selectedCommandBuilding();
        if (!building && state.selectedCommandBuildingKey !== null) {
            state.panelMode = "build";
            state.selectedCommandBuildingKey = null;
            state.pendingRecruit = null;
            state.commandFeedback = null;
        } else if (state.pendingRecruit && building) {
            const changedQueue = queueIdSignature(building) !== state.pendingRecruit.baselineQueue;
            const spentGold = Number(state.resources.gold) < state.pendingRecruit.baselineGold;
            if (changedQueue || spentGold) {
                state.pendingRecruit = null;
            }
        }
        applyActionErrorSnapshot(snapshot);
        renderCommandPanel();
        setBuildVisibility();
    }

    function returnToBuildPanel() {
        state.panelMode = "build";
        state.selectedCommandBuildingKey = null;
        state.pendingRecruit = null;
        state.commandFeedback = null;
        state.buildOpen = true;
        setBuildVisibility();
    }

    function selectCommandBuilding(building) {
        clearTroopSelection();
        state.selectedTile = {x: building.x, y: building.y};
        state.selectedCommandBuildingKey = building.key;
        state.panelMode = "command";
        state.buildOpen = true;
        state.commandFeedback = null;
        renderCommandPanel();
        setBuildVisibility();
    }

    async function recruitSelectedBuilding() {
        const building = selectedCommandBuilding();
        if (
            !building ||
            !building.isMine ||
            !building.canRecruit ||
            state.interactionLocked ||
            state.pendingRecruit
        ) {
            return;
        }
        const pending = {
            buildingKey: building.key,
            baselineQueue: queueIdSignature(building),
            baselineGold: Number(state.resources.gold),
            sentAt: performance.now(),
        };
        state.commandFeedback = null;
        state.pendingRecruit = pending;
        renderCommandPanel();
        const result = await callBridge("recruit_troop", building.x, building.y);
        if (
            (!result || result.ok === false) &&
            state.pendingRecruit === pending
        ) {
            state.pendingRecruit = null;
            state.commandFeedback = {
                buildingKey: building.key,
                message: "Não foi possível enviar a ordem de recrutamento.",
                expiresAt: performance.now() + 4000,
            };
            renderCommandPanel();
        }
    }

    function normalizeTarget(target) {
        if (
            !Array.isArray(target) ||
            target.length !== 2 ||
            !target.every(Number.isFinite)
        ) {
            return null;
        }
        return [Number(target[0]), Number(target[1])];
    }

    function normalizeTroop(rawTroop) {
        if (!rawTroop || typeof rawTroop !== "object" || rawTroop.id == null) {
            return null;
        }

        const x = Number(rawTroop.x);
        const y = Number(rawTroop.y);
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
            return null;
        }

        const maxHp = Math.max(1, Number(rawTroop.max_hp) || 1);
        const hp = Math.max(0, Math.min(maxHp, Number(rawTroop.hp) || 0));
        const status = ["idle", "moving", "attacking"].includes(rawTroop.status)
            ? rawTroop.status
            : "idle";

        return {
            id: rawTroop.id,
            key: String(rawTroop.id),
            owner: rawTroop.owner == null ? null : String(rawTroop.owner),
            isMine: typeof rawTroop.is_mine === "boolean" ? rawTroop.is_mine : null,
            kind: rawTroop.kind === "boat" ? "boat" : "land",
            x,
            y,
            hp,
            maxHp,
            target: normalizeTarget(rawTroop.target),
            status,
        };
    }

    function troopIsMine(troop) {
        if (typeof troop?.isMine === "boolean") {
            return troop.isMine;
        }
        return Boolean(
            troop &&
            state.playerId !== null &&
            troop.owner === state.playerId
        );
    }

    function rebuildTroopOffsets() {
        const groups = new Map();
        for (const troop of state.troops) {
            const positionKey = `${troop.x},${troop.y}`;
            if (!groups.has(positionKey)) {
                groups.set(positionKey, []);
            }
            groups.get(positionKey).push(troop);
        }

        state.troopOffsets = new Map();
        for (const troopsAtPosition of groups.values()) {
            troopsAtPosition.sort((first, second) => first.key.localeCompare(second.key));
            for (let index = 0; index < troopsAtPosition.length; index += 1) {
                const offset = troopsAtPosition.length > 1
                    ? TROOP_STACK_OFFSETS[index % TROOP_STACK_OFFSETS.length]
                    : [0, 0];
                state.troopOffsets.set(troopsAtPosition[index].key, offset);
            }
        }
    }

    function selectedTroop() {
        if (state.selectedTroopId === null) {
            return null;
        }
        return state.troops.find((troop) => (
            troop.key === state.selectedTroopId && troopIsMine(troop)
        )) || null;
    }

    function troopTarget(troop) {
        if (
            state.pendingTroopTarget &&
            state.pendingTroopTarget.unitKey === troop.key
        ) {
            return [state.pendingTroopTarget.x, state.pendingTroopTarget.y];
        }
        return troop.target;
    }

    function troopStatusText(troop) {
        const target = troopTarget(troop);
        const destination = target
            ? ` (${Math.trunc(target[0])}, ${Math.trunc(target[1])})`
            : "";

        if (
            state.pendingTroopTarget &&
            state.pendingTroopTarget.unitKey === troop.key
        ) {
            return `Ordem enviada${destination}`;
        }
        if (troop.status === "attacking") {
            return `Em combate${destination}`;
        }
        if (troop.status === "moving") {
            return troop.kind === "boat"
                ? `Navegando${destination}`
                : `Marchando${destination}`;
        }
        return "Em posição";
    }

    function updateTroopSelectionUi() {
        const troop = state.visible ? selectedTroop() : null;
        const isVisible = Boolean(troop);

        troopSelection.hidden = !isVisible;
        gameScreen.classList.toggle("has-selected-troop", isVisible);
        if (!troop) {
            return;
        }

        const healthRatio = Math.max(0, Math.min(1, troop.hp / troop.maxHp));
        troopSelectionTitle.textContent = troop.kind === "boat"
            ? "Embarcação"
            : "Tropa terrestre";
        troopHealthValue.textContent = `${Math.ceil(troop.hp)} / ${Math.ceil(troop.maxHp)}`;
        troopHealth.style.setProperty("--troop-health", String(healthRatio));
        troopHealth.setAttribute("aria-valuemax", String(Math.ceil(troop.maxHp)));
        troopHealth.setAttribute("aria-valuenow", String(Math.ceil(troop.hp)));
        troopStatus.textContent = troopStatusText(troop);
    }

    function addTroopEffect(kind, troop, now) {
        state.troopEffects.push({
            kind,
            x: troop.x,
            y: troop.y,
            seed: hashText(troop.key),
            startedAt: now,
        });
        if (state.troopEffects.length > TROOP_EFFECT_LIMIT) {
            state.troopEffects.splice(
                0,
                state.troopEffects.length - TROOP_EFFECT_LIMIT,
            );
        }
    }

    function troopTilePassable(kind, x, y) {
        if (
            !Number.isInteger(x) ||
            !Number.isInteger(y) ||
            x < 0 ||
            y < 0 ||
            x >= state.worldWidth ||
            y >= state.worldHeight ||
            !Array.isArray(state.matrix?.[y])
        ) {
            return false;
        }
        const name = tileName(state.matrix[y][x]);
        return kind === "boat"
            ? ["water", "dock"].includes(name)
            : !["water", "dock", "mountain", "mine"].includes(name);
    }

    function findTroopPath(troop, from, to) {
        const fromX = Math.trunc(from.x);
        const fromY = Math.trunc(from.y);
        const toX = Math.trunc(to.x);
        const toY = Math.trunc(to.y);
        const directDistance = Math.abs(toX - fromX) + Math.abs(toY - fromY);
        if (directDistance === 0) {
            return [{x: toX, y: toY}];
        }
        // Uma distância maior pode indicar snapshots intermediários perdidos.
        // Nesse caso o reconciliador ainda dará retorno visual direto, mas não
        // inventará uma rota pelo mapa que o cliente nunca recebeu.
        if (directDistance > 4 || !state.matrix) {
            return null;
        }

        const padding = 4;
        const minX = Math.max(0, Math.min(fromX, toX) - padding);
        const maxX = Math.min(state.worldWidth - 1, Math.max(fromX, toX) + padding);
        const minY = Math.max(0, Math.min(fromY, toY) - padding);
        const maxY = Math.min(state.worldHeight - 1, Math.max(fromY, toY) + padding);
        const startKey = commandBuildingKey(fromX, fromY);
        const targetKey = commandBuildingKey(toX, toY);
        const queue = [{x: fromX, y: fromY}];
        const cameFrom = new Map([[startKey, null]]);
        const directions = [[1, 0], [0, 1], [-1, 0], [0, -1]];

        for (let cursor = 0; cursor < queue.length; cursor += 1) {
            const current = queue[cursor];
            const currentKey = commandBuildingKey(current.x, current.y);
            if (currentKey === targetKey) {
                break;
            }
            for (const [dx, dy] of directions) {
                const x = current.x + dx;
                const y = current.y + dy;
                const key = commandBuildingKey(x, y);
                if (
                    x < minX || x > maxX || y < minY || y > maxY ||
                    cameFrom.has(key) ||
                    !troopTilePassable(troop.kind, x, y)
                ) {
                    continue;
                }
                cameFrom.set(key, currentKey);
                queue.push({x, y});
            }
        }

        if (!cameFrom.has(targetKey)) {
            return null;
        }
        const reversed = [];
        let key = targetKey;
        while (key !== null) {
            const [x, y] = key.split(",").map(Number);
            reversed.push({x, y});
            key = cameFrom.get(key) ?? null;
        }
        return reversed.reverse();
    }

    function startTroopMotion(troop, previous, now) {
        const resolvedPath = findTroopPath(troop, previous, troop);
        const catchUp = !resolvedPath || resolvedPath.length < 2;
        const path = catchUp
            ? [
                {x: previous.x, y: previous.y},
                {x: troop.x, y: troop.y},
            ]
            : resolvedPath;
        if (
            path[0].x === path[path.length - 1].x &&
            path[0].y === path[path.length - 1].y
        ) {
            state.troopMotions.delete(troop.key);
            return;
        }
        const travelDistance = path.slice(1).reduce((distance, position, index) => (
            distance +
            Math.abs(position.x - path[index].x) +
            Math.abs(position.y - path[index].y)
        ), 0);
        const reduced = prefersReducedMotion();
        const durationMs = reduced
            ? Math.max(
                TROOP_MOTION_REDUCED_MIN_MS,
                Math.min(TROOP_MOTION_REDUCED_MAX_MS, 420 + travelDistance * 120),
            )
            : Math.max(
                TROOP_MOTION_MIN_MS,
                Math.min(TROOP_MOTION_MAX_MS, 1200 + travelDistance * 600),
            );
        state.troopMotions.set(troop.key, {
            path,
            startedAt: now,
            durationMs,
            reduced,
            catchUp,
            destinationKey: commandBuildingKey(troop.x, troop.y),
        });
    }

    function troopVisualState(troop, now = performance.now()) {
        const motion = state.troopMotions.get(troop.key);
        if (!motion) {
            return {x: troop.x, y: troop.y, moving: false, dx: 0, dy: 0};
        }
        const rawProgress = Math.max(0, (now - motion.startedAt) / motion.durationMs);
        if (rawProgress >= 1) {
            state.troopMotions.delete(troop.key);
            return {x: troop.x, y: troop.y, moving: false, dx: 0, dy: 0};
        }
        const progress = rawProgress * rawProgress * (3 - 2 * rawProgress);
        const segmentPosition = progress * (motion.path.length - 1);
        const segmentIndex = Math.min(
            motion.path.length - 2,
            Math.floor(segmentPosition),
        );
        const localProgress = segmentPosition - segmentIndex;
        const from = motion.path[segmentIndex];
        const to = motion.path[segmentIndex + 1];
        return {
            x: from.x + (to.x - from.x) * localProgress,
            y: from.y + (to.y - from.y) * localProgress,
            moving: true,
            dx: to.x - from.x,
            dy: to.y - from.y,
            progress: rawProgress,
            segmentIndex,
        };
    }

    function applyTroopSnapshot(snapshot) {
        if (snapshot.player_id != null) {
            state.playerId = String(snapshot.player_id);
        }
        if (!Array.isArray(snapshot.troops)) {
            return;
        }

        const nextTroops = snapshot.troops
            .map(normalizeTroop)
            .filter(Boolean);
        const previousById = new Map(state.troops.map((troop) => [troop.key, troop]));
        const nextById = new Map(nextTroops.map((troop) => [troop.key, troop]));
        const now = performance.now();

        for (const troop of nextTroops) {
            const previous = previousById.get(troop.key);
            if (!previous) {
                if (state.hasTroopSnapshot) {
                    addTroopEffect("spawn", troop, now);
                }
            } else {
                if (troop.hp < previous.hp) {
                    addTroopEffect("damage", troop, now);
                }
                if (troop.x !== previous.x || troop.y !== previous.y) {
                    if (state.hasTroopSnapshot) {
                        startTroopMotion(troop, previous, now);
                    } else {
                        state.troopMotions.delete(troop.key);
                    }
                }
            }
        }
        for (const troop of state.troops) {
            if (!nextById.has(troop.key)) {
                if (state.hasTroopSnapshot) {
                    addTroopEffect("death", troop, now);
                }
                state.troopMotions.delete(troop.key);
            }
        }

        state.troops = nextTroops;
        state.hasTroopSnapshot = true;
        rebuildTroopOffsets();
        const selected = selectedTroop();
        if (!selected) {
            state.selectedTroopId = null;
            state.pendingTroopTarget = null;
        } else if (
            state.pendingTroopTarget &&
            selected.target &&
            selected.target[0] === state.pendingTroopTarget.x &&
            selected.target[1] === state.pendingTroopTarget.y
        ) {
            state.pendingTroopTarget = null;
        } else if (
            state.pendingTroopTarget &&
            now - state.pendingTroopTarget.sentAt > 2500
        ) {
            // A ponte confirma o envio local antes da validação do servidor.
            // Não preserve indefinidamente uma ordem que tenha sido recusada.
            state.pendingTroopTarget = null;
        }
        updateTroopSelectionUi();
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

        // A matriz e as dimensões precisam estar atuais antes de calcular as
        // rotas visuais das tropas recebidas neste mesmo snapshot.
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

        applyTickSnapshot(snapshot);
        updateTickHud(performance.now());
        applyTroopSnapshot(snapshot);
        applyCommandSnapshot(snapshot);

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

    function worldPoint(point) {
        return {
            x: state.cameraX + point.x / state.zoom,
            y: state.cameraY + point.y / state.zoom,
        };
    }

    function tileAtPoint(point) {
        const world = worldPoint(point);
        const x = Math.floor(world.x / TILE_SIZE);
        const y = Math.floor(world.y / TILE_SIZE);
        if (
            x < 0 ||
            y < 0 ||
            x >= state.worldWidth ||
            y >= state.worldHeight
        ) {
            return null;
        }
        return {x, y};
    }

    function troopAtPoint(point) {
        const world = worldPoint(point);
        let nearest = null;
        let nearestDistance = TROOP_HIT_RADIUS * TROOP_HIT_RADIUS;
        const now = performance.now();

        for (const troop of state.troops) {
            const center = troopWorldCenter(troop, now);
            const distance = (
                (world.x - center.x) ** 2 +
                (world.y - center.y) ** 2
            );
            if (
                distance <= nearestDistance &&
                (!nearest || troopIsMine(troop) || !troopIsMine(nearest))
            ) {
                nearest = troop;
                nearestDistance = distance;
            }
        }
        return nearest;
    }

    function clearTroopSelection() {
        state.selectedTroopId = null;
        state.pendingTroopTarget = null;
        updateTroopSelectionUi();
    }

    function selectTroop(troop) {
        if (!troopIsMine(troop)) {
            clearTroopSelection();
            return;
        }
        state.selectedTroopId = troop.key;
        state.pendingTroopTarget = null;
        state.selectedTile = null;
        state.panelMode = "build";
        state.selectedCommandBuildingKey = null;
        state.pendingRecruit = null;
        state.commandFeedback = null;
        state.buildOpen = false;
        setBuildVisibility();
        updateTroopSelectionUi();
    }

    async function commandSelectedTroop(tile) {
        const troop = selectedTroop();
        if (!troop || state.interactionLocked) {
            return;
        }

        const pendingOrder = {
            unitKey: troop.key,
            x: tile.x,
            y: tile.y,
            sentAt: performance.now(),
        };
        state.pendingTroopTarget = pendingOrder;
        updateTroopSelectionUi();
        const result = await callBridge(
            "command_troop",
            troop.id,
            tile.x,
            tile.y,
        );
        if (
            (!result || result.ok === false) &&
            state.pendingTroopTarget === pendingOrder
        ) {
            state.pendingTroopTarget = null;
            updateTroopSelectionUi();
        }
    }

    function selectTile(point) {
        if (!state.matrix || state.worldWidth <= 0 || state.worldHeight <= 0) {
            return;
        }

        const tile = tileAtPoint(point);
        if (!tile) {
            return;
        }
        const {x: tileX, y: tileY} = tile;
        state.panelMode = "build";
        state.selectedCommandBuildingKey = null;
        state.pendingRecruit = null;
        state.commandFeedback = null;

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

    function hashText(value) {
        let hash = 2166136261;
        const textValue = String(value);
        for (let index = 0; index < textValue.length; index += 1) {
            hash ^= textValue.charCodeAt(index);
            hash = Math.imul(hash, 16777619);
        }
        return hash >>> 0;
    }

    function seededValue(seed, index) {
        let value = (seed + Math.imul(index + 1, 0x9e3779b1)) >>> 0;
        value ^= value >>> 16;
        value = Math.imul(value, 0x21f0aaad);
        value ^= value >>> 15;
        value = Math.imul(value, 0x735a2d97);
        return (value ^ (value >>> 15)) >>> 0;
    }

    function troopPalette(troop) {
        if (troopIsMine(troop)) {
            return {
                bright: "#ffe29a",
                main: "#d9ad55",
                dark: "#704720",
                accent: "#9fc8b0",
            };
        }
        const hue = hashText(troop.owner || troop.key) % 360;
        return {
            bright: `hsl(${hue} 78% 76%)`,
            main: `hsl(${hue} 62% 55%)`,
            dark: `hsl(${hue} 48% 25%)`,
            accent: "#e47b68",
        };
    }

    function troopScreenCenter(troop, now = performance.now(), visual = null) {
        const center = troopWorldCenter(troop, now, visual);
        return {
            x: (center.x - state.cameraX) * state.zoom,
            y: (center.y - state.cameraY) * state.zoom,
        };
    }

    function troopWorldCenter(troop, now = performance.now(), visual = null) {
        const offset = state.troopOffsets.get(troop.key) || [0, 0];
        const position = visual || troopVisualState(troop, now);
        return {
            x: (position.x + 0.5) * TILE_SIZE + offset[0],
            y: (position.y + 0.5) * TILE_SIZE + offset[1],
        };
    }

    function drawPixelRect(center, dx, dy, width, height, color) {
        context.fillStyle = color;
        context.fillRect(
            Math.round(center.x + dx * state.zoom),
            Math.round(center.y + dy * state.zoom),
            Math.max(1, Math.round(width * state.zoom)),
            Math.max(1, Math.round(height * state.zoom)),
        );
    }

    function drawLandTroop(troop, center, palette, seed) {
        const memberCount = 5 + seed % 4;
        for (let index = 0; index < memberCount; index += 1) {
            const random = seededValue(seed, index);
            const [formationX, formationY] = LAND_FORMATION[index];
            const offsetX = formationX + (random % 3) - 1;
            const offsetY = formationY + ((random >>> 3) % 3) - 1;
            const bodyColor = index % 3 === 0 ? palette.accent : palette.main;

            drawPixelRect(center, offsetX - 1, offsetY + 4, 3, 1, "rgba(8, 7, 5, 0.55)");
            drawPixelRect(center, offsetX - 1, offsetY - 3, 2, 2, palette.bright);
            drawPixelRect(center, offsetX - 1, offsetY - 1, 3, 4, bodyColor);
            drawPixelRect(center, offsetX - 1, offsetY + 3, 1, 2, palette.dark);
            drawPixelRect(center, offsetX + 1, offsetY + 3, 1, 2, palette.dark);
            if ((random >>> 7) % 2 === 0) {
                drawPixelRect(center, offsetX + 2, offsetY - 1, 1, 6, palette.bright);
            }
        }
    }

    function drawBoatTroop(troop, center, palette, seed) {
        const target = troopTarget(troop);
        const direction = target && target[0] < troop.x ? -1 : 1;
        const orientedX = (offset, width) => (
            direction > 0 ? offset : -offset - width
        );

        drawPixelRect(center, -10, 6, 20, 3, "rgba(6, 9, 10, 0.58)");
        drawPixelRect(center, -10, 3, 20, 4, palette.dark);
        drawPixelRect(center, -8, 0, 16, 4, palette.main);
        drawPixelRect(center, orientedX(8, 3), 1, 3, 3, palette.bright);
        drawPixelRect(center, -1, -10, 2, 12, palette.dark);
        drawPixelRect(center, orientedX(1, 7), -9, 7, 2, palette.bright);
        drawPixelRect(center, orientedX(1, 6), -7, 6, 2, palette.bright);
        drawPixelRect(center, orientedX(1, 5), -5, 5, 2, palette.accent);
        drawPixelRect(
            center,
            orientedX(-3, 5),
            -12,
            5,
            2,
            seed % 2 ? palette.accent : palette.main,
        );
        drawPixelRect(center, -6, 5, 12, 1, palette.bright);
    }

    function troopPathScreenPoint(position, offset) {
        return {
            x: ((position.x + 0.5) * TILE_SIZE + offset[0] - state.cameraX) * state.zoom,
            y: ((position.y + 0.5) * TILE_SIZE + offset[1] - state.cameraY) * state.zoom,
        };
    }

    function drawTroopMotionFeedback(troop, center, visual, palette, now) {
        if (!visual.moving) {
            return;
        }
        const motion = state.troopMotions.get(troop.key);
        if (!motion) {
            return;
        }

        const offset = state.troopOffsets.get(troop.key) || [0, 0];
        const pathPoints = motion.path.map((position) => (
            troopPathScreenPoint(position, offset)
        ));
        const lineWidth = Math.max(1, Math.round(2 * state.zoom));

        // A rota inteira liga exclusivamente as duas posições autoritativas.
        // O trecho sólido termina na posição visual interpolada neste frame.
        context.save();
        context.lineCap = "square";
        context.lineJoin = "miter";
        context.strokeStyle = palette.bright;
        context.globalAlpha = motion.reduced ? 0.38 : 0.26;
        context.lineWidth = lineWidth;
        context.setLineDash([
            Math.max(2, Math.round(4 * state.zoom)),
            Math.max(2, Math.round(3 * state.zoom)),
        ]);
        context.beginPath();
        context.moveTo(pathPoints[0].x, pathPoints[0].y);
        for (const point of pathPoints.slice(1)) {
            context.lineTo(point.x, point.y);
        }
        context.stroke();

        context.globalAlpha = motion.reduced ? 0.88 : 0.68;
        context.setLineDash([]);
        context.beginPath();
        context.moveTo(pathPoints[0].x, pathPoints[0].y);
        for (let index = 1; index <= visual.segmentIndex; index += 1) {
            context.lineTo(pathPoints[index].x, pathPoints[index].y);
        }
        context.lineTo(center.x, center.y);
        context.stroke();
        context.restore();

        const pulse = (now % 520) / 520;
        const radius = motion.reduced ? 15 : 14 + pulse * 4;
        const markerAlpha = motion.reduced ? 0.95 : 0.72 - pulse * 0.26;
        const markerColor = motion.catchUp
            ? `rgba(246, 158, 91, ${markerAlpha})`
            : troop.kind === "boat"
            ? `rgba(191, 237, 236, ${markerAlpha})`
            : `rgba(242, 208, 130, ${markerAlpha})`;
        drawPixelRect(center, -radius, -radius, 6, 2, markerColor);
        drawPixelRect(center, radius - 6, -radius, 6, 2, markerColor);
        drawPixelRect(center, -radius, radius - 2, 6, 2, markerColor);
        drawPixelRect(center, radius - 6, radius - 2, 6, 2, markerColor);

        const arrowDistance = 15;
        const arrowCenter = {
            x: center.x + visual.dx * arrowDistance * state.zoom,
            y: center.y + visual.dy * arrowDistance * state.zoom,
        };
        drawPixelRect(arrowCenter, -2, -2, 4, 4, markerColor);
    }

    function drawLandDust(center, visual, seed, now) {
        if (!visual.moving) {
            return;
        }
        const pulse = Math.floor(now / 120);
        const backX = -visual.dx * 7;
        const backY = -visual.dy * 7;
        const perpendicularX = -visual.dy;
        const perpendicularY = visual.dx;
        for (let index = 0; index < 4; index += 1) {
            const random = seededValue(seed + pulse, index);
            const spread = (random % 9) - 4;
            const distance = index * 3 + (random >>> 5) % 3;
            drawPixelRect(
                center,
                backX - visual.dx * distance + perpendicularX * spread,
                backY - visual.dy * distance + perpendicularY * spread + 7,
                index % 2 ? 2 : 3,
                2,
                `rgba(194, 155, 96, ${0.42 - index * 0.07})`,
            );
        }
    }

    function drawBoatWake(center, visual, now) {
        if (!visual.moving) {
            return;
        }
        const pulse = (now % 420) / 420;
        const backX = -visual.dx;
        const backY = -visual.dy;
        const perpendicularX = -visual.dy;
        const perpendicularY = visual.dx;
        for (let index = 0; index < 4; index += 1) {
            const distance = 8 + index * 5 + pulse * 4;
            const spread = 2 + index * 2;
            for (const side of [-1, 1]) {
                drawPixelRect(
                    center,
                    backX * distance + perpendicularX * spread * side,
                    backY * distance + perpendicularY * spread * side + 5,
                    index < 2 ? 3 : 2,
                    1,
                    `rgba(177, 225, 224, ${0.62 - index * 0.11})`,
                );
            }
        }
    }

    function drawTroopHealth(troop, center, selected) {
        if (!selected && troop.hp >= troop.maxHp) {
            return;
        }
        const width = 22;
        const ratio = Math.max(0, Math.min(1, troop.hp / troop.maxHp));
        drawPixelRect(center, -width / 2 - 1, -15, width + 2, 4, "rgba(10, 7, 5, 0.88)");
        drawPixelRect(
            center,
            -width / 2,
            -14,
            Math.max(1, width * ratio),
            2,
            ratio > 0.35 ? "#91c568" : "#df6857",
        );
    }

    function drawTroopSelection(center) {
        const color = "#ffe598";
        const corner = 5;
        const radius = 14;
        drawPixelRect(center, -radius, -radius, corner, 2, color);
        drawPixelRect(center, -radius, -radius, 2, corner, color);
        drawPixelRect(center, radius - corner, -radius, corner, 2, color);
        drawPixelRect(center, radius - 2, -radius, 2, corner, color);
        drawPixelRect(center, -radius, radius - 2, corner, 2, color);
        drawPixelRect(center, -radius, radius - corner, 2, corner, color);
        drawPixelRect(center, radius - corner, radius - 2, corner, 2, color);
        drawPixelRect(center, radius - 2, radius - corner, 2, corner, color);
    }

    function drawTroopOrder(now) {
        const troop = selectedTroop();
        const target = troop ? troopTarget(troop) : null;
        if (!troop || !target) {
            return;
        }

        const start = troopScreenCenter(troop, now);
        const end = {
            x: ((target[0] + 0.5) * TILE_SIZE - state.cameraX) * state.zoom,
            y: ((target[1] + 0.5) * TILE_SIZE - state.cameraY) * state.zoom,
        };
        const hostileAtTarget = state.troops.some((candidate) => (
            !troopIsMine(candidate) &&
            Math.trunc(candidate.x) === Math.trunc(target[0]) &&
            Math.trunc(candidate.y) === Math.trunc(target[1])
        ));
        const color = hostileAtTarget ? "#ef7865" : "#f5d77f";

        context.save();
        context.strokeStyle = color;
        context.lineWidth = Math.max(1, state.zoom);
        context.globalAlpha = 0.86;
        context.setLineDash([
            Math.max(3, Math.round(5 * state.zoom)),
            Math.max(2, Math.round(4 * state.zoom)),
        ]);
        context.beginPath();
        context.moveTo(Math.round(start.x), Math.round(start.y));
        context.lineTo(Math.round(end.x), Math.round(end.y));
        context.stroke();
        context.restore();

        drawPixelRect(end, -8, -8, 6, 2, color);
        drawPixelRect(end, -8, -8, 2, 6, color);
        drawPixelRect(end, 2, -8, 6, 2, color);
        drawPixelRect(end, 6, -8, 2, 6, color);
        drawPixelRect(end, -8, 6, 6, 2, color);
        drawPixelRect(end, -8, 2, 2, 6, color);
        drawPixelRect(end, 2, 6, 6, 2, color);
        drawPixelRect(end, 6, 2, 2, 6, color);
    }

    function drawTroops(now) {
        for (const troop of state.troops) {
            const visual = troopVisualState(troop, now);
            const center = troopScreenCenter(troop, now, visual);
            const margin = TILE_SIZE * state.zoom;
            if (
                center.x < -margin ||
                center.y < -margin ||
                center.x > state.viewportWidth + margin ||
                center.y > state.viewportHeight + margin
            ) {
                continue;
            }

            const selected = troop.key === state.selectedTroopId;
            const palette = troopPalette(troop);
            const seed = hashText(troop.key);
            drawTroopMotionFeedback(troop, center, visual, palette, now);
            if (selected) {
                drawTroopSelection(center);
            }
            if (troop.kind === "boat") {
                drawBoatWake(center, visual, now);
                drawBoatTroop(troop, center, palette, seed);
            } else {
                drawLandDust(center, visual, seed, now);
                drawLandTroop(troop, center, palette, seed);
            }
            drawTroopHealth(troop, center, selected);
        }
    }

    function drawTroopEffects(now) {
        const activeEffects = [];
        for (const effect of state.troopEffects) {
            const duration = TROOP_EFFECT_DURATION_MS[effect.kind];
            const progress = (now - effect.startedAt) / duration;
            if (progress < 0 || progress >= 1) {
                continue;
            }
            activeEffects.push(effect);
            const center = {
                x: ((effect.x + 0.5) * TILE_SIZE - state.cameraX) * state.zoom,
                y: ((effect.y + 0.5) * TILE_SIZE - state.cameraY) * state.zoom,
            };

            context.save();
            context.globalAlpha = 1 - progress;
            if (effect.kind === "spawn") {
                const radius = 7 + progress * 13;
                context.strokeStyle = "#c6e78d";
                context.lineWidth = Math.max(1, state.zoom);
                context.strokeRect(
                    Math.round(center.x - radius * state.zoom),
                    Math.round(center.y - radius * state.zoom),
                    Math.round(radius * 2 * state.zoom),
                    Math.round(radius * 2 * state.zoom),
                );
            } else {
                const color = effect.kind === "damage" ? "#ff765f" : "#6e2924";
                const distance = (4 + progress * 13) * state.zoom;
                for (let index = 0; index < 7; index += 1) {
                    const random = seededValue(effect.seed, index);
                    const angle = (random % 628) / 100;
                    context.fillStyle = color;
                    context.fillRect(
                        Math.round(center.x + Math.cos(angle) * distance),
                        Math.round(center.y + Math.sin(angle) * distance),
                        Math.max(1, Math.round((effect.kind === "death" ? 3 : 2) * state.zoom)),
                        Math.max(1, Math.round(2 * state.zoom)),
                    );
                }
            }
            context.restore();
        }
        state.troopEffects = activeEffects;
    }

    function drawWorld(now = performance.now()) {
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

        drawTroopOrder(now);
        drawTroops(now);
        drawTroopEffects(now);
    }

    listen(canvas, "pointerdown", (event) => {
        if (event.button !== 0 || !state.visible || state.interactionLocked) {
            return;
        }

        const point = logicalPoint(event.clientX, event.clientY);
        if (point) {
            event.preventDefault();
            const troop = troopAtPoint(point);
            if (troop && troopIsMine(troop)) {
                selectTroop(troop);
            } else {
                clearTroopSelection();
                if (troop) {
                    state.selectedTile = null;
                    state.panelMode = "build";
                    state.selectedCommandBuildingKey = null;
                    state.pendingRecruit = null;
                    state.commandFeedback = null;
                    state.buildOpen = false;
                    setBuildVisibility();
                } else {
                    const tile = tileAtPoint(point);
                    const building = tile ? commandBuildingAt(tile.x, tile.y) : null;
                    if (building) {
                        selectCommandBuilding(building);
                    } else {
                        selectTile(point);
                    }
                }
            }
        }
    });

    listen(canvas, "contextmenu", (event) => {
        if (!state.visible) {
            return;
        }
        event.preventDefault();
        if (state.interactionLocked || !selectedTroop()) {
            return;
        }

        const point = logicalPoint(event.clientX, event.clientY);
        const tile = point ? tileAtPoint(point) : null;
        if (tile) {
            void commandSelectedTroop(tile);
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

        if (
            event.code === "Escape" &&
            state.buildOpen &&
            state.panelMode === "command"
        ) {
            event.preventDefault();
            returnToBuildPanel();
            return;
        }

        if (event.code === "Escape" && state.buildOpen) {
            event.preventDefault();
            state.buildOpen = false;
            setBuildVisibility();
            return;
        }

        if (event.code === "Escape" && state.selectedTroopId !== null) {
            event.preventDefault();
            clearTroopSelection();
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
    disposers.push(bindPrimaryAction(commandPanelBack, returnToBuildPanel));
    disposers.push(bindPrimaryAction(commandRecruitButton, () => {
        void recruitSelectedBuilding();
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
            updateCommandQueueTiming(time);
            if (!state.interactionLocked) {
                updateCamera(deltaSeconds);
            }
            drawWorld(time);
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
