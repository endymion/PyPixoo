import React from "react";
import { PIXOO_SIZE } from "../pixoo";
import { Row } from "./Row";

export type KanbusIssueType = "task" | "bug" | "story" | "epic" | "unknown";
export type KanbusCardKind = "created" | "transition" | "comment" | "unknown";

export interface KanbusCardProps {
  idPrefix: string;
  issueType: KanbusIssueType;
  status: string;
  kind: KanbusCardKind;
  parentLines?: string[];
  issueLines: string[];
  commentLines?: string[];
}

type CardPalette = {
  header: string;
  main: string;
  dim: string;
  bg: string;
  border: string;
};

const TYPE_PALETTES: Record<KanbusIssueType, CardPalette> = {
  task: {
    header: "#5BA5FF",
    main: "#9DC9FF",
    dim: "#3B6EA8",
    bg: "#0A111B",
    border: "#2A4A6E",
  },
  bug: {
    header: "#FF6B70",
    main: "#FF9DA1",
    dim: "#A84D4F",
    bg: "#1B0A0B",
    border: "#6E2A2D",
  },
  story: {
    header: "#D2B24D",
    main: "#E6CD7A",
    dim: "#8F7837",
    bg: "#171208",
    border: "#5B4A21",
  },
  epic: {
    header: "#8F8CFF",
    main: "#B8B5FF",
    dim: "#5A58A8",
    bg: "#0D0C1A",
    border: "#3A3870",
  },
  unknown: {
    header: "#BFB79E",
    main: "#D7CFB5",
    dim: "#7F785F",
    bg: "#11100D",
    border: "#4E4A3C",
  },
};

const HEADER_HEIGHT = 8;
const BODY_TOP = HEADER_HEIGHT;
const BODY_HEIGHT = PIXOO_SIZE - BODY_TOP;
const LINE_HEIGHT = 8;

function normalizeLines(lines: string[] | undefined, count: number): string[] {
  const base = (lines ?? []).slice(0, count);
  while (base.length < count) {
    base.push("");
  }
  return base;
}

function kindRows(props: KanbusCardProps): { top: string[]; bottom: string[]; divider: boolean } {
  if (props.kind === "comment") {
    return {
      top: normalizeLines(props.issueLines, 2),
      bottom: normalizeLines(props.commentLines, 3),
      divider: false,
    };
  }
  if (props.kind === "unknown") {
    return {
      top: [],
      bottom: normalizeLines(props.issueLines, 5),
      divider: false,
    };
  }
  const hasParent = (props.parentLines?.length ?? 0) > 0;
  if (hasParent) {
    return {
      top: normalizeLines(props.parentLines, 3),
      bottom: normalizeLines(props.issueLines, 4),
      divider: true,
    };
  }
  return {
    top: [],
    bottom: normalizeLines(props.issueLines, 7),
    divider: false,
  };
}

function Header({ parts, color }: { parts: string[]; color: string }) {
  return (
    <div
      style={{
        paddingLeft: 1,
        display: "flex",
        flexDirection: "row",
        alignItems: "center",
        fontFamily: "'Tiny5', monospace",
        fontSize: 5,
        lineHeight: "5px",
        color,
        whiteSpace: "nowrap",
      }}
    >
      {parts.map((part, index) => (
        <React.Fragment key={`${part}-${index}`}>
          {index > 0 ? <span style={{ display: "inline-block", width: 3 }} /> : null}
          <span>{part}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

function BodyRow({
  y,
  text,
  color,
}: {
  y: number;
  text: string;
  color: string;
}) {
  return (
    <Row y={y} height={LINE_HEIGHT} backgroundColor="transparent">
      <div
        style={{
          paddingLeft: 1,
          fontFamily: "'Tiny5', monospace",
          fontSize: 5,
          lineHeight: "5px",
          color,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "clip",
        }}
      >
        {text || " "}
      </div>
    </Row>
  );
}

export function KanbusCard(props: KanbusCardProps) {
  const palette = TYPE_PALETTES[props.issueType] ?? TYPE_PALETTES.unknown;
  const { top, bottom, divider } = kindRows(props);
  const headerParts = [props.idPrefix.toUpperCase(), props.issueType.toUpperCase(), props.status.toUpperCase()];

  const rows: React.ReactNode[] = [];
  let y = BODY_TOP;

  for (const line of top) {
    rows.push(<BodyRow key={`top-${y}`} y={y} text={line} color={palette.dim} />);
    y += LINE_HEIGHT;
  }

  if (divider) {
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

  for (const line of bottom) {
    if (y >= PIXOO_SIZE) {
      break;
    }
    rows.push(<BodyRow key={`bottom-${y}`} y={y} text={line} color={palette.main} />);
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
        backgroundColor={palette.bg}
        bottomBorderPx={1}
        bottomBorderColor={palette.border}
      >
        <Header parts={headerParts} color={palette.header} />
      </Row>
      <Row y={BODY_TOP} height={BODY_HEIGHT} backgroundColor={palette.bg}>
        {rows}
      </Row>
    </div>
  );
}

