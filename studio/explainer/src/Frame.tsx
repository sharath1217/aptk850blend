import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { C, SANS, fade } from "./theme";

/** Dark documentary look: deep gradient, slow drifting light, film grain, vignette, captions. */
export const Frame: React.FC<{ children: React.ReactNode; caption?: string; dur: number }> = ({ children, caption, dur }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const u = Math.min(width, height) / 1080;
  const drift = interpolate(f, [0, dur], [-4, 4]);
  const sentences: string[] = (caption || "").match(/[^.!?]+[.!?]+/g) || (caption ? [caption] : []);
  const total = sentences.reduce((a, s) => a + s.length, 0) || 1;
  let acc = 0, current = "";
  for (const s of sentences) {
    const a = (acc / total) * dur, b = ((acc + s.length) / total) * dur;
    if (f >= a && f < b) current = s.trim();
    acc += s.length;
  }
  const out = interpolate(f, [dur - 10, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at ${50 + drift}% 40%, ${C.bg1} 0%, ${C.bg0} 70%)`, overflow: "hidden" }}>
      <AbsoluteFill style={{ opacity: Math.min(fade(f, 0, 12), out) }}>{children}</AbsoluteFill>
      {/* film grain */}
      <AbsoluteFill style={{ opacity: 0.07, mixBlendMode: "screen" }}>
        <svg width="100%" height="100%"><filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={f % 60} /></filter>
          <rect width="100%" height="100%" filter="url(#g)" /></svg>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.75) 100%)" }} />
      {current && (
        <div style={{ position: "absolute", left: "8%", right: "8%", bottom: height > width ? "14%" : "6%", textAlign: "center",
          fontFamily: SANS, fontSize: 30 * u * (height > width ? 1.7 : 1), fontWeight: height > width ? 700 : 500, lineHeight: 1.35, color: C.text,
          textShadow: "0 2px 12px rgba(0,0,0,0.9)", opacity: out }}>{current}</div>
      )}
    </AbsoluteFill>
  );
};
