export type RadixBand =
  | "blue"
  | "red"
  | "yellow"
  | "indigo"
  | "sand"
  | "plum"
  | "bronze";

type RadixScale = Record<number, string>;

const RADIX_DARK: Record<RadixBand, RadixScale> = {
  blue: {
    1: "#0d1520",
    2: "#111927",
    3: "#0d2847",
    4: "#003362",
    5: "#004074",
    6: "#104d87",
    7: "#205d9e",
    8: "#2870bd",
    9: "#0090ff",
    10: "#3b9eff",
    11: "#70b8ff",
    12: "#c2e6ff",
  },
  red: {
    1: "#191111",
    2: "#201314",
    3: "#3b1219",
    4: "#500f1c",
    5: "#611623",
    6: "#72232d",
    7: "#8c333a",
    8: "#b54548",
    9: "#e5484d",
    10: "#ec5d5e",
    11: "#ff9592",
    12: "#ffd1d9",
  },
  yellow: {
    1: "#14120b",
    2: "#1b180f",
    3: "#2d2305",
    4: "#362b00",
    5: "#433500",
    6: "#524202",
    7: "#665417",
    8: "#836a21",
    9: "#ffe629",
    10: "#ffff57",
    11: "#f5e147",
    12: "#f6eeb4",
  },
  indigo: {
    1: "#11131f",
    2: "#141726",
    3: "#182449",
    4: "#1d2e62",
    5: "#253974",
    6: "#304384",
    7: "#3a4f97",
    8: "#435db1",
    9: "#3e63dd",
    10: "#5472e4",
    11: "#9eb1ff",
    12: "#d6e1ff",
  },
  sand: {
    1: "#111110",
    2: "#191918",
    3: "#222221",
    4: "#2a2a28",
    5: "#31312e",
    6: "#3b3a37",
    7: "#494844",
    8: "#62605b",
    9: "#6f6d66",
    10: "#7c7b74",
    11: "#b5b3ad",
    12: "#eeeeec",
  },
  plum: {
    1: "#181118",
    2: "#201320",
    3: "#351a35",
    4: "#451d47",
    5: "#512454",
    6: "#5e3061",
    7: "#734079",
    8: "#92549c",
    9: "#ab4aba",
    10: "#b658c4",
    11: "#e796f3",
    12: "#f4d4f4",
  },
  bronze: {
    1: "#141110",
    2: "#1c1917",
    3: "#262220",
    4: "#302a27",
    5: "#3b3330",
    6: "#493e3a",
    7: "#5a4c47",
    8: "#6f5f58",
    9: "#a18072",
    10: "#ae8c7e",
    11: "#d4b3a5",
    12: "#ede0d9",
  },
};

const RADIX_LIGHT: Record<RadixBand, RadixScale> = {
  blue: {
    1: "#fbfdff",
    2: "#f4faff",
    3: "#e6f4fe",
    4: "#d5efff",
    5: "#c2e5ff",
    6: "#acd8fc",
    7: "#8ec8f6",
    8: "#5eb1ef",
    9: "#0090ff",
    10: "#0588f0",
    11: "#0d74ce",
    12: "#113264",
  },
  red: {
    1: "#fffcfc",
    2: "#fff7f7",
    3: "#feebec",
    4: "#ffdbdc",
    5: "#ffcdce",
    6: "#fdbdbe",
    7: "#f4a9aa",
    8: "#eb8e90",
    9: "#e5484d",
    10: "#dc3e42",
    11: "#ce2c31",
    12: "#641723",
  },
  yellow: {
    1: "#fdfdf9",
    2: "#fefce9",
    3: "#fffab8",
    4: "#fff394",
    5: "#ffe770",
    6: "#f3d768",
    7: "#e4c767",
    8: "#d5ae39",
    9: "#ffe629",
    10: "#ffdc00",
    11: "#9e6c00",
    12: "#473b1f",
  },
  indigo: {
    1: "#fdfdfe",
    2: "#f7f9ff",
    3: "#edf2fe",
    4: "#e1e9ff",
    5: "#d2deff",
    6: "#c1d0ff",
    7: "#abbdf9",
    8: "#8da4ef",
    9: "#3e63dd",
    10: "#3358d4",
    11: "#3a5bc7",
    12: "#1f2d5c",
  },
  sand: {
    1: "#fdfdfc",
    2: "#f9f9f8",
    3: "#f1f0ef",
    4: "#e9e8e6",
    5: "#e2e1de",
    6: "#dad9d6",
    7: "#cfceca",
    8: "#bcbbb5",
    9: "#8d8d86",
    10: "#82827c",
    11: "#63635e",
    12: "#21201c",
  },
  plum: {
    1: "#fefcff",
    2: "#fdf7fd",
    3: "#fbebfb",
    4: "#f7def8",
    5: "#f2d1f3",
    6: "#e9c2ec",
    7: "#deade3",
    8: "#cf91d8",
    9: "#ab4aba",
    10: "#a144af",
    11: "#953ea3",
    12: "#53195d",
  },
  bronze: {
    1: "#fdfcfc",
    2: "#fdf7f5",
    3: "#f6edea",
    4: "#efe4df",
    5: "#e7d9d3",
    6: "#dfcdc5",
    7: "#d3bcb3",
    8: "#c2a499",
    9: "#a18072",
    10: "#957468",
    11: "#7d5e54",
    12: "#43302b",
  },
};

export function radixDark(band: RadixBand, step: number): string {
  const scale = RADIX_DARK[band];
  const value = scale?.[step];
  if (!value) {
    throw new Error(`Unknown Radix dark token: ${band}${step}`);
  }
  return value;
}

export function radixLight(band: RadixBand, step: number): string {
  const scale = RADIX_LIGHT[band];
  const value = scale?.[step];
  if (!value) {
    throw new Error(`Unknown Radix light token: ${band}${step}`);
  }
  return value;
}
