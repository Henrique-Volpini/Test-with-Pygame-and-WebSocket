export const MIN_LOGICAL_WIDTH = 1280;
export const LOGICAL_HEIGHT = 960;
export const VIEWPORT_RESIZE_EVENT = "logicalviewportresize";
export let LOGICAL_WIDTH = MIN_LOGICAL_WIDTH;

export function byId(id) {
    const element = document.getElementById(id);
    if (!element) {
        throw new Error(`Elemento obrigatório não encontrado: #${id}`);
    }
    return element;
}

export function bindPrimaryAction(element, action) {
    const onPointerDown = (event) => {
        if (event.button !== 0) {
            return;
        }
        event.preventDefault();
        action(event);
    };

    const onClick = (event) => {
        if (event.detail !== 0) {
            return;
        }
        event.preventDefault();
        action(event);
    };

    element.addEventListener("pointerdown", onPointerDown);
    element.addEventListener("click", onClick);

    return () => {
        element.removeEventListener("pointerdown", onPointerDown);
        element.removeEventListener("click", onClick);
    };
}

export function initializeViewport(viewport) {
    function fitViewport() {
        const availableWidth = Math.max(1, window.innerWidth);
        const availableHeight = Math.max(1, window.innerHeight);
        const previousLogicalWidth = LOGICAL_WIDTH;
        LOGICAL_WIDTH = Math.max(
            MIN_LOGICAL_WIDTH,
            Math.round(LOGICAL_HEIGHT * availableWidth / availableHeight),
        );

        viewport.style.setProperty("--logical-width", `${LOGICAL_WIDTH}px`);
        viewport.style.setProperty("--logical-height", `${LOGICAL_HEIGHT}px`);
        viewport.style.width = `${LOGICAL_WIDTH}px`;
        viewport.style.height = `${LOGICAL_HEIGHT}px`;

        const scale = Math.min(
            availableWidth / LOGICAL_WIDTH,
            availableHeight / LOGICAL_HEIGHT,
        );
        const renderWidth = LOGICAL_WIDTH * scale;
        const renderHeight = LOGICAL_HEIGHT * scale;
        const offsetX = (availableWidth - renderWidth) / 2;
        const offsetY = (availableHeight - renderHeight) / 2;

        viewport.style.left = `${offsetX}px`;
        viewport.style.top = `${offsetY}px`;
        viewport.style.transform = `scale(${scale})`;
        viewport.dispatchEvent(new CustomEvent(VIEWPORT_RESIZE_EVENT, {
            detail: {
                logicalWidth: LOGICAL_WIDTH,
                logicalHeight: LOGICAL_HEIGHT,
                previousLogicalWidth,
                scale,
            },
        }));
    }

    const preventDefault = (event) => event.preventDefault();

    viewport.addEventListener("contextmenu", preventDefault);
    viewport.addEventListener("dragstart", preventDefault);
    window.addEventListener("resize", fitViewport);
    fitViewport();

    return () => {
        viewport.removeEventListener("contextmenu", preventDefault);
        viewport.removeEventListener("dragstart", preventDefault);
        window.removeEventListener("resize", fitViewport);
    };
}
