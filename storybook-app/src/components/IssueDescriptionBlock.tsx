import React from "react";
import { Row } from "./Row";

const DEFAULT_ROW_HEIGHT = 6;

export interface IssueDescriptionBlockProps {
  y: number;
  lines: string[];
  rowCount?: number;
  rowHeight?: number;
  textColor: string;
  backgroundColor?: string;
  fontFamily?: string;
  fontSize?: number;
  lineHeightPx?: number;
  textOffsetY?: number;
  leftPadding?: number;
}

function normalizeLines(lines: string[] | undefined, count: number): string[] {
  const base = (lines ?? []).slice(0, count);
  while (base.length < count) {
    base.push("");
  }
  return base;
}

export function IssueDescriptionBlock({
  y,
  lines,
  rowCount = 2,
  rowHeight = DEFAULT_ROW_HEIGHT,
  textColor,
  backgroundColor = "transparent",
  fontFamily = "Bytesized",
  fontSize = 8,
  lineHeightPx = 8,
  textOffsetY = 0,
  leftPadding = 1,
}: IssueDescriptionBlockProps) {
  const safeHeight = Math.max(1, Math.floor(rowHeight));
  const rows = normalizeLines(lines, rowCount);
  const rendered: React.ReactNode[] = [];
  let currentY = Math.floor(y);

  for (let i = 0; i < rows.length; i += 1) {
    const line = rows[i] || " ";
    rendered.push(
      <Row key={`issue-row-${currentY}-${i}`} y={currentY} height={safeHeight} backgroundColor={backgroundColor}>
        <div
          style={{
            paddingLeft: leftPadding,
            position: "relative",
            top: textOffsetY,
            fontFamily,
            fontSize,
            lineHeight: `${lineHeightPx}px`,
            color: textColor,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "clip",
            wordSpacing: "-2px",
          }}
        >
          {line}
        </div>
      </Row>
    );
    currentY += safeHeight;
  }

  return <>{rendered}</>;
}
