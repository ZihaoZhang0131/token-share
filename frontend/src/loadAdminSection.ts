/** A failed section must not discard successful siblings or overwrite last good data. */
export async function loadAdminSection<T>(
  label: string,
  request: () => Promise<T>,
  apply: (value: T) => void
): Promise<string> {
  try {
    apply(await request());
    return "";
  } catch (reason) {
    return `${label}：${reason instanceof Error ? reason.message : "加载失败"}`;
  }
}
