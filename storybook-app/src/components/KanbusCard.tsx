import React from "react";
import { PIXOO_SIZE } from "../pixoo";
import { Row } from "./Row";
import { KanbusHeader } from "./KanbusHeader";
import { IssueDescriptionBlock } from "./IssueDescriptionBlock";

export type KanbusIssueType = "task" | "bug" | "story" | "epic" | "unknown";
export type KanbusCardKind = "created" | "transition" | "comment" | "unknown";
export type KanbusParentType = "epic" | "initiative" | "unknown";

export interface KanbusCardProps {
  idPrefix: string;
  issueType: KanbusIssueType;
  status: string;
  kind: KanbusCardKind;
  parentType?: KanbusParentType;
  parentLines?: string[];
  issueLines: string[];
  commentLines?: string[];
}

type CardPalette = {
  header: string;
  main: string;
  dim: string;
  bg: string;
  headerBg: string;
  border: string;
};

const TYPE_PALETTES: Record<KanbusIssueType, CardPalette> = {
  task: {
    header: "#5BA5FF",
    main: "#9DC9FF",
    dim: "#3B6EA8",
    bg: "#0A111B",
    headerBg: "#1E3E68",
    border: "#2A4A6E",
  },
  bug: {
    header: "#FF6B70",
    main: "#FF9DA1",
    dim: "#A84D4F",
    bg: "#1B0A0B",
    headerBg: "#3A1C1F",
    border: "#6E2A2D",
  },
  story: {
    header: "#D2B24D",
    main: "#E6CD7A",
    dim: "#8F7837",
    bg: "#171208",
    headerBg: "#3A321B",
    border: "#5B4A21",
  },
  epic: {
    header: "#8F8CFF",
    main: "#B8B5FF",
    dim: "#5A58A8",
    bg: "#0D0C1A",
    headerBg: "#2B2858",
    border: "#3A3870",
  },
  unknown: {
    header: "#BFB79E",
    main: "#D7CFB5",
    dim: "#7F785F",
    bg: "#11100D",
    headerBg: "#33312B",
    border: "#4E4A3C",
  },
};

const HEADER_HEIGHT = 6;
const BODY_TOP = HEADER_HEIGHT;
const LINE_HEIGHT = 6;
const COMMENT_TEXT_COLOR = "#E8E0CB";
const BODY_MAX_CHARS = 17;
const STATUS_LIGHTEN_AMOUNT = 0.2;

function lightenHex(hex: string, amount: number): string {
  if (!hex.startsWith("#") || hex.length !== 7) {
    return hex;
  }
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const mix = (channel: number) => Math.min(255, Math.round(channel + (255 - channel) * amount));
  const out = [
    mix(r).toString(16).padStart(2, "0"),
    mix(g).toString(16).padStart(2, "0"),
    mix(b).toString(16).padStart(2, "0"),
  ].join("");
  return `#${out}`;
}

function normalizeLines(lines: string[] | undefined, count: number): string[] {
  const base = (lines ?? []).slice(0, count);
  while (base.length < count) {
    base.push("");
  }
  return base;
}

function wrapLines(lines: string[] | undefined, count: number, maxChars = BODY_MAX_CHARS): string[] {
  const wrapped: string[] = [];
  const source = lines ?? [];
  for (const rawLine of source) {
    const normalized = rawLine.replace(/\s+/g, " ").trim();
    if (!normalized) {
      if (wrapped.length < count) {
        wrapped.push("");
      }
      continue;
    }

    const words = normalized.split(" ");
    let current = "";

    for (const word of words) {
      if (word.length > maxChars) {
        if (current) {
          wrapped.push(current);
          current = "";
          if (wrapped.length >= count) {
            return wrapped.slice(0, count);
          }
        }
        let remaining = word;
        while (remaining.length > maxChars) {
          wrapped.push(remaining.slice(0, maxChars));
          remaining = remaining.slice(maxChars);
          if (wrapped.length >= count) {
            return wrapped.slice(0, count);
          }
        }
        current = remaining;
        continue;
      }

      if (!current) {
        current = word;
        continue;
      }

      if ((current.length + 1 + word.length) <= maxChars) {
        current = `${current} ${word}`;
      } else {
        wrapped.push(current);
        if (wrapped.length >= count) {
          return wrapped.slice(0, count);
        }
        current = word;
      }
    }

    if (current) {
      wrapped.push(current);
      if (wrapped.length >= count) {
        return wrapped.slice(0, count);
      }
    }
  }

  while (wrapped.length < count) {
    wrapped.push("");
  }
  return wrapped.slice(0, count);
}

function kindRows(props: KanbusCardProps): { top: string[]; bottom: string[]; divider: boolean } {
  const hasParent = (props.parentLines?.length ?? 0) > 0;
  if (props.kind === "comment") {
    if (hasParent) {
      return {
        top: [],
        bottom: wrapLines(props.commentLines, 5),
        divider: false,
      };
    }
    return {
      top: wrapLines(props.issueLines, 2),
      bottom: wrapLines(props.commentLines, 7),
      divider: false,
    };
  }
  if (props.kind === "unknown") {
    if (hasParent) {
      return {
        top: [],
        bottom: wrapLines(props.issueLines?.slice(2), 6),
        divider: false,
      };
    }
    return {
      top: [],
      bottom: wrapLines(props.issueLines, 8),
      divider: false,
    };
  }
  if (hasParent) {
    return {
      top: [],
      bottom: wrapLines(props.issueLines?.slice(2), 6),
      divider: false,
    };
  }
  return {
    top: wrapLines(props.issueLines, 2),
    bottom: wrapLines(props.issueLines?.slice(2), 8),
    divider: false,
  };
}

export function KanbusCard(props: KanbusCardProps) {
  const palette = TYPE_PALETTES[props.issueType] ?? TYPE_PALETTES.unknown;
  const { top, bottom, divider } = kindRows(props);
  const headerParts = [props.idPrefix.toUpperCase(), props.issueType.toUpperCase(), props.status.toUpperCase()];
  const statusColor =
    props.kind === "transition" || props.kind === "created"
      ? lightenHex(palette.main, STATUS_LIGHTEN_AMOUNT)
      : palette.main;
  const hasParent = (props.parentLines?.length ?? 0) > 0;
  const parentTextColor =
    props.parentType === "initiative"
      ? "#A86BB4"
      : props.parentType === "epic"
        ? "#7470D8"
        : palette.dim;
  const parentRowBg =
    props.parentType === "initiative"
      ? "#3B1E3F"
      : props.parentType === "epic"
        ? "#22254A"
        : "#1A1A1A";
  const issueRowBg = palette.headerBg;
  const issueTextColor = palette.dim;

  const rows: React.ReactNode[] = [];
  let y = BODY_TOP;

  if (hasParent) {
    rows.push(
      <IssueDescriptionBlock
        key={`parent-block-${y}`}
        y={y}
        lines={wrapLines(props.parentLines, 2)}
        rowCount={2}
        rowHeight={LINE_HEIGHT}
        textColor={parentTextColor}
        backgroundColor={parentRowBg}
        textOffsetY={-1}
      />
    );
    y += 2 * LINE_HEIGHT;

    rows.push(
      <IssueDescriptionBlock
        key={`issue-block-${y}`}
        y={y}
        lines={wrapLines(props.issueLines, 2)}
        rowCount={2}
        rowHeight={LINE_HEIGHT}
        textColor={issueTextColor}
        backgroundColor={issueRowBg}
        textOffsetY={-1}
      />
    );
    y += 2 * LINE_HEIGHT;
  } else if (props.kind === "comment" || props.kind === "created" || props.kind === "transition") {
    rows.push(
      <IssueDescriptionBlock
        key={`issue-block-${y}`}
        y={y}
        lines={wrapLines(props.issueLines, 2)}
        rowCount={2}
        rowHeight={LINE_HEIGHT}
        textColor={issueTextColor}
        backgroundColor={issueRowBg}
        textOffsetY={-1}
      />
    );
    y += 2 * LINE_HEIGHT;
  } else {
    for (const line of top) {
      rows.push(
        <IssueDescriptionBlock
          key={`top-${y}`}
          y={y}
          lines={[line]}
          rowCount={1}
          rowHeight={LINE_HEIGHT}
          textColor={parentTextColor}
          backgroundColor={"transparent"}
        />
      );
      y += LINE_HEIGHT;
    }
  }

  if (divider && !hasParent) {
    rows.push(
      <Row
        key={`divider-${y}`}
        y={y}
        height={1}
        backgroundColor={palette.border}
      />
    );
    y += 1;
  }

  if (props.kind === "comment" && hasParent) {
    y += 1;
  }
  if (props.kind === "comment" && !hasParent) {
    y += 1;
  }

  for (const line of bottom) {
    if (y >= PIXOO_SIZE) {
      break;
    }
    const bottomTextColor = props.kind === "comment" ? COMMENT_TEXT_COLOR : palette.main;
    const bottomBackgroundColor =
      props.kind === "comment" ? "transparent" : issueRowBg;
    rows.push(
      <IssueDescriptionBlock
        key={`bottom-${y}`}
        y={y}
        lines={[line]}
        rowCount={1}
        rowHeight={LINE_HEIGHT}
        textColor={bottomTextColor}
        backgroundColor={bottomBackgroundColor}
      />
    );
    y += LINE_HEIGHT;
  }

  return (
    <div
      style={{
        width: PIXOO_SIZE,
        height: PIXOO_SIZE,
        background: palette.bg,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <Row
        y={0}
        height={HEADER_HEIGHT}
        backgroundColor={palette.headerBg}
      >
        <KanbusHeader
          idPrefix={headerParts[0]}
          issueType={headerParts[1]}
          status={headerParts[2]}
          color={palette.main}
          statusColor={statusColor}
        />
      </Row>
      {rows}
    </div>
  );
}
