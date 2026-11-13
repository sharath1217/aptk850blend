import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { geoMercator, geoPath, geoGraticule10 } from "d3-geo";
import { feature } from "topojson-client";
import land50 from "world-atlas/land-50m.json";
import { C, SERIF, SANS, fade, rise, prog, ease, inOut } from "./theme";

// vertical (Shorts/Reels) gets ~40% bigger elements: they must read on a phone at a glance
const useU = () => { const { width, height } = useVideoConfig(); const tall = height > width;
  return { u: (Math.min(width, height) / 1080) * (tall ? 1.4 : 1), w: width, h: height, tall }; };
const Kicker: React.FC<{ t: string; at?: number }> = ({ t, at = 0 }) => {
  const f = useCurrentFrame(); const { u } = useU();
  return <div style={{ fontFamily: SANS, letterSpacing: 8 * u, fontSize: 22 * u, color: C.gold, opacity: fade(f, at), fontWeight: 600 }}>{t}</div>;
};

// ---------------------------------------------------------------- title
export const Title: React.FC<any> = ({ kicker, title, subtitle }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const spacing = interpolate(f, [0, 150], [60, 24], { extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <Kicker t={kicker} at={8} />
      <div style={{ fontFamily: SERIF, fontSize: Math.min(190 * u, 1700 / Math.max(6, title.length) * (u / 1.4)), color: C.text, letterSpacing: spacing * u * 0.6, marginTop: 20 * u,
        opacity: fade(f, 14, 40), transform: `scale(${interpolate(f, [0, 200], [1.08, 1])})` }}>{title}</div>
      <div style={{ width: interpolate(prog(f, 40, 90), [0, 1], [0, 420]) * u, height: 2 * u, background: C.gold, margin: `${26 * u}px 0` }} />
      <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 54 * u, color: C.gold2, opacity: fade(f, 60, 30), transform: `translateY(${rise(f, 60)}px)` }}>{subtitle}</div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- ship (line-art Titanic, side view)
const Titanic: React.FC<{ flood?: number; scrape?: number }> = ({ flood = 0, scrape = 0 }) => {
  const hull = "M20,170 L60,232 L940,232 Q975,232 985,200 L1000,170 Z";
  const comp = Array.from({ length: 16 }, (_, i) => 70 + i * 54);
  return (
    <svg viewBox="0 0 1020 260" width="100%" height="100%">
      <defs><clipPath id="hullclip"><path d={hull} /></clipPath>
        <linearGradient id="hullg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1a1d22" /><stop offset="0.72" stopColor="#0e1013" /><stop offset="0.72" stopColor="#5a1f17" /><stop offset="1" stopColor="#3b130e" /></linearGradient></defs>
      <line x1="120" y1="18" x2="120" y2="170" stroke={C.dim} strokeWidth="2" /><line x1="860" y1="22" x2="860" y2="170" stroke={C.dim} strokeWidth="2" />
      <line x1="120" y1="20" x2="30" y2="168" stroke={C.dim} strokeWidth="0.7" /><line x1="860" y1="24" x2="992" y2="168" stroke={C.dim} strokeWidth="0.7" />
      <line x1="120" y1="20" x2="860" y2="24" stroke={C.dim} strokeWidth="0.5" strokeOpacity="0.5" />
      <path d="M150,170 L150,140 L870,140 L870,170 Z" fill="#e9e4d8" /><path d="M210,140 L210,122 L800,122 L800,140 Z" fill="#dcd6c8" />
      {[300, 420, 540, 660].map((x, i) => (
        <g key={i} transform={`translate(${x},122) skewX(-10)`}><rect x="0" y="-78" width="34" height="78" fill="#c99a52" /><rect x="0" y="-78" width="34" height="14" fill="#111" /></g>
      ))}
      <path d={hull} fill="url(#hullg)" />
      {Array.from({ length: 34 }, (_, i) => <circle key={i} cx={90 + i * 25} cy={186} r="2.2" fill="#f4e3b0" opacity="0.8" />)}
      <g clipPath="url(#hullclip)">
        {comp.map((x, i) => <line key={i} x1={x} y1="170" x2={x} y2="232" stroke="#ffffff" strokeOpacity={flood ? 0.35 : 0} strokeDasharray="4 4" />)}
        {[0, 1, 2, 3, 4].map((i) => {
          const x0 = 1000 - (i + 1) * 54 - 16; const level = Math.max(0, Math.min(1, flood * 5 - i * 0.6));
          return <rect key={i} x={x0} y={232 - 62 * level} width="54" height={62 * level} fill={C.ice} opacity="0.55" />;
        })}
      </g>
      {scrape > 0 && <path d={`M985,215 L${985 - 320 * scrape},222`} stroke={C.red} strokeWidth="4" strokeLinecap="round" />}
    </svg>
  );
};

export const Ship: React.FC<any> = ({ mode, labels = [], dur }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const sinking = mode === "sinking";
  const tilt = sinking ? interpolate(f, [0, dur], [3, 16], { easing: inOut }) : mode === "impact" ? Math.sin(f / 4) * prog(f, 20, 30) * (1 - prog(f, 30, 60)) * 1.2 : 0;
  const drop = sinking ? interpolate(f, [0, dur], [10, 120]) : 0;
  const camX = mode === "intro" ? interpolate(f, [0, dur], [40, -40]) : 0;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", width: tall ? "125%" : "86%", height: 330 * u, top: tall ? "34%" : "26%",
        transform: `translate(${camX * u}px, ${drop * u}px) rotate(${tilt}deg)`, transformOrigin: "85% 70%" }}>
        <Titanic flood={mode === "compartments" ? prog(f, 20, dur - 30, ease) : 0} scrape={mode === "impact" ? prog(f, 25, 70, ease) : 0} />
      </div>
      {/* sea surface */}
      <div style={{ position: "absolute", left: 0, right: 0, top: tall ? `calc(34% + ${232 / 260 * 330 * u}px)` : `calc(26% + ${232 / 260 * 330 * u - 4}px)`, bottom: 0,
        background: `linear-gradient(${C.sea}ee, #02060a)`, borderTop: `1px solid ${C.ice}55` }} />
      {mode === "impact" && <svg style={{ position: "absolute", right: tall ? "2%" : "4%", top: tall ? "38%" : "30%", width: 260 * u, height: 260 * u, opacity: fade(f, 0, 20) }} viewBox="0 0 100 100">
        <path d="M10,95 L28,40 L42,52 L55,18 L70,46 L90,95 Z" fill="#cfe6f5" opacity="0.9" /></svg>}
      <div style={{ position: "absolute", left: "8%", right: "8%", top: tall ? "64%" : "68%", display: "flex", gap: 40 * u, justifyContent: "center", flexWrap: "wrap" }}>
        {labels.map((l: string, i: number) => (
          <div key={i} style={{ fontFamily: SANS, fontSize: 28 * u, color: i === 0 && mode !== "intro" ? C.gold2 : C.text, opacity: fade(f, 20 + i * 18),
            transform: `translateY(${rise(f, 20 + i * 18, 20)}px)`, borderLeft: `3px solid ${C.gold}`, paddingLeft: 14 * u }}>{l}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- map with route
const PLACES: Record<string, [number, number]> = {
  Southampton: [-1.40, 50.90], Cherbourg: [-1.62, 49.64], Queenstown: [-8.30, 51.85], "New York": [-74.0, 40.7],
  Collision: [-49.95, 41.73], Carpathia: [-50.0, 40.7],
};
const VIEWS: Record<string, { c: [number, number]; s: number; z2: number }> = {
  voyage: { c: [-28, 46], s: 1.0, z2: 1.0 }, rescue: { c: [-50, 41.4], s: 6.5, z2: 7.5 }, wreck: { c: [-49.95, 41.73], s: 7, z2: 14 },
};
const LAND: any = feature(land50 as any, (land50 as any).objects.land);

export const MapScene: React.FC<any> = ({ view, route, dur }) => {
  const f = useCurrentFrame(); const { w, h, u } = useU();
  const v = VIEWS[view] || VIEWS.voyage;
  const zoom = interpolate(f, [0, dur], [v.s, v.z2], { easing: inOut });
  const proj = geoMercator().center(v.c).scale((Math.min(w, h) * 1.15) * zoom).translate([w / 2, h / 2]);
  const path = geoPath(proj);
  const pts = route.map((n: string) => proj(PLACES[n]) as [number, number]);
  const lineD = pts.map((p: number[], i: number) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join("");
  const p = prog(f, 15, dur * 0.75);
  let len = 0; const segs: number[] = [];
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); segs.push(d); len += d; }
  let rem = p * len, pos = pts[0];
  for (let i = 1; i < pts.length; i++) {
    if (rem <= segs[i - 1]) { const t = rem / (segs[i - 1] || 1); pos = [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t]; break; }
    rem -= segs[i - 1]; pos = pts[i];
  }
  const pulse = 1 + 0.35 * Math.sin(f / 6);
  return (
    <AbsoluteFill>
      <svg width={w} height={h}>
        <rect width={w} height={h} fill={C.sea} opacity="0.55" />
        <path d={path(geoGraticule10()) || ""} fill="none" stroke={C.ice} strokeOpacity={0.08} strokeWidth={1} />
        <path d={path(LAND) || ""} fill={C.land} stroke={C.landEdge} strokeWidth={1.2} />
        {view === "voyage" && <path d={lineD} fill="none" stroke={C.gold} strokeWidth={3 * u} strokeDasharray={len} strokeDashoffset={len * (1 - p)} />}
        {view === "voyage" && <path d={`M${pts[pts.length - 1][0]},${pts[pts.length - 1][1]} L${(proj(PLACES["New York"]) as any)[0]},${(proj(PLACES["New York"]) as any)[1]}`}
          stroke={C.dim} strokeWidth={2 * u} strokeDasharray={`${8 * u} ${8 * u}`} opacity={fade(f, dur * 0.7)} fill="none" />}
        {view === "rescue" && <path d={lineD} fill="none" stroke={C.ice} strokeWidth={3 * u} strokeDasharray={len} strokeDashoffset={len * (1 - p)} />}
        {route.map((n: string, i: number) => { const q = proj(PLACES[n]) as [number, number];
          const show = view !== "voyage" || p * len >= segs.slice(0, i).reduce((a, b) => a + b, 0) - 1;
          const isX = n === "Collision";
          return show && <g key={n}>
            <circle cx={q[0]} cy={q[1]} r={(isX ? 9 * pulse : 6) * u} fill={isX ? C.red : C.gold} opacity={isX ? 0.9 : 1} />
            <text x={q[0] + 14 * u} y={q[1] - 12 * u} fill={C.text} fontFamily={SANS} fontSize={24 * u}>{isX ? (view === "wreck" ? "Wreck · 3,800 m deep" : "Collision · 41.7°N 49.9°W") : n}</text>
          </g>; })}
        {view !== "wreck" && <circle cx={pos[0]} cy={pos[1]} r={7 * u} fill={view === "rescue" ? C.ice : C.text} />}
        {view === "rescue" && <text x={pts[0][0] - 20 * u} y={pts[0][1] + 40 * u} fill={C.ice} fontFamily={SANS} fontSize={24 * u}>~58 nautical miles</text>}
      </svg>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- big number
export const Counter: React.FC<any> = ({ value, label, sub, dur }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const n = Math.round(value * prog(f, 4, Math.min(40, dur * 0.4), ease));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ fontFamily: SERIF, fontSize: Math.min(260, 1500 / Math.max(4, n.toLocaleString("en-US").length)) * u * (tall ? 0.8 : 1), color: C.gold2, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{n.toLocaleString("en-US")}</div>
      <div style={{ fontFamily: SANS, fontSize: 44 * u, color: C.text, marginTop: 20 * u, opacity: fade(f, 30), letterSpacing: 2 * u }}>{label}</div>
      <div style={{ fontFamily: SANS, fontSize: 30 * u, color: C.dim, marginTop: 10 * u, opacity: fade(f, 50) }}>{sub}</div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- comparison bars
export const Bars: React.FC<any> = ({ title, items }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const max = Math.max(...items.map((i: any) => i.value));
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: `0 ${tall ? 8 : 14}%` }}>
      <Kicker t={title.toUpperCase()} />
      {items.map((it: any, i: number) => {
        const g = prog(f, 8 + i * 15, 40 + i * 15, ease);
        return <div key={i} style={{ marginTop: 50 * u }}>
          <div style={{ fontFamily: SANS, fontSize: 32 * u, color: C.text, marginBottom: 12 * u, opacity: fade(f, 15 + i * 25) }}>{it.label}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 24 * u }}>
            <div style={{ height: 46 * u, width: `${(it.value / max) * 78 * g}%`, background: i ? `linear-gradient(90deg, ${C.ice}, #5f9fd0)` : `linear-gradient(90deg, ${C.gold}, ${C.gold2})` }} />
            <div style={{ fontFamily: SERIF, fontSize: 56 * u, color: i ? C.ice : C.gold2, fontVariantNumeric: "tabular-nums" }}>{it.prefix || ""}{Math.round(it.value * g).toLocaleString("en-US")}{it.suffix || ""}</div>
          </div>
        </div>;
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- facts list
export const Facts: React.FC<any> = ({ title, items }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: `0 ${tall ? 8 : 14}%` }}>
      <div style={{ fontFamily: SERIF, fontSize: 70 * u, color: C.text, opacity: fade(f, 0), marginBottom: 40 * u }}>{title}</div>
      {items.map((t: string, i: number) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 26 * u, margin: `${18 * u}px 0`, opacity: fade(f, 8 + i * 14), transform: `translateX(${rise(f, 8 + i * 14, 60)}px)` }}>
          <div style={{ width: 14 * u, height: 14 * u, transform: "rotate(45deg)", background: C.gold }} />
          <div style={{ fontFamily: SANS, fontSize: 40 * u, color: C.text }}>{t}</div>
        </div>
      ))}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- clock
export const Clock: React.FC<any> = ({ time, label }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const [hh, mm] = time.split(":").map(Number);
  const spin = interpolate(prog(f, 0, 45, ease), [0, 1], [-60, 0]);
  const ma = (mm + spin) * 6, ha = ((hh % 12) + (mm + spin) / 60) * 30;
  const R = 230 * u;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <svg width={R * 2.2} height={R * 2.2} viewBox="-110 -110 220 220">
        <circle r="100" fill="none" stroke={C.gold} strokeWidth="1.5" opacity="0.8" />
        {Array.from({ length: 60 }, (_, i) => <line key={i} x1="0" y1={i % 5 ? -94 : -88} x2="0" y2="-99" stroke={C.text} strokeWidth={i % 5 ? 0.6 : 1.6} transform={`rotate(${i * 6})`} />)}
        <line x1="0" y1="8" x2="0" y2="-55" stroke={C.text} strokeWidth="4" strokeLinecap="round" transform={`rotate(${ha})`} />
        <line x1="0" y1="10" x2="0" y2="-85" stroke={C.gold2} strokeWidth="2.5" strokeLinecap="round" transform={`rotate(${ma})`} />
        <circle r="4" fill={C.gold} />
      </svg>
      <div style={{ fontFamily: SERIF, fontSize: 96 * u, color: C.text, marginTop: 10 * u, fontVariantNumeric: "tabular-nums" }}>{time}</div>
      <div style={{ fontFamily: SANS, fontSize: 36 * u, letterSpacing: 10 * u, color: C.red, opacity: fade(f, 40) * (0.75 + 0.25 * Math.sin(f / 5)), fontWeight: 700 }}>{label}</div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- timeline
export const Timeline: React.FC<any> = ({ events, dur }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const p = prog(f, 10, dur * 0.85);
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: `0 ${tall ? 10 : 10}%` }}>
      <div style={{ position: "relative", height: tall ? 900 * u : 300 * u }}>
        <div style={{ position: "absolute", left: tall ? 30 * u : 0, top: tall ? 0 : 140 * u, width: tall ? 3 * u : `${p * 100}%`, height: tall ? `${p * 100}%` : 3 * u, background: C.gold }} />
        {events.map((e: any, i: number) => {
          const at = i / Math.max(1, events.length - 1); const on = p >= at - 0.001;
          const style: React.CSSProperties = tall ? { position: "absolute", top: `${at * 92}%`, left: 0 } : { position: "absolute", left: `${at * 88}%`, top: 70 * u };
          return <div key={i} style={{ ...style, opacity: on ? 1 : 0.15 }}>
            <div style={{ fontFamily: SERIF, fontSize: 56 * u, color: on ? C.gold2 : C.dim, marginLeft: tall ? 70 * u : 0 }}>{e.time}</div>
            {!tall && <div style={{ width: 22 * u, height: 22 * u, borderRadius: 99, background: on ? C.gold : C.dim, margin: `${16 * u}px 0` }} />}
            <div style={{ fontFamily: SANS, fontSize: 30 * u, color: C.text, marginLeft: tall ? 70 * u : 0, maxWidth: 300 * u }}>{e.label}</div>
          </div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- quote
export const Quote: React.FC<any> = ({ text, by }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const words = text.split(" ");
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", padding: "0 12%" }}>
      <div style={{ fontFamily: SERIF, fontSize: 150 * u, color: C.gold, lineHeight: 0.6, opacity: fade(f, 0) }}>“</div>
      <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 64 * u, color: C.text, lineHeight: 1.3 }}>
        {words.map((w: string, i: number) => <span key={i} style={{ opacity: fade(f, 4 + i * 2, 8) }}>{w} </span>)}
      </div>
      <div style={{ fontFamily: SANS, fontSize: 28 * u, color: C.dim, marginTop: 40 * u, opacity: fade(f, 20 + words.length * 4) }}>— {by}</div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- outro
export const Outro: React.FC<any> = ({ title, lines }) => {
  const f = useCurrentFrame(); const { u } = useU();
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ fontFamily: SERIF, fontSize: Math.min(140 * u, 1500 / Math.max(6, title.length)), letterSpacing: 12 * u, color: C.text, opacity: fade(f, 0, 40) }}>{title}</div>
      <div style={{ display: "flex", gap: 50 * u, marginTop: 30 * u, flexWrap: "wrap", justifyContent: "center" }}>
        {lines.map((l: string, i: number) => <div key={i} style={{ fontFamily: SANS, fontSize: 30 * u, color: C.gold2, opacity: fade(f, 30 + i * 20) }}>{l}</div>)}
      </div>
      <div style={{ fontFamily: SANS, fontSize: 26 * u, letterSpacing: 8 * u, color: C.dim, marginTop: 90 * u, opacity: fade(f, 100) }}>GETYR STUDIO</div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- depth gauge
export const Depth: React.FC<any> = ({ depth = 3800, compare, dur }) => {
  const f = useCurrentFrame(); const { u, h } = useU();
  const p = prog(f, 10, dur * 0.7, ease);
  const top = 0.14 * h, bottom = 0.68 * h, y = top + (bottom - top) * p;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 0, right: 0, top, bottom: 0, background: `linear-gradient(${C.sea}, #010307 85%)` }} />
      <div style={{ position: "absolute", left: "50%", top, width: 2 * u, height: y - top, background: C.gold }} />
      <div style={{ position: "absolute", left: "50%", top: y, transform: "translate(-50%,-50%)", width: 22 * u, height: 22 * u, borderRadius: 99, background: C.gold2 }} />
      <div style={{ position: "absolute", left: "53%", top: y - 40 * u, fontFamily: SERIF, fontSize: 84 * u, color: C.text, fontVariantNumeric: "tabular-nums" }}>
        {Math.round(depth * p).toLocaleString("en-US")} m</div>
      <div style={{ position: "absolute", left: "53%", top: y + 50 * u, fontFamily: SANS, fontSize: 30 * u, color: C.dim, opacity: fade(f, dur * 0.7) }}>{compare}</div>
      <div style={{ position: "absolute", left: "8%", top: top - 50 * u, fontFamily: SANS, fontSize: 26 * u, letterSpacing: 6 * u, color: C.ice }}>SEA LEVEL</div>
    </AbsoluteFill>
  );
};

// ================================================================ electronics scenes
const Electrons: React.FC<{ d: string; on: number; color?: string; n?: number; speed?: number }> = ({ d, on, color = C.ice, n = 14, speed = 0.012 }) => {
  const f = useCurrentFrame();
  return <g opacity={on}>{Array.from({ length: n }, (_, i) => (
    <circle key={i} r="5" fill={color} style={{ offsetPath: `path('${d}')`, offsetDistance: `${((i / n + f * speed) % 1) * 100}%` } as any} />))}</g>;
};

// water pipe with a tap: the transistor analogy
export const Valve: React.FC<any> = ({ labels = [], dur }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const open = interpolate(f, [0, dur * 0.2, dur * 0.35, dur * 0.6, dur * 0.75, dur], [0, 0, 1, 1, 0, 0], { easing: inOut });
  const pipe = "M80,260 L920,260";
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1000 520" style={{ width: tall ? "96%" : "70%" }}>
        <rect x="80" y="225" width="840" height="70" rx="12" fill="#13202e" stroke={C.dim} />
        <g transform={`translate(500,260)`}>
          <rect x="-40" y={-35 + open * 60} width="80" height="70" fill="#2b3b4f" stroke={C.gold} />
          <rect x="-8" y={-150} width="16" height={115 + open * 60} fill={C.gold} />
          <rect x="-60" y={-170 + open * 60} width="120" height="20" rx="8" fill={C.gold2} />
        </g>
        <Electrons d={pipe} on={open} n={22} speed={0.01} />
        <text x="500" y="70" textAnchor="middle" fill={C.gold2} fontFamily={SANS} fontSize="30">{open > 0.5 ? "SMALL PUSH → BIG FLOW" : "NO PUSH → NO FLOW"}</text>
        {labels.map((l: string, i: number) => <text key={i} x={[120, 500, 880][i]} y="370" textAnchor="middle" fill={C.text} fontFamily={SANS} fontSize="28">{l}</text>)}
      </svg>
    </AbsoluteFill>
  );
};

// silicon crystal + doping
export const Silicon: React.FC<any> = ({ dur }) => {
  const f = useCurrentFrame(); const { tall } = useU();
  const dope = prog(f, dur * 0.35, dur * 0.55);
  const cells = [];
  for (let r = 0; r < 5; r++) for (let c = 0; c < 9; c++) {
    const P = (r === 1 && c === 2) || (r === 3 && c === 6), B = (r === 2 && c === 4);
    cells.push({ x: 120 + c * 95, y: 90 + r * 85, P, B });
  }
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1000 560" style={{ width: tall ? "98%" : "72%" }}>
        {cells.map((p, i) => <g key={i}>
          {i % 9 !== 8 && <line x1={p.x} y1={p.y} x2={p.x + 95} y2={p.y} stroke={C.dim} strokeOpacity="0.4" />}
          {i < 36 && <line x1={p.x} y1={p.y} x2={p.x} y2={p.y + 85} stroke={C.dim} strokeOpacity="0.4" />}
          <circle cx={p.x} cy={p.y} r="22" fill={(p.P || p.B) && dope > 0.5 ? (p.P ? "#3b6ea5" : "#a5623b") : "#1d2a38"} stroke={C.landEdge} />
          <text x={p.x} y={p.y + 7} textAnchor="middle" fill={C.text} fontFamily={SANS} fontSize="18">{(p.P || p.B) && dope > 0.5 ? (p.P ? "P" : "B") : "Si"}</text>
          {p.P && dope > 0.5 && <circle cx={p.x + 34 + 10 * Math.sin(f / 5)} cy={p.y - 30} r="7" fill={C.ice} />}
          {p.B && dope > 0.5 && <circle cx={p.x + 34} cy={p.y - 30} r="7" fill="none" stroke={C.gold2} strokeWidth="3" />}
        </g>)}
        <text x="500" y="535" textAnchor="middle" fill={C.gold2} fontFamily={SANS} fontSize="28" opacity={dope}>Phosphorus adds a free electron · Boron leaves a "hole"</text>
      </svg>
    </AbsoluteFill>
  );
};

// MOSFET cross-section: gate voltage pulls electrons into a channel
export const Mosfet: React.FC<any> = ({ dur, state }) => {
  const f = useCurrentFrame(); const { tall } = useU();
  const on = state === "off" ? 0 : interpolate(f, [0, dur * 0.25, dur * 0.4, dur * 0.8, dur * 0.9], [0, 0, 1, 1, 0], { extrapolateRight: "clamp", easing: inOut });
  const chan = "M260,300 L740,300";
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1000 600" style={{ width: tall ? "98%" : "70%" }}>
        <rect x="120" y="270" width="760" height="260" fill="#3a2a22" stroke={C.landEdge} />
        <text x="500" y="500" textAnchor="middle" fill={C.dim} fontFamily={SANS} fontSize="24">silicon (p-type)</text>
        {[[150, "SOURCE"], [690, "DRAIN"]].map(([x, t]: any) => <g key={t}>
          <rect x={x} y="270" width="160" height="90" fill="#24456b" /><rect x={x + 40} y="200" width="80" height="70" fill="#9aa4ad" />
          <text x={x + 80} y="185" textAnchor="middle" fill={C.text} fontFamily={SANS} fontSize="26">{t}</text></g>)}
        <rect x="320" y="250" width="360" height="20" fill="#d9e2ea" opacity="0.6" />
        <rect x="330" y="190" width="340" height="60" fill={on > 0.5 ? C.gold : "#6d7782"} />
        <text x="500" y="175" textAnchor="middle" fill={on > 0.5 ? C.gold2 : C.text} fontFamily={SANS} fontSize="28">GATE {on > 0.5 ? "+ voltage ON" : "off"}</text>
        <rect x="310" y="278" width="380" height="40" fill={C.ice} opacity={0.25 * on} />
        <Electrons d={chan} on={on} n={16} speed={0.015} />
        <text x="500" y="580" textAnchor="middle" fill={C.gold2} fontFamily={SANS} fontSize="28" opacity={on}>a channel opens → current flows</text>
      </svg>
    </AbsoluteFill>
  );
};

// simple circuit: battery, transistor, LED; the transistor switches the LED
export const Circuit: React.FC<any> = ({ dur }) => {
  const f = useCurrentFrame(); const { tall } = useU();
  const on = Math.floor((f / Math.max(1, dur)) * 6) % 2 === 1 ? 1 : 0;
  const loop = "M150,120 L850,120 L850,460 L150,460 Z";
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1000 600" style={{ width: tall ? "98%" : "66%" }}>
        <path d={loop} fill="none" stroke={C.dim} strokeWidth="5" />
        <rect x="120" y="250" width="60" height="90" fill="#1d2a38" stroke={C.gold} /><text x="150" y="380" textAnchor="middle" fill={C.text} fontFamily={SANS} fontSize="22">battery</text>
        <circle cx="500" cy="120" r="45" fill={on ? "#ffd27a" : "#2a2f36"} style={{ filter: on ? "drop-shadow(0 0 30px #ffcc66)" : "none" }} />
        <text x="500" y="200" textAnchor="middle" fill={C.text} fontFamily={SANS} fontSize="24">LED</text>
        <rect x="800" y="250" width="100" height="100" rx="12" fill="#1d2a38" stroke={on ? C.gold : C.dim} strokeWidth="4" />
        <text x="850" y="308" textAnchor="middle" fill={on ? C.gold2 : C.text} fontFamily={SANS} fontSize="22">transistor</text>
        <line x1="900" y1="300" x2="980" y2="300" stroke={on ? C.gold : C.dim} strokeWidth="4" />
        <text x="960" y="280" textAnchor="end" fill={on ? C.gold2 : C.dim} fontFamily={SANS} fontSize="20">{on ? "signal: 1" : "signal: 0"}</text>
        <Electrons d={loop} on={on} n={26} speed={0.008} />
      </svg>
    </AbsoluteFill>
  );
};

// binary: switches = 1s and 0s
export const Binary: React.FC<any> = ({ dur }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const n = tall ? 6 : 8; const word = "01001000";
  const shown = Math.floor(prog(f, 5, dur * 0.5) * n);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ display: "flex", gap: 22 * u }}>
        {Array.from({ length: n }, (_, i) => { const bit = word[i % 8] === "1"; const vis = i < shown;
          return <div key={i} style={{ width: 90 * u, height: 140 * u, borderRadius: 14 * u, border: `3px solid ${bit && vis ? C.gold : C.landEdge}`,
            background: bit && vis ? "rgba(214,170,92,0.18)" : "transparent", display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: SERIF, fontSize: 80 * u, color: bit ? C.gold2 : C.dim, opacity: vis ? 1 : 0.15 }}>{vis ? (bit ? 1 : 0) : ""}</div>; })}
      </div>
      <div style={{ fontFamily: SANS, fontSize: 36 * u, color: C.text, marginTop: 50 * u, opacity: fade(f, dur * 0.55) }}>
        {tall ? "ON = 1 · OFF = 0" : "8 switches → 01001000 → the letter “H”"}</div>
    </AbsoluteFill>
  );
};
