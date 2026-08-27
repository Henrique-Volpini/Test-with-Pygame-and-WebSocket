export function createBridge() {
    let ready = Boolean(window.pywebview && window.pywebview.api);
    const readyListeners = new Set();

    function signalReady() {
        ready = true;
        for (const listener of readyListeners) {
            listener();
        }
    }

    window.addEventListener("pywebviewready", signalReady);

    async function call(method, ...args) {
        const api = window.pywebview && window.pywebview.api;
        if (!api || typeof api[method] !== "function") {
            return null;
        }

        ready = true;
        try {
            return await api[method](...args);
        } catch (_error) {
            return null;
        }
    }

    function onReady(listener) {
        readyListeners.add(listener);
        if (ready || Boolean(window.pywebview && window.pywebview.api)) {
            ready = true;
            queueMicrotask(listener);
        }
        return () => readyListeners.delete(listener);
    }

    function dispose() {
        window.removeEventListener("pywebviewready", signalReady);
        readyListeners.clear();
        ready = false;
    }

    return {
        call,
        onReady,
        isReady: () => ready,
        dispose,
    };
}
