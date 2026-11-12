// Render one still from the middle of every scene (quick visual check).  node stills.mjs <comp> <outdir> [browser]
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "fs";
const [comp = "Explainer", out = "out/stills", browser] = process.argv.slice(2);
const ep = JSON.parse(fs.readFileSync(process.env.EPISODE || "episodes/titanic.json"));
const serveUrl = await bundle({ entryPoint: "src/index.ts" });
const inputProps = comp === "Short" ? { ep, pick: ep.short, hook: ep.short_hook } : { ep };
const c = await selectComposition({ serveUrl, id: comp, inputProps, browserExecutable: browser });
fs.mkdirSync(out, { recursive: true });
const framesOf = (s) => s.frames || Math.round((s.narration.split(" ").length / 2.4 + 1.2) * 30);
const list = comp === "Short" ? ep.short.map((i) => ep.scenes[i]) : ep.scenes;
let at = comp === "Short" ? 75 : 0;
const shots = comp === "Short" ? [40] : [];
for (const s of list) { shots.push(at + Math.round(framesOf(s) * 0.62)); at += framesOf(s); }
for (const [k, frame] of shots.entries()) {
  await renderStill({ composition: c, serveUrl, frame, inputProps, output: `${out}/${String(k).padStart(2, "0")}.png`, browserExecutable: browser, scale: 0.5 });
}
console.log("stills:", shots.length);
