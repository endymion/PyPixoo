import React from "react";
import { PIXOO_SIZE } from "../pixoo";

export type ClockMarkerMode =
  | "dot12"
  | "dots_quarters"
  | "ticks_all"
  | "dots_all_thick_quarters"
  | "ticks_all_thick_quarters";

export interface ClockProps {
  /** Time in [0, 1); 0 = 12:00, 0.25 = 3:00. Used when hour/minute not set (single hand). */
  t?: number;
  /** Hour (0–11). With minute, draws hour + minute hands. */
  hour?: number;
  /** Minute (0–59). With hour, draws hour + minute hands. */
  minute?: number;
  /** Second (0–59). Optional third hand; shown when showSecondHand is true. */
  second?: number;
  /** Whether to show the second hand (default: true). */
  showSecondHand?: boolean;
  /** Hand color (CSS color) for hour and minute hands. */
  handColor?: string;
  /** Second hand color (CSS color). */
  secondHandColor?: string;
  /** Marker color (CSS color). */
  markerColor?: string;
  /** Face background (CSS color) */
  faceColor?: string;
  /** Clock face marker style. */
  markerMode?: ClockMarkerMode;
}

const TAU = 2 * Math.PI;
const CX = PIXOO_SIZE / 2;
const CY = PIXOO_SIZE / 2;
const MARKER_ANGLES = Array.from({ length: 12 }, (_, i) => (i / 12) * TAU);
const MARKER_OUTWARD_OFFSET = 1.0;

/** Angle 0 = 12 o'clock, clockwise in radians. */
function angleToXY(angleRad: number, length: number) {
  const a = angleRad - Math.PI / 2;
  return { x: CX + length * Math.cos(a), y: CY + length * Math.sin(a) };
}

function isQuarterHour(index: number) {
  return index % 3 === 0;
}

/**
 * Clock for Pixoo 64. Either:
 * - Set t (0–1) for a single sweeping hand (animation).
 * - Set hour (0–11) + minute (0–59) for real time with hour and minute hands; optional second (0–59).
 */
export function Clock({
  t = 0,
  hour,
  minute,
  second,
  showSecondHand = true,
  handColor = "white",
  secondHandColor = "rgba(255,100,100,0.9)",
  markerColor = "rgba(255,255,255,0.75)",
  faceColor = "black",
  markerMode = "ticks_all_thick_quarters",
}: ClockProps) {
  const useTimeMode = typeof hour === "number" && typeof minute === "number";

  const radius = (PIXOO_SIZE / 2) * 0.95;
  const hourLength = radius * 0.55;
  const minuteLength = radius * 0.85;
  const secondLength = radius * 0.88;

  const hourAngle =
    useTimeMode
      ? ((hour % 12) + minute / 60 + (second ?? 0) / 3600) / 12 * TAU
      : t * TAU;
  const minuteAngle =
    useTimeMode
      ? (minute + (second ?? 0) / 60) / 60 * TAU
      : t * TAU;
  const secondAngle =
    showSecondHand && typeof second === "number"
      ? second / 60 * TAU
      : null;

  const hourEnd = angleToXY(hourAngle, hourLength);
  const minuteEnd = angleToXY(minuteAngle, minuteLength);
  const secondEnd =
    secondAngle !== null ? angleToXY(secondAngle, secondLength) : null;

  const markerOuter = Math.min(CX - 0.25, (radius * 0.96) + MARKER_OUTWARD_OFFSET);
  const markerInner = Math.min(CX - 0.25, (radius * 0.82) + MARKER_OUTWARD_OFFSET);
  const markerDot = Math.min(CX - 0.25, (radius * 0.90) + MARKER_OUTWARD_OFFSET);

  const markers = MARKER_ANGLES.map((angle, i) => {
    const quarter = isQuarterHour(i);
    const key = `marker-${i}`;

    if (markerMode === "dot12" && i !== 0) {
      return null;
    }
    if (markerMode === "dots_quarters" && !quarter) {
      return null;
    }

    const shouldDrawDot =
      markerMode === "dot12" ||
      (markerMode === "dots_quarters" && quarter) ||
      markerMode === "dots_all_thick_quarters";

    if (shouldDrawDot) {
      const pos = angleToXY(angle, markerDot);
      const dotRadius =
        markerMode === "dots_all_thick_quarters"
          ? quarter
            ? 1.25
            : 0.8
          : 1.2;
      return <circle key={key} cx={pos.x} cy={pos.y} r={dotRadius} fill={markerColor} />;
    }

    const thickTick = markerMode === "ticks_all_thick_quarters" && quarter;
    const start = angleToXY(angle, markerOuter);
    const end = angleToXY(angle, markerInner);
    return (
      <line
        key={key}
        x1={start.x}
        y1={start.y}
        x2={end.x}
        y2={end.y}
        stroke={markerColor}
        strokeWidth={thickTick ? 1.9 : 1.2}
        strokeLinecap="round"
      />
    );
  });

  return (
    <svg
      width={PIXOO_SIZE}
      height={PIXOO_SIZE}
      viewBox={`0 0 ${PIXOO_SIZE} ${PIXOO_SIZE}`}
      style={{ display: "block", background: faceColor }}
    >
      {markers}
      {useTimeMode ? (
        <>
          <line
            x1={CX}
            y1={CY}
            x2={hourEnd.x}
            y2={hourEnd.y}
            stroke={handColor}
            strokeWidth={2.5}
            strokeLinecap="round"
          />
          <line
            x1={CX}
            y1={CY}
            x2={minuteEnd.x}
            y2={minuteEnd.y}
            stroke={handColor}
            strokeWidth={1.5}
            strokeLinecap="round"
          />
          {secondEnd !== null && (
            <line
              x1={CX}
              y1={CY}
              x2={secondEnd.x}
              y2={secondEnd.y}
              stroke={secondHandColor}
              strokeWidth={1}
              strokeLinecap="round"
            />
          )}
        </>
      ) : (
        <line
          x1={CX}
          y1={CY}
          x2={minuteEnd.x}
          y2={minuteEnd.y}
          stroke={handColor}
          strokeWidth={2}
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}
