import {mkdir, writeFile} from "node:fs/promises";
import {resolve} from "node:path";

// Executado pelo mesmo Edge headless do frontend_motion_probe.mjs.
export async function auditResponsiveUi(session, artifactDir) {
    await mkdir(artifactDir, {recursive: true});
    const evaluate = (fn) => session.evaluate(`(${fn.toString()})()`);
    const pause = () => new Promise((done) => setTimeout(done, 240));
    const screenshot = async (name) => {
        const shot = await session.call("Page.captureScreenshot", {format: "png"});
        await writeFile(resolve(artifactDir, `${name}.png`), Buffer.from(shot.data, "base64"));
    };
    await evaluate(() => {
        window.__uiLobbySnapshot = structuredClone(window.__motionSnapshot.lobby);
        window.__motionSnapshot = structuredClone(window.__uiSavedGame);
        window.__uiChecks = [];
        window.__uiCheck = (condition, message) => { if (!condition) throw new Error(message); };
        window.__uiClickMap = (dx = 0, dy = 0) => {
            const canvas = document.getElementById("world-canvas");
            const box = canvas.getBoundingClientRect();
            canvas.dispatchEvent(new PointerEvent("pointerdown", {
                button: 0, bubbles: true,
                clientX: box.left + box.width / 2 + dx * 80 * box.width / canvas.width,
                clientY: box.top + box.height / 2 + dy * 80 * box.height / canvas.height,
            }));
        };
        window.__uiAudit = (label) => {
            const issues = [];
            const walker = document.createTreeWalker(document.getElementById("viewport"), NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const node = walker.currentNode;
                if (!node.textContent.trim()) continue;
                const element = node.parentElement;
                if (!element.checkVisibility() || element.closest("[inert]")) continue;
                const style = getComputedStyle(element);
                if (style.visibility !== "visible") continue;
                const parentRect = element.getBoundingClientRect();
                const range = document.createRange();
                range.selectNodeContents(node);
                for (const rect of range.getClientRects()) {
                    if (rect.bottom < 0 || rect.top > innerHeight) continue;
                    if (rect.right > parentRect.right + 2 || rect.left < parentRect.left - 2) {
                        issues.push(`${element.id || element.className}: ${node.textContent.trim()}`);
                    }
                }
            }
            window.__uiCheck(!issues.length, `${label}: texto fora do campo: ${issues.join(" | ")}`);
            window.__uiCheck(getComputedStyle(document.getElementById("viewport")).transform === "none", "Textos não podem ser escalados pelo viewport.");
            for (const selector of [".menu-card", ".lobby-shell", ".settings-dialog", ".troop-selection", "#build-menu.is-open"]) {
                for (const el of document.querySelectorAll(selector)) {
                    if (!el.checkVisibility()) continue;
                    const box = el.getBoundingClientRect();
                    window.__uiCheck(box.left >= 0 && box.right <= innerWidth + 1 && box.top >= 0 && box.bottom <= innerHeight + 1, `${label}: ${selector} fora da janela.`);
                    window.__uiCheck(el.scrollWidth <= el.clientWidth + 1, `${label}: ${selector} com rolagem horizontal.`);
                }
            }
            window.__uiChecks.push(label);
        };
    });

    await pause();
    await evaluate(() => {
        window.__uiClickMap(2);
        window.__uiClickMap(3);
    });
    for (const [width, height, deviceScaleFactor] of [
        [960, 720, 1], [1280, 720, 1], [1280, 960, 1], [1366, 768, 1],
        [1536, 864, 1.25], [1600, 900, 1], [1920, 1080, 1.5],
    ]) {
        await session.call("Emulation.setDeviceMetricsOverride", {width, height, deviceScaleFactor, mobile: false});
        await pause();
        await evaluate(() => {
            window.__uiAudit(`pioneiro-${innerWidth}`);
            const byId = (id) => document.getElementById(id);
            byId("build-panel-toggle").click();
        });
        await pause();
        await evaluate(() => {
            const byId = (id) => document.getElementById(id);
            const visibleTiles = () => [...document.querySelectorAll(".build-button")].filter((button) => !button.hidden).map((button) => button.dataset.tile);
            const groups = {
                buildings: ["town_center", "city", "guard_house", "dock", "mine", "lumberjack_cabin"],
                terrain: ["water", "mountain", "grass"],
                vegetation: ["small_forest", "medium_forest", "big_forest"],
            };
            for (const [category, expected] of Object.entries(groups)) {
                const tab = document.querySelector(`[data-build-category="${category}"]`);
                tab.click();
                window.__uiCheck(JSON.stringify(visibleTiles()) === JSON.stringify(expected), `Categoria ${category} perdeu construções.`);
                window.__uiCheck(tab.getAttribute("aria-pressed") === "true", "Categoria ativa não anunciada.");
                window.__uiAudit(`construcoes-${category}-${innerWidth}`);
            }
            document.querySelector('[data-build-category="buildings"]').click();
            document.querySelector('[data-tile="lumberjack_cabin"]').focus();
            window.__uiAudit(`detalhes-construcao-${innerWidth}`);
        });
        if (width === 1280 && height === 720) await screenshot("ui-construcoes-1280");
        await evaluate(() => {
            document.activeElement.blur();
            document.getElementById("build-panel-toggle").click();
            const snapshot = window.__motionSnapshot;
            snapshot.command_buildings[0].queue = Array.from({length: 5}, (_, index) => ({
                id: `ui-queue-${index}`, unit_kind: "pioneer", remaining_ticks: 1,
                total_ticks: 1, cost_gold: 60, waiting_for_start: true,
            }));
            snapshot.world_revision += 1;
            window.__uiClickMap();
        });
        await pause();
        await evaluate(() => {
            window.__uiAudit(`fila-cheia-${innerWidth}`);
            const queue = document.getElementById("command-queue");
            window.__uiCheck(queue.children.length === 5, "Fila deve manter todas as ordens.");
            queue.scrollTop = queue.scrollHeight;
            const last = queue.lastElementChild.getBoundingClientRect();
            window.__uiCheck(last.bottom <= queue.getBoundingClientRect().bottom + 1, "Última ordem não é acessível por rolagem.");
            window.__uiCheck(document.getElementById("command-recruit-button").disabled, "Fila cheia deve bloquear recrutamento.");
        });
        if (width === 960) await screenshot("ui-recrutamento-960");
        await evaluate(() => {
            document.getElementById("build-panel-toggle").click();
            window.__uiClickMap(2);
            window.__uiClickMap(3);
            document.getElementById("troop-selection-close").click();
            // O próximo Escape abre as configurações, sem seleção ativa.
            document.dispatchEvent(new KeyboardEvent("keydown", {code: "Escape", key: "Escape", bubbles: true}));
        });
        await pause();
        await evaluate(() => {
            window.__uiCheck(!document.getElementById("settings-overlay").hidden, "Configurações não abriram.");
            window.__uiAudit(`configuracoes-${innerWidth}`);
            const background = document.getElementById("game-screen");
            window.__uiCheck(background.inert, "Configurações devem bloquear interação do fundo.");
        });
        if (width === 1280 && height === 720) await screenshot("ui-configuracoes-1280");
        await evaluate(() => {
            document.getElementById("settings-close").click();
            window.__uiClickMap(2);
            window.__uiClickMap(3);
        });
    }
    // Sem depender da câmera: menu, campo nativo e lobby nos tamanhos extremos.
    await evaluate(() => {
        window.__motionSnapshot.screen = "main";
        window.pywebview.api.connect_game = async () => ({ok: true});
    });
    await pause();
    for (const [width, height] of [[960, 720], [1366, 768], [1920, 1080]]) {
        await session.call("Emulation.setDeviceMetricsOverride", {width, height, deviceScaleFactor: 1, mobile: false});
        await pause();
        await evaluate(() => window.__uiAudit(`menu-${innerWidth}`));
        if (width === 1366) await screenshot("ui-menu-1366");
    }
    await evaluate(() => document.getElementById("connect-button").click());
    await pause();
    await session.call("Input.insertText", {text: "AB12CD345"});
    await evaluate(() => {
        const input = document.getElementById("game-code-input");
        window.__uiCheck(input.value === "AB12CD345", "Digitação nativa perdeu caracteres.");
        input.setSelectionRange(2, 4);
    });
    await session.call("Input.insertText", {text: "xy"});
    await evaluate(() => {
        const input = document.getElementById("game-code-input");
        window.__uiCheck(input.value === "ABXYCD345", "Substituir seleção deve manter restante do código.");
        window.__uiCheck(input.selectionStart === 4, "Cursor deve permanecer no ponto de edição.");
    });
    await session.call("Input.dispatchKeyEvent", {type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9});
    await session.call("Input.dispatchKeyEvent", {type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9});
    await evaluate(() => {
        window.__uiCheck(document.activeElement.id === "join-game-button", "Tab deve sair do campo e alcançar Entrar.");
        window.__uiAudit("codigo-editavel");
        window.__motionSnapshot.screen = "lobby";
        window.__motionSnapshot.lobby = window.__uiLobbySnapshot;
    });
    await pause();
    for (const [width, height] of [[960, 720], [1280, 720], [1920, 1080]]) {
        await session.call("Emulation.setDeviceMetricsOverride", {width, height, deviceScaleFactor: 1, mobile: false});
        await pause();
        await evaluate(() => {
            const details = document.getElementById("lobby-world-tuning");
            details.open = false;
            window.__uiAudit(`lobby-${innerWidth}`);
            details.open = true;
        });
        await pause();
        await evaluate(() => window.__uiAudit(`lobby-terreno-${innerWidth}`));
        if (width === 1280) await screenshot("ui-lobby-1280");
    }
    return evaluate(() => ({layouts: window.__uiChecks, nativeTextEditing: true, fullQueueAccessible: true}));
}
