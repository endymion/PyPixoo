import React from "react";
import { PIXOO_SIZE } from "../pixoo";
import { Row } from "./Row";
import { KanbusHeader } from "./KanbusHeader";
import { IssueDescriptionBlock } from "./IssueDescriptionBlock";
import { radixDark, RadixBand } from "../radixColors";

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
  base: string;
  attention: string;
  dim: string;
  bg: string;
  headerBg: string;
  border: string;
};

const TYPE_BANDS: Record<KanbusIssueType, RadixBand> = {
  task: "blue",
  bug: "red",
  story: "yellow",
  epic: "indigo",
  unknown: "sand",
};

function paletteForBand(band: RadixBand): CardPalette {
  return {
    base: radixDark(band, 7),
    attention: radixDark(band, 11),
    dim: radixDark(band, 6),
    bg: radixDark(band, 1),
    headerBg: radixDark(band, 4),
    border: radixDark(band, 5),
  };
}


const HEADER_HEIGHT = 6;
const BODY_TOP = HEADER_HEIGHT;
const LINE_HEIGHT = 6;
const COMMENT_TEXT_COLOR = radixDark("sky", 11);
const BODY_MAX_CHARS = 17;

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
  const band = TYPE_BANDS[props.issueType] ?? "sand";
  const palette = paletteForBand(band);
  const { top, bottom, divider } = kindRows(props);
  const headerParts = [props.idPrefix.toUpperCase(), props.issueType.toUpperCase(), props.status.toUpperCase()];
  const headerBase = palette.base;
  const issueTypeHeader = palette.base;
  const statusColor = props.kind === "transition" ? palette.attention : palette.base;
  const idColor = radixDark(band, 8);
  const hasParent = (props.parentLines?.length ?? 0) > 0;
  const parentBand =
    props.parentType === "initiative"
      ? "plum"
      : props.parentType === "epic"
        ? "indigo"
        : band;
  const parentTextColor =
    props.parentType === "initiative" || props.parentType === "epic"
      ? radixDark(parentBand, 7)
      : palette.base;
  const bodyBg = palette.bg;
  const parentRowBg = radixDark(parentBand, 3);
  const issueRowBg = radixDark(band, 2);
  const issueTextColor = palette.base;

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
    const bottomTextColor = props.kind === "comment" ? COMMENT_TEXT_COLOR : palette.attention;
    const bottomBackgroundColor =
      props.kind === "comment" ? "transparent" : bodyBg;
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
      <Row y={0} height={HEADER_HEIGHT} backgroundColor={palette.headerBg}>
        <KanbusHeader
          idPrefix={headerParts[0]}
          issueType={headerParts[1]}
          status={headerParts[2]}
          color={headerBase}
          idColor={idColor}
          issueTypeColor={issueTypeHeader}
          statusColor={statusColor}
        />
      </Row>
      {rows}
    </div>
  );
}
