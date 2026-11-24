/* 色码令牌，ui@1.2 §5.1 为唯一定义。仅管理端组件可引用 COLOR_META。 */
export const COLOR_ORDER = ["green", "blue", "yellow", "orange", "red"] as const;

export type Color = (typeof COLOR_ORDER)[number];

export const COLOR_META: Record<Color, { label: string; token: string }> = {
  green: { label: "绿", token: "--c-green" },
  blue: { label: "蓝", token: "--c-blue" },
  yellow: { label: "黄", token: "--c-yellow" },
  orange: { label: "橙", token: "--c-orange" },
  red: { label: "红", token: "--c-red" },
};

export function isColor(value: unknown): value is Color {
  return typeof value === "string" && (COLOR_ORDER as readonly string[]).includes(value);
}
