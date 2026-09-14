// O canvas lê os mesmos tokens CSS dos menus. Valores são armazenados para
// evitar leituras de estilo durante a renderização de cada tile/unidade.
export function readThemeColors() {
    const style = getComputedStyle(document.documentElement);
    const cache = new Map();
    return (name) => {
        if (!cache.has(name)) {
            const value = style.getPropertyValue(`--${name}`).trim();
            if (!value) throw new Error(`Cor ausente em theme.css: ${name}`);
            cache.set(name, value);
        }
        return cache.get(name);
    };
}

const colorChannels = new Map();

function parseRgbChannels(color) {
    const value = String(color).trim();
    if (colorChannels.has(value)) return colorChannels.get(value);

    const hex = value.match(/^#([\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$/i)?.[1];
    if (hex) {
        const expanded = hex.length <= 4
            ? [...hex].map((part) => `${part}${part}`).join("")
            : hex;
        const channels = expanded.slice(0, 6).match(/.{2}/g)
            .map((part) => parseInt(part, 16));
        colorChannels.set(value, channels);
        return channels;
    }

    const rgb = value.match(
        /^rgba?\(\s*([\d.]+)(%)?[,\s]+([\d.]+)(%)?[,\s]+([\d.]+)(%)?/i,
    );
    if (rgb) {
        const channels = [[rgb[1], rgb[2]], [rgb[3], rgb[4]], [rgb[5], rgb[6]]]
            .map(([part, percentage]) => {
                const numeric = Number(part) * (percentage ? 2.55 : 1);
                return Math.max(0, Math.min(255, Math.round(numeric)));
            });
        colorChannels.set(value, channels);
        return channels;
    }

    const srgb = value.match(
        /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/i,
    );
    if (srgb) {
        const channels = srgb.slice(1, 4)
            .map((part) => Math.max(0, Math.min(255, Math.round(Number(part) * 255))));
        colorChannels.set(value, channels);
        return channels;
    }

    // Resolve nomes, color-mix() e aliases var() com o mesmo motor CSS da UI.
    if (typeof document !== "undefined") {
        const probe = document.createElement("span");
        probe.style.color = value;
        if (probe.style.color) {
            probe.hidden = true;
            document.documentElement.append(probe);
            const resolved = getComputedStyle(probe).color;
            probe.remove();
            if (resolved && resolved !== value) {
                const channels = parseRgbChannels(resolved);
                colorChannels.set(value, channels);
                return channels;
            }
        }
    }
    throw new TypeError(`Cor CSS inválida para transparência: ${value}`);
}

export function withAlpha(color, opacity) {
    const rgb = parseRgbChannels(color);
    return `rgba(${rgb.join(", ")}, ${Math.max(0, Math.min(1, opacity))})`;
}
