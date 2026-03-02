/**
 * Stripe pattern: vertical strips with every-other pixel on;
 * one blank column between strips. For screen/alignment testing.
 */
import React from "react";
import { PIXOO_SIZE } from "../pixoo";

export function StripePattern() {
  const pixels: { x: number; y: number }[] = [];
  for (let x = 0; x < PIXOO_SIZE; x += 2) {
    for (let y = 0; y < PIXOO_SIZE; y += 2) {
      pixels.push({ x, y });
    }
  }
  return (
    <svg
      width={PIXOO_SIZE}
      height={PIXOO_SIZE}
      viewBox={`0 0 ${PIXOO_SIZE} ${PIXOO_SIZE}`}
      style={{ display: "block", background: "#000" }}
    >
      {pixels.map(({ x, y }, i) => (
        <rect key={i} x={x} y={y} width={1} height={1} fill="#fff" />
      ))}
    </svg>
  );
}
