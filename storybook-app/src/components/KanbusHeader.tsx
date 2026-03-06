import React from "react";

export interface KanbusHeaderProps {
  idPrefix: string;
  issueType: string;
  status: string;
  color: string;
  idColor?: string;
  issueTypeColor?: string;
  statusColor?: string;
  leftPadPx?: number;
  gapPx?: number;
}

export function KanbusHeader({
  idPrefix,
  issueType,
  status,
  color,
  idColor,
  issueTypeColor,
  statusColor,
  leftPadPx = 1,
  gapPx = 3,
}: KanbusHeaderProps) {
  const WORD_SPACE_PX = 2;
  const TOKEN_GAP_PX = gapPx;
  const parts = [
    idPrefix.toUpperCase().replace(/\s+/g, " ").trim(),
    issueType.toUpperCase().replace(/\s+/g, " ").trim(),
    status.toUpperCase().replace(/\s+/g, " ").trim(),
  ];
  const tokenColors = [idColor ?? color, issueTypeColor ?? color, statusColor ?? color];

  const renderToken = (token: string, keyPrefix: string) => {
    const nodes: React.ReactNode[] = [];
    let prevWasLetter = false;
    for (let i = 0; i < token.length; i += 1) {
      const ch = token[i];
      if (/\s/.test(ch)) {
        prevWasLetter = false;
        nodes.push(
          <span
            key={`${keyPrefix}-ws-${i}`}
            style={{ display: "inline-block", width: WORD_SPACE_PX, height: 8 }}
          />
        );
      } else {
        if (prevWasLetter) {
          nodes.push(
            <span
              key={`${keyPrefix}-gap-${i}`}
              style={{ display: "inline-block", width: 1, height: 8 }}
            />
          );
        }
        nodes.push(
          <span
            key={`${keyPrefix}-ch-${i}`}
            style={{
              display: "inline-block",
              width: 3,
              textAlign: "left",
            }}
          >
            {ch}
          </span>
        );
        prevWasLetter = true;
      }
    }
    return nodes;
  };

  return (
    <div
      style={{
        paddingLeft: leftPadPx,
        paddingTop: 1,
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        fontFamily: "Bytesized",
        fontSize: 8,
        lineHeight: "8px",
        color,
        whiteSpace: "nowrap",
        letterSpacing: 0,
        fontKerning: "none",
        fontVariantLigatures: "none",
        height: "100%",
        boxSizing: "border-box",
        position: "relative",
        top: -2,
      }}
    >
      {parts.map((part, index) => (
        <span
          key={`${part}-${index}`}
          style={{
            display: "inline-flex",
            flexDirection: "row",
            alignItems: "center",
            marginLeft: index > 0 ? TOKEN_GAP_PX : 0,
            color: tokenColors[index],
          }}
        >
          {renderToken(part, `part-${index}`)}
        </span>
      ))}
    </div>
  );
}
