export const LOGICAL_WIDTH = 1280;
export const LOGICAL_HEIGHT = 960;

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
        viewport.style.transform = (
            `scale(${renderWidth / LOGICAL_WIDTH}, ${renderHeight / LOGICAL_HEIGHT})`
        );
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
