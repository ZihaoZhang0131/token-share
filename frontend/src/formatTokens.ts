const decimal = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 });
const integer = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });

/** Display only: all API values and quota calculations remain integer tokens. */
export function formatTokens(tokens: number): string {
  if (!Number.isFinite(tokens)) return "—";
  if (tokens === 0) return "0 M";
  if (Math.abs(tokens) < 1000) return tokens > 0 ? "<0.001 M" : ">-0.001 M";
  return `${decimal.format(tokens / 1_000_000)} M`;
}

export function exactTokens(tokens: number): string {
  return Number.isFinite(tokens) ? `${integer.format(tokens)} Token` : "—";
}
