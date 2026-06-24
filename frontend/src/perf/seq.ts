/** 全局性能事件序号生成器（单例）。
 *
 * 统一 observer.ts 与 index.ts 的 seq 空间，避免两套独立计数器
 * 在同一 session 内产生重复 seq，导致后端按 (session_id, seq) 去重时丢事件。
 */

let _seq = 0;

export function nextSeq(): number {
  return ++_seq;
}

/** 仅供测试或 session 重置时使用。 */
export function resetSeq(): void {
  _seq = 0;
}
