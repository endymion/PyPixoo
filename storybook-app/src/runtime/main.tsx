import React from "react";
import { createRoot } from "react-dom/client";

import { Clock, type ClockProps } from "../components/Clock";
import { PIXOO_SIZE } from "../pixoo";
import { radixDark, radixLight } from "../radixColors";

declare global {
  interface Window {
    __pixooReady?: boolean;
    __pixooReadyError?: string;
    __pixooApplyClockArgs?: (raw: Record<string, unknown>) => Promise<void>;
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
    faceColor: theme === "light" ? radix("sand", 8) : "#000000",
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

function parseBoolUnknown(raw: unknown): boolean | undefined {
  if (typeof raw === "boolean") {
    return raw;
  }
  if (typeof raw === "number") {
    return raw !== 0;
  }
  if (typeof raw === "string") {
    return parseBool(raw);
  }
  return undefined;
}

function parseNumberUnknown(raw: unknown): number | undefined {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  if (typeof raw === "string") {
    const parsed = Number(raw);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function parseStringUnknown(raw: unknown): string | undefined {
  if (typeof raw === "string" && raw.length > 0) {
    return raw;
  }
  return undefined;
}

function normalizeTheme(raw: unknown, fallback: "dark" | "light"): "dark" | "light" {
  if (typeof raw === "string" && raw.trim().toLowerCase() === "light") {
    return "light";
  }
  return fallback;
}

function buildClockPropsFromRaw(
  raw: Record<string, unknown>,
  fallbackTheme: "dark" | "light",
): { props: ClockProps; theme: "dark" | "light" } {
  const theme = normalizeTheme(raw.theme, fallbackTheme);
  const props: ClockProps = { ...defaultClockProps(theme) };

  for (const key of NUMBER_KEYS) {
    const parsed = parseNumberUnknown(raw[key]);
    if (parsed !== undefined) {
      props[key] = parsed as never;
    }
  }

  for (const key of STRING_KEYS) {
    const parsed = parseStringUnknown(raw[key]);
    if (parsed !== undefined) {
      props[key] = parsed as never;
    }
  }

  const showSecondHand = parseBoolUnknown(raw.showSecondHand);
  if (typeof showSecondHand === "boolean") {
    props.showSecondHand = showSecondHand;
  }

  return { props, theme };
}

function parseClockPropsFromQuery(): ClockProps {
  const params = new URLSearchParams(window.location.search);
  const raw: Record<string, unknown> = {};
  for (const [key, value] of params.entries()) {
    raw[key] = value;
  }
  return buildClockPropsFromRaw(raw, "dark").props;
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
    const root = createRoot(rootEl);
    const initialProps = parseClockPropsFromQuery();
    const initialTheme = normalizeTheme(
      new URLSearchParams(window.location.search).get("theme"),
      "dark",
    );
    let activeTheme: "dark" | "light" = initialTheme;

    const renderClock = (clockProps: ClockProps): void => {
      root.render(
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
    };

    renderClock(initialProps);
    window.__pixooApplyClockArgs = async (raw: Record<string, unknown>) => {
      const next = buildClockPropsFromRaw(raw, activeTheme);
      activeTheme = next.theme;
      renderClock(next.props);
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => resolve());
        });
      });
    };
    markReadySoon();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    window.__pixooReadyError = message;
    window.__pixooReady = false;
  }
}

bootstrap();
