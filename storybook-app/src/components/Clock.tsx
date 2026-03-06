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
  /** Hour hand color (CSS color). Falls back to handColor. */
  hourHandColor?: string;
  /** Minute hand color (CSS color). Falls back to handColor. */
  minuteHandColor?: string;
  /** Second hand color (CSS color). */
  secondHandColor?: string;
  /** Marker color (CSS color). */
  markerColor?: string;
  /** Optional override for the top-center marker (12 o'clock). */
  topMarkerColor?: string;
  /** Face background (CSS color) */
  faceColor?: string;
  /** Clock face marker style. */
  markerMode?: ClockMarkerMode;
  /** Intensity multiplier for markers + hands (0.0 to 1.0). */
  faceFade?: number;
  /** Hour hand length in pixels from center. */
  hourLength?: number;
  /** Minute hand length in pixels from center. */
  minuteLength?: number;
  /** Second hand length in pixels from center. */
  secondLength?: number;
  /** Marker inner radius in pixels from center (for tick modes). */
  markerInnerRadius?: number;
  /** Marker outer radius in pixels from center. */
  markerOuterRadius?: number;
  /** Base marker dot radius in pixels. */
  markerRadius?: number;
  /** 12 o'clock marker dot radius in pixels. */
  topMarkerRadius?: number;
  /** Quarter marker dot radius in pixels (dots_all_thick_quarters). */
  quarterMarkerRadius?: number;
  /** Base tick thickness in pixels. */
  markerTickThickness?: number;
  /** 12 o'clock tick thickness in pixels. */
  topMarkerTickThickness?: number;
  /** Quarter tick thickness in pixels (ticks_all_thick_quarters). */
  quarterMarkerTickThickness?: number;
  /** Hour hand stroke thickness in pixels. */
  hourHandThickness?: number;
  /** Minute hand stroke thickness in pixels. */
  minuteHandThickness?: number;
  /** Second hand stroke thickness in pixels. */
  secondHandThickness?: number;
  /** Center dot radius in pixels. */
  centerDotRadius?: number;
  /** Center dot color. */
  centerDotColor?: string;
}

const TAU = 2 * Math.PI;
const CX = PIXOO_SIZE / 2;
const CY = PIXOO_SIZE / 2;
const MARKER_ANGLES = Array.from({ length: 12 }, (_, i) => (i / 12) * TAU);

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
  hourHandColor,
  minuteHandColor,
  secondHandColor = "rgba(255,100,100,0.9)",
  markerColor = "rgba(255,255,255,0.75)",
  topMarkerColor,
  faceColor = "black",
  markerMode = "ticks_all_thick_quarters",
  faceFade = 1.0,
  hourLength = 17,
  minuteLength = 26,
  secondLength = 28,
  markerInnerRadius = 26,
  markerOuterRadius = 30,
  markerRadius = 0.8,
  topMarkerRadius = 1.25,
  quarterMarkerRadius = 1.25,
  markerTickThickness = 1.2,
  topMarkerTickThickness = 1.9,
  quarterMarkerTickThickness = 1.9,
  hourHandThickness = 2.5,
  minuteHandThickness = 1.5,
  secondHandThickness = 1,
  centerDotRadius = 1,
  centerDotColor,
}: ClockProps) {
  const useTimeMode = typeof hour === "number" && typeof minute === "number";
  const clampedFaceFade = Math.max(0, Math.min(1, faceFade));
  const hourStroke = hourHandColor ?? handColor ?? "white";
  const minuteStroke = minuteHandColor ?? handColor ?? "white";
  const centerFill = centerDotColor ?? minuteStroke;

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

  const markerOuter = markerOuterRadius;
  const markerInner = markerInnerRadius;
  const markerDot = markerOuterRadius;

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
      const markerStrokeColor = i === 0 ? (topMarkerColor ?? markerColor) : markerColor;

    if (shouldDrawDot) {
      const pos = angleToXY(angle, markerDot);
      const dotRadius =
        markerMode === "dots_all_thick_quarters"
          ? i === 0
            ? topMarkerRadius
            : quarter
              ? quarterMarkerRadius
              : markerRadius
          : i === 0
            ? topMarkerRadius
            : markerRadius;
      return <circle key={key} cx={pos.x} cy={pos.y} r={dotRadius} fill={markerStrokeColor} />;
    }

    const tickThickness =
      markerMode === "ticks_all_thick_quarters"
        ? i === 0
          ? topMarkerTickThickness
          : quarter
            ? quarterMarkerTickThickness
            : markerTickThickness
        : i === 0
          ? topMarkerTickThickness
          : markerTickThickness;
    const start = angleToXY(angle, markerOuter);
    const end = angleToXY(angle, markerInner);
    return (
      <line
        key={key}
        x1={start.x}
        y1={start.y}
        x2={end.x}
        y2={end.y}
        stroke={markerStrokeColor}
        strokeWidth={tickThickness}
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
      <g opacity={clampedFaceFade}>
        {markers}
        {useTimeMode ? (
          <>
            <line
              x1={CX}
              y1={CY}
              x2={hourEnd.x}
              y2={hourEnd.y}
              stroke={hourStroke}
              strokeWidth={hourHandThickness}
              strokeLinecap="round"
            />
            <line
              x1={CX}
              y1={CY}
              x2={minuteEnd.x}
              y2={minuteEnd.y}
              stroke={minuteStroke}
              strokeWidth={minuteHandThickness}
              strokeLinecap="round"
            />
            {secondEnd !== null && (
              <line
                x1={CX}
                y1={CY}
                x2={secondEnd.x}
                y2={secondEnd.y}
                stroke={secondHandColor}
                strokeWidth={secondHandThickness}
                strokeLinecap="round"
              />
            )}
            <circle cx={CX} cy={CY} r={centerDotRadius} fill={centerFill} />
          </>
        ) : (
          <line
            x1={CX}
            y1={CY}
            x2={minuteEnd.x}
            y2={minuteEnd.y}
            stroke={minuteStroke}
            strokeWidth={minuteHandThickness}
            strokeLinecap="round"
          />
        )}
      </g>
    </svg>
  );
}
