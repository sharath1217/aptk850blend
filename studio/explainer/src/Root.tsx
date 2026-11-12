import React from "react";
import { AbsoluteFill, Audio, Composition, Sequence, staticFile, useCurrentFrame, interpolate } from "remotion";
import { Frame } from "./Frame";
import { Title, Ship, MapScene, Counter, Bars, Facts, Clock, Timeline, Quote, Outro, Depth } from "./scenes";
import { C, SERIF, SANS, fade } from "./theme";
import sample from "../episodes/titanic.json";

const FPS = 30;
const SCENES: Record<string, React.FC<any>> = { title: Title, ship: Ship, map: MapScene, counter: Counter, bars: Bars,
  facts: Facts, clock: Clock, timeline: Timeline, quote: Quote, outro: Outro, depth: Depth };
const framesOf = (s: any) => s.frames || Math.round((s.narration.split(" ").length / 2.4 + 1.2) * FPS);

const Film: React.FC<{ ep: any; pick?: number[]; hook?: string }> = ({ ep, pick, hook }) => {
  const scenes = (pick ? pick.map((i) => ({ ...ep.scenes[i], idx: i })) : ep.scenes.map((s: any, i: number) => ({ ...s, idx: i })));
  let at = hook ? 75 : 0;
  return (
    <AbsoluteFill style={{ background: C.bg0 }}>
      {hook && <Sequence durationInFrames={75}><Hook text={hook} /></Sequence>}
      {scenes.map((s: any) => {
        const d = framesOf(s); const from = at; at += d; const Comp = SCENES[s.type];
        return (
          <Sequence key={s.idx} from={from} durationInFrames={d}>
            <Frame caption={s.narration} dur={d}><Comp {...s} dur={d} /></Frame>
            {s.audio && <Audio src={staticFile(`audio/s${s.idx}.mp3`)} />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const Hook: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: C.bg0, alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 8%" }}>
    <div style={{ fontFamily: SERIF, fontSize: 92, color: C.text, opacity: fade(f, 0, 12), transform: `scale(${interpolate(f, [0, 75], [1.1, 1])})` }}>{text}</div>
    <div style={{ fontFamily: SANS, fontSize: 34, letterSpacing: 8, color: C.gold, marginTop: 40, opacity: fade(f, 20) }}>TITANIC · 1912</div>
  </AbsoluteFill>;
};

const total = (ep: any, pick?: number[], hook?: boolean) =>
  (pick ? pick.map((i) => ep.scenes[i]) : ep.scenes).reduce((a: number, s: any) => a + framesOf(s), hook ? 75 : 0);

export const Root: React.FC = () => (
  <>
    <Composition id="Explainer" component={Film as any} fps={FPS} width={1920} height={1080} durationInFrames={total(sample)}
      defaultProps={{ ep: sample }} calculateMetadata={({ props }: any) => ({ durationInFrames: total(props.ep) })} />
    <Composition id="Short" component={Film as any} fps={FPS} width={1080} height={1920} durationInFrames={total(sample, sample.short, true)}
      defaultProps={{ ep: sample, pick: sample.short, hook: sample.short_hook }}
      calculateMetadata={({ props }: any) => ({ durationInFrames: total(props.ep, props.pick, true) })} />
  </>
);
