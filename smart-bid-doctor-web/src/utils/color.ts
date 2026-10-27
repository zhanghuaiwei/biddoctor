/** 颜色工具：HEX 混色（主题色阶计算用，与 less `mix(白, 基色, N)` 同口径） */

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function toHex(n: number): string {
  return Math.round(Math.min(255, Math.max(0, n)))
    .toString(16)
    .padStart(2, '0')
}

/** 混合两色：weightA 为 a 的占比（0~1） */
export function mixHex(a: string, b: string, weightA: number): string {
  const [ar, ag, ab] = hexToRgb(a)
  const [br, bg, bb] = hexToRgb(b)
  const w = Math.min(1, Math.max(0, weightA))
  return `#${toHex(ar * w + br * (1 - w))}${toHex(ag * w + bg * (1 - w))}${toHex(ab * w + bb * (1 - w))}`
}
