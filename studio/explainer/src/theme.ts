import { Easing, interpolate } from "remotion";
import "@fontsource/playfair-display/400.css";
import "@fontsource/playfair-display/400-italic.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";

export const SERIF = `"Playfair Display", Georgia, serif`;
export const SANS = `Inter, Helvetica, Arial, sans-serif`;

export const C = {
  bg0: "#05070b", bg1: "#0d1622", gold: "#d6aa5c", gold2: "#f1d39a", ice: "#9fd3ff",
  sea: "#0a1e30", land: "#33414f", landEdge: "#7d8a99", text: "#ecebe6", dim: "#8b94a3", red: "#e0533d",
};

// ease helpers: everything moves like a camera operator, never linear
export const ease = Easing.bezier(0.22, 1, 0.36, 1);
export const inOut = Easing.bezier(0.65, 0, 0.35, 1);
export const fade = (f: number, start: number, len = 10) =>
  interpolate(f, [start, start + len], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
export const rise = (f: number, start: number, dist = 40, len = 14) =>
  interpolate(f, [start, start + len], [dist, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
export const prog = (f: number, a: number, b: number, e = inOut) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: e });
