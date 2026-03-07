import React from "react";
import { createRoot } from "react-dom/client";

import { Clock, type ClockProps } from "../components/Clock";
import { PIXOO_SIZE } from "../pixoo";
import { radixDark, radixLight } from "../radixColors";

declare global {
  interface Window {
    __pixooReady?: boolean;
    __pixooReadyError?: string;
  }
}

const NUMBER_KEYS: Array<keyof ClockProps> = [
  "hour",
  "minute",
  "second",
  "hourLength",
  "minuteLength",
  "secondLength",
  "markerInnerRadius",
  "markerOuterRadius",
  "markerRadius",
  "topMarkerRadius",
  "quarterMarkerRadius",
  "markerTickThickness",
  "topMarkerTickThickness",
  "quarterMarkerTickThickness",
  "hourHandThickness",
  "minuteHandThickness",
  "secondHandThickness",
  "centerDotRadius",
  "faceFade",
];

const STRING_KEYS: Array<keyof ClockProps> = [
  "handColor",
  "hourHandColor",
  "minuteHandColor",
  "secondHandColor",
  "markerColor",
  "topMarkerColor",
  "faceColor",
  "centerDotColor",
  "markerMode",
];

function defaultClockProps(theme: "dark" | "light"): ClockProps {
  const radix = theme === "light" ? radixLight : radixDark;
  return {
    showSecondHand: false,
    markerMode: "dot12",
    faceColor: radix("bronze", 1),
    markerColor: radix("bronze", 7),
    topMarkerColor: radix("bronze", 8),
    hourHandColor: radix("bronze", 10),
    minuteHandColor: radix("bronze", 11),
    secondHandColor: radix("bronze", 6),
    centerDotColor: radix("bronze", 7),
    hourLength: 20,
    minuteLength: 27,
    secondLength: 30,
    markerInnerRadius: 26,
    markerOuterRadius: 30,
    markerRadius: 1,
    topMarkerRadius: 2,
    quarterMarkerRadius: 2,
    markerTickThickness: 1,
    topMarkerTickThickness: 2,
    quarterMarkerTickThickness: 2,
    hourHandThickness: 2,
    minuteHandThickness: 2,
    secondHandThickness: 1,
    centerDotRadius: 1,
    faceFade: 1.0,
  };
}

function parseBool(raw: string | null): boolean | undefined {
  if (raw == null) {
    return undefined;
  }
  const normalized = raw.trim().toLowerCase();
  if (normalized === "true" || normalized === "1" || normalized === "yes") {
    return true;
  }
  if (normalized === "false" || normalized === "0" || normalized === "no") {
    return false;
  }
  return undefined;
}

function parseClockPropsFromQuery(): ClockProps {
  const params = new URLSearchParams(window.location.search);
  const rawTheme = (params.get("theme") || "dark").trim().toLowerCase();
  const theme: "dark" | "light" = rawTheme === "light" ? "light" : "dark";
  const props: ClockProps = { ...defaultClockProps(theme) };

  for (const key of NUMBER_KEYS) {
    const value = params.get(key);
    if (value == null) {
      continue;
    }
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      props[key] = parsed as never;
    }
  }

  for (const key of STRING_KEYS) {
    const value = params.get(key);
    if (value != null && value.length > 0) {
      props[key] = value as never;
    }
  }

  const showSecondHand = parseBool(params.get("showSecondHand"));
  if (typeof showSecondHand === "boolean") {
    props.showSecondHand = showSecondHand;
  }

  return props;
}

function markReadySoon(): void {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      window.__pixooReady = true;
    });
  });
}

function bootstrap(): void {
  window.__pixooReady = false;
  window.__pixooReadyError = undefined;
  try {
    const rootEl = document.getElementById("root");
    if (!rootEl) {
      throw new Error("Missing #root element");
    }
    const clockProps = parseClockPropsFromQuery();
    createRoot(rootEl).render(
      <div
        style={{
          width: PIXOO_SIZE,
          height: PIXOO_SIZE,
          overflow: "hidden",
          background: "#000",
        }}
      >
        <Clock {...clockProps} />
      </div>
    );
    markReadySoon();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    window.__pixooReadyError = message;
    window.__pixooReady = false;
  }
}

bootstrap();
