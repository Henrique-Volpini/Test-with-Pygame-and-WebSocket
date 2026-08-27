import {bindPrimaryAction, byId} from "../shared/runtime.js";

const MENU_VIEWS = new Set(["main", "host", "connect", "game"]);

export function createMenu({callBridge, requestView}) {
    const menuScreen = byId("menu-screen");
    const mainMenu = byId("main-menu");
    const hostMenu = byId("host-menu");
    const connectMenu = byId("connect-menu");
    const disposers = [];
    let activeView = "main";

    function listen(target, type, listener, options) {
        target.addEventListener(type, listener, options);
        disposers.push(() => target.removeEventListener(type, listener, options));
    }

    function createTextField(
        inputId,
        displayId,
        placeholder,
        allowedCharacter,
        limit,
        handlers = {},
    ) {
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

        listen(input, "focus", refresh);
        listen(input, "blur", refresh);
        listen(input, "pointerdown", (event) => {
            if (event.button !== 0) {
                event.preventDefault();
            }
        });
        listen(input, "paste", (event) => event.preventDefault());
        listen(input, "drop", (event) => event.preventDefault());
        listen(input, "keydown", (event) => {
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

            if (
                event.ctrlKey ||
                event.metaKey ||
                event.altKey ||
                event.key.length !== 1
            ) {
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
            cancel: () => requestView("main"),
        },
    );

    function show(view) {
        if (!MENU_VIEWS.has(view)) {
            return;
        }

        activeView = view;
        menuScreen.hidden = view === "game";
        mainMenu.hidden = view !== "main";
        hostMenu.hidden = view !== "host";
        connectMenu.hidden = view !== "connect";

        if (view !== "host") {
            worldSizeField.blur();
        }
        if (view !== "connect") {
            gameCodeField.blur();
        }
    }

    listen(menuScreen, "pointerdown", (event) => {
        if (event.button !== 0) {
            return;
        }
        if (
            activeView === "host" &&
            !byId("world-size-field").contains(event.target)
        ) {
            worldSizeField.blur();
        } else if (
            activeView === "connect" &&
            !byId("game-code-field").contains(event.target)
        ) {
            gameCodeField.blur();
        }
    });

    listen(document, "keydown", (event) => {
        if (event.code === "F11") {
            event.preventDefault();
            if (!event.repeat) {
                void callBridge("toggle_fullscreen");
            }
            return;
        }

        const noModifiers = !event.ctrlKey && !event.metaKey && !event.altKey;
        if (activeView === "main" && event.code === "KeyF" && noModifiers) {
            event.preventDefault();
            if (!event.repeat) {
                void callBridge("toggle_fullscreen");
            }
        }
    });

    disposers.push(bindPrimaryAction(byId("host-button"), () => {
        worldSizeField.clear();
        requestView("host");
        window.requestAnimationFrame(() => worldSizeField.focus());
    }));

    disposers.push(bindPrimaryAction(byId("connect-button"), () => {
        gameCodeField.clear();
        requestView("connect");
        window.requestAnimationFrame(() => gameCodeField.focus());
    }));

    disposers.push(bindPrimaryAction(byId("exit-button"), () => {
        void callBridge("close_window");
    }));

    disposers.push(bindPrimaryAction(byId("fullscreen-button"), () => {
        void callBridge("toggle_fullscreen");
    }));

    disposers.push(bindPrimaryAction(byId("start-host-button"), () => {
        void hostGame();
    }));

    return {
        show,
        dispose() {
            while (disposers.length > 0) {
                disposers.pop()();
            }
        },
    };
}
