"""性能监控服务：数据摄入、聚合、告警。"""

from __future__ import annotations

import logging
from collections import defaultdict
from math import ceil
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlmodel import desc, select

from app.models.perf import PerfAlert, PerfEvent, PerfSession
from app.schemas.perf import PerfEventIn, PerfSessionCreate

logger = logging.getLogger(__name__)

# 告警阈值（后续可迁移到 config.yaml）
ALERT_THRESHOLDS = {
    "longtask.single": 300,       # 单条长任务 >300ms 告警
    "longtask.total_ratio": 0.10, # 长任务总时长占会话时长 >10% 告警
    "memory.used_ratio": 0.85,    # JS Heap 使用 >85% 告警
    "directorySync.total": 500,   # 目录同步 >500ms 告警
    "media.prefetch.total": 200,  # 媒体预取 >200ms 告警
    "store.saveProject": 50,      # 项目保存 >50ms 告警
    "fps.drop": 50,               # FPS <50 告警
    "block.single": 200,          # 主线程阻塞 >200ms 告警
    "slow.request": 200,          # 后端慢请求 >200ms 告警
    "eventloop.blocked": 200,     # 后端事件循环阻塞 >200ms 告警
}

# 每个会话最多保留的原始事件数
MAX_EVENTS_PER_SESSION = 500


def _event_from_schema(e: PerfEventIn, session_id: str) -> PerfEvent:
    """把前端 Schema 转换为 ORM 对象。"""
    return PerfEvent(
        session_id=session_id,
        seq=e.seq,
        ts=e.ts,
        kind=e.kind,
        name=e.name,
        duration_ms=e.durationMs,
        payload=e.payload,
    )


def _aggregate_events(events: list[PerfEvent]) -> dict:
    """从原始事件计算聚合指标。"""
    long_tasks = [e for e in events if e.kind == "longtask"]
    blocks = [e for e in events if e.kind == "block"]
    fps_samples = [e for e in events if e.kind == "fps"]
    counters: dict[str, int] = defaultdict(int)
    measures: dict[str, list[float]] = defaultdict(list)

    for e in events:
        if e.kind == "counter" and e.duration_ms is not None:
            counters[e.name] += int(e.duration_ms)
        elif e.kind == "measure" and e.duration_ms is not None:
            measures[e.name].append(e.duration_ms)

    measure_aggregates = []
    for name, values in measures.items():
        values.sort()
        p95_idx = max(0, ceil(len(values) * 0.95) - 1)
        measure_aggregates.append({
            "name": name,
            "count": len(values),
            "totalMs": round(sum(values), 2),
            "avgMs": round(sum(values) / len(values), 2),
            "p95Ms": round(values[p95_idx], 2),
            "maxMs": round(max(values), 2),
        })

    last_memory = next(
        (e for e in reversed(events) if e.kind == "memory"),
        None,
    )

    # FPS 聚合
    fps_values = []
    fps_min = None
    fps_dropped = 0
    for e in fps_samples:
        v = (e.payload or {}).get("fps")
        if isinstance(v, (int, float)):
            fps_values.append(v)
            if v < ALERT_THRESHOLDS.get("fps.drop", 50):
                fps_dropped += 1
            if fps_min is None or v < fps_min:
                fps_min = v
    fps_avg = round(sum(fps_values) / len(fps_values), 1) if fps_values else None

    # 阻塞事件聚合
    block_count = len(blocks)
    block_total_ms = round(sum(e.duration_ms or 0 for e in blocks), 2)
    block_max_ms = round(max((e.duration_ms or 0 for e in blocks), default=0), 2)

    return {
        "longTaskCount": len(long_tasks),
        "longTaskTotalMs": round(sum(e.duration_ms or 0 for e in long_tasks), 2),
        "memUsedMB": (last_memory.payload or {}).get("usedMB", 0) if last_memory else 0,
        "memTotalMB": (last_memory.payload or {}).get("totalMB") if last_memory else None,
        "memLimitMB": (last_memory.payload or {}).get("limitMB") if last_memory else None,
        "counters": dict(counters),
        "measureAggregates": measure_aggregates,
        "fpsAvg": fps_avg,
        "fpsMin": fps_min,
        "fpsDroppedSamples": fps_dropped,
        "fpsSampleCount": len(fps_values),
        "blockCount": block_count,
        "blockTotalMs": block_total_ms,
        "blockMaxMs": block_max_ms,
    }


def _evaluate_alerts(session_id: str, summary: dict, duration_s: int) -> list[PerfAlert]:
    """根据聚合指标生成告警。"""
    alerts: list[PerfAlert] = []

    # 单条长任务告警（measureAggregates 中 name 为 main-thread 的代表长任务）
    for agg in summary.get("measureAggregates", []):
        if agg["name"] == "main-thread":
            threshold = ALERT_THRESHOLDS.get("longtask.single")
            if threshold and agg["maxMs"] > threshold:
                alerts.append(
                    PerfAlert(
                        session_id=session_id,
                        level="warning",
                        metric="longtask.single",
                        threshold=threshold,
                        actual=agg["maxMs"],
                        message=f"检测到主线程长任务 {agg['maxMs']:.0f}ms，可能导致界面卡顿",
                    )
                )

    # 长任务占比
    if duration_s > 0:
        ratio = summary["longTaskTotalMs"] / (duration_s * 1000)
        threshold = ALERT_THRESHOLDS.get("longtask.total_ratio")
        if threshold and ratio > threshold:
            alerts.append(
                PerfAlert(
                    session_id=session_id,
                    level="warning",
                    metric="longtask.total_ratio",
                    threshold=threshold,
                    actual=round(ratio, 3),
                    message=f"长任务占总时长 {ratio*100:.1f}%，主线程阻塞严重",
                )
            )

    # 内存告警
    # 优先使用 jsHeapSizeLimit（浏览器堆上限）计算真实 OOM 风险
    # totalJSHeapSize 只是已分配量，used/total 通常 85-95%，属正常现象
    mem_limit = summary.get("memLimitMB")
    mem_total = summary.get("memTotalMB")
    if mem_limit and mem_limit > 0:
        ratio = summary["memUsedMB"] / mem_limit
        threshold = ALERT_THRESHOLDS.get("memory.used_ratio")
        if threshold and ratio > threshold:
            alerts.append(
                PerfAlert(
                    session_id=session_id,
                    level="error",
                    metric="memory.used_ratio",
                    threshold=threshold,
                    actual=round(ratio, 3),
                    message=f"JS 堆内存使用率达 {ratio*100:.1f}%（{summary['memUsedMB']}/{mem_limit}MB），存在 OOM 风险",
                )
            )
    elif mem_total and mem_total > 0:
        # 兼容旧版前端（无 jsHeapSizeLimit），但提高阈值避免误报
        ratio = summary["memUsedMB"] / mem_total
        threshold = 0.95  # used/total 超过 95% 才告警（因为 used/total 通常就很高）
        if ratio > threshold:
            alerts.append(
                PerfAlert(
                    session_id=session_id,
                    level="warning",
                    metric="memory.used_ratio",
                    threshold=threshold,
                    actual=round(ratio, 3),
                    message=f"JS 堆内存使用率达 {ratio*100:.1f}%（{summary['memUsedMB']}/{mem_total}MB），可能存在 OOM 风险",
                )
            )

    # 业务指标告警
    for agg in summary.get("measureAggregates", []):
        threshold = ALERT_THRESHOLDS.get(agg["name"])
        if threshold and agg["maxMs"] > threshold:
            alerts.append(
                PerfAlert(
                    session_id=session_id,
                    level="warning",
                    metric=agg["name"],
                    threshold=threshold,
                    actual=agg["maxMs"],
                    message=f"{agg['name']} 最大耗时 {agg['maxMs']:.0f}ms，超过阈值 {threshold}ms",
                )
            )

    # FPS 告警
    fps_min = summary.get("fpsMin")
    fps_dropped = summary.get("fpsDroppedSamples", 0)
    fps_total = summary.get("fpsSampleCount", 0)
    fps_threshold = ALERT_THRESHOLDS.get("fps.drop")
    if fps_threshold and fps_min is not None and fps_min < fps_threshold:
        ratio = (fps_dropped / fps_total) if fps_total else 0
        level = "error" if ratio > 0.3 else "warning"
        alerts.append(
            PerfAlert(
                session_id=session_id,
                level=level,
                metric="fps.drop",
                threshold=fps_threshold,
                actual=fps_min,
                message=f"FPS 最低 {fps_min:.0f}（{fps_dropped}/{fps_total} 次采样低于 {fps_threshold}），存在掉帧卡顿",
            )
        )

    # 主线程阻塞告警
    block_max = summary.get("blockMaxMs", 0)
    block_count = summary.get("blockCount", 0)
    block_threshold = ALERT_THRESHOLDS.get("block.single")
    if block_threshold and block_max > block_threshold:
        level = "error" if block_max > 1000 else "warning"
        alerts.append(
            PerfAlert(
                session_id=session_id,
                level=level,
                metric="block.single",
                threshold=block_threshold,
                actual=block_max,
                message=f"主线程阻塞 {block_max:.0f}ms（共 {block_count} 次），界面可能冻结",
            )
        )

    return alerts


def ingest_session(db: Session, data: PerfSessionCreate) -> tuple[str, list[PerfAlert]]:
    """摄入一个前端性能会话，合并历史事件重新计算聚合指标，并生成告警。"""
    session_id = data.sessionId

    # 查询或创建会话记录
    session_record = db.exec(
        select(PerfSession).where(PerfSession.session_id == session_id)
    ).first()

    if not session_record:
        session_record = PerfSession(session_id=session_id)
        db.add(session_record)
        db.flush()

    # 读取该会话已有的 seq，避免重复写入（同一 batch 重复上报或前后端网络抖动）
    existing_seqs = set(
        db.exec(
            select(PerfEvent.seq).where(PerfEvent.session_id == session_id)
        ).all()
    )

    new_events = []
    for e in data.events:
        if e.seq in existing_seqs:
            continue
        new_events.append(_event_from_schema(e, session_id))

    # 读取已有事件，与新事件合并后重新计算聚合指标
    existing_events = db.exec(
        select(PerfEvent)
        .where(PerfEvent.session_id == session_id)
        .order_by(desc(PerfEvent.ts), desc(PerfEvent.seq))
        .limit(MAX_EVENTS_PER_SESSION)
    ).all()

    merged_events = list(existing_events) + new_events

    # 保留最近 MAX_EVENTS_PER_SESSION 条，避免无限增长
    if len(merged_events) > MAX_EVENTS_PER_SESSION:
        # 按时间戳优先、seq 其次排序，保留最新的
        merged_events.sort(key=lambda e: (e.ts or 0, e.seq or 0), reverse=True)
        merged_events = merged_events[:MAX_EVENTS_PER_SESSION]

        # 只删除已有的旧事件；新事件尚未写入，无需删除
        keep_ids = {e.id for e in merged_events if e.id is not None}
        remove_ids = {e.id for e in existing_events if e.id not in keep_ids}
        if remove_ids:
            db.exec(delete(PerfEvent).where(PerfEvent.id.in_(remove_ids)))

    # 计算聚合指标
    aggregated = _aggregate_events(merged_events)
    duration_s = max(1, data.summary.sessionDurationS)

    # 把 fps / block 聚合注入 measure_aggregates，复用现有 JSON 字段（无需改表结构）
    extra_aggs = list(aggregated["measureAggregates"])
    if aggregated.get("fpsSampleCount"):
        extra_aggs.append({
            "name": "fps.min",
            "count": aggregated["fpsSampleCount"],
            "totalMs": 0,
            "avgMs": aggregated.get("fpsAvg") or 0,
            "p95Ms": 0,
            "maxMs": aggregated.get("fpsMin") or 0,
        })
    if aggregated.get("blockCount"):
        extra_aggs.append({
            "name": "block.max",
            "count": aggregated["blockCount"],
            "totalMs": aggregated["blockTotalMs"],
            "avgMs": round(aggregated["blockTotalMs"] / aggregated["blockCount"], 2),
            "p95Ms": aggregated["blockMaxMs"],
            "maxMs": aggregated["blockMaxMs"],
        })

    # 更新会话聚合记录
    session_record.started_at = data.startedAt
    session_record.ended_at = data.endedAt
    session_record.ua = data.ua
    session_record.app_version = data.appVersion
    session_record.session_duration_s = duration_s
    session_record.long_task_count = aggregated["longTaskCount"]
    session_record.long_task_total_ms = aggregated["longTaskTotalMs"]
    session_record.mem_used_mb = aggregated["memUsedMB"]
    session_record.mem_total_mb = aggregated["memTotalMB"]
    session_record.mem_limit_mb = aggregated["memLimitMB"]
    session_record.counters = aggregated["counters"]
    session_record.measure_aggregates = extra_aggs

    # 写入新事件（忽略唯一约束冲突，防止并发写入导致失败）
    for e in new_events:
        db.add(e)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # 重新去重后再次尝试写入
        current_seqs = set(
            db.exec(
                select(PerfEvent.seq).where(PerfEvent.session_id == session_id)
            ).all()
        )
        for e in new_events:
            if e.seq not in current_seqs:
                db.add(e)
        db.flush()

    # 生成告警（避免同一 session 同 metric 重复告警）
    existing_alerts = db.exec(
        select(PerfAlert).where(
            PerfAlert.session_id == session_id,
            PerfAlert.acknowledged == False,
        )
    ).all()
    alert_map = {a.metric: a for a in existing_alerts}

    new_alerts = _evaluate_alerts(session_id, aggregated, duration_s)
    alerts_to_return: list[PerfAlert] = []
    for alert in new_alerts:
        existing = alert_map.get(alert.metric)
        if existing:
            # 更新已有未处理告警的实际值和时间戳
            existing.actual = alert.actual
            existing.message = alert.message
            existing.created_at = alert.created_at
            alerts_to_return.append(existing)
        else:
            db.add(alert)
            alert_map[alert.metric] = alert
            alerts_to_return.append(alert)

    db.commit()
    return session_record.id, alerts_to_return


def list_sessions(db: Session, limit: int = 50, offset: int = 0) -> list[PerfSession]:
    """查询历史会话，按创建时间倒序。"""
    return db.exec(
        select(PerfSession).order_by(desc(PerfSession.created_at)).offset(offset).limit(limit)
    ).all()


def get_session(db: Session, session_id: str) -> Optional[PerfSession]:
    """获取单个会话详情。"""
    return db.exec(select(PerfSession).where(PerfSession.session_id == session_id)).first()


def list_alerts(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    acknowledged: Optional[bool] = None,
) -> list[PerfAlert]:
    """查询性能告警。"""
    stmt = select(PerfAlert)
    if acknowledged is not None:
        stmt = stmt.where(PerfAlert.acknowledged == acknowledged)
    stmt = stmt.order_by(desc(PerfAlert.created_at)).offset(offset).limit(limit)
    return db.exec(stmt).all()


def acknowledge_alert(db: Session, alert_id: str) -> Optional[PerfAlert]:
    """标记告警已处理。"""
    alert = db.exec(select(PerfAlert).where(PerfAlert.id == alert_id)).first()
    if alert:
        alert.acknowledged = True
        db.commit()
    return alert


def clear_all(db: Session) -> dict:
    """清空所有性能监控数据（会话、事件、告警）。"""
    db.exec(delete(PerfAlert))
    db.exec(delete(PerfEvent))
    db.exec(delete(PerfSession))
    db.commit()
    return {"deleted": True}


# ============================================================
# AI 诊断：规则化根因分析
# ============================================================

def get_queue_depth() -> dict:
    """采集任务队列深度（复用 generate.py 的信号量状态）。"""
    try:
        from app.api.generate import _background_tasks, _task_semaphore, _get_max_concurrent
        max_concurrent = _get_max_concurrent()
        return {
            "active_tasks": len(_background_tasks),
            "semaphore_available": _task_semaphore._value if _task_semaphore else max_concurrent,
            "semaphore_max": max_concurrent,
            "saturated": len(_background_tasks) >= max_concurrent,
        }
    except Exception:
        return {"active_tasks": 0, "semaphore_available": 0, "semaphore_max": 0, "saturated": False}


def diagnose_session(db: Session, session_id: str) -> dict:
    """对性能会话做规则化根因分析，产出结构化诊断报告供 AI / 用户定位卡顿。

    返回结构：
      - severity: overall / warning / error / critical
      - findings: [{ id, severity, category, title, evidence, suggestion, suspects }]
      - report: 完整原始报告（可复制喂给任意 AI）
    """
    session = get_session(db, session_id)
    if not session:
        return {"error": "session not found", "session_id": session_id}

    # 原始事件（用于归因分析）
    events = db.exec(
        select(PerfEvent)
        .where(PerfEvent.session_id == session_id)
        .order_by(PerfEvent.ts)
    ).all()

    alerts = db.exec(
        select(PerfAlert).where(PerfAlert.session_id == session_id)
    ).all()

    aggs = session.measure_aggregates or []
    agg_map = {a["name"]: a for a in aggs if isinstance(a, dict)}
    counters = session.counters or {}

    findings: list[dict] = []
    duration_s = max(1, session.session_duration_s)

    # ---- 1. 主线程阻塞（block 事件） ----
    # 关键：区分"真冻结"和"主线程持续繁忙"
    #   - block 来源含 'raf' → rAF 真的停了 >200ms，是真冻结，critical
    #   - block 来源全是 'worker' + FPS 仍在跑（有 fps 采样）→ 主线程繁忙但未冻结，
    #     Worker 心跳超时是消息处理被挤占的副产物，降级为 warning
    block_agg = agg_map.get("block.max")
    block_events = [e for e in events if e.kind == "block"]
    block_sources = set((e.payload or {}).get("source") for e in block_events)
    has_raf_block = "raf" in block_sources
    only_worker_block = "raf" not in block_sources and "worker" in block_sources
    fps_agg = agg_map.get("fps.min")
    fps_active = fps_agg and fps_agg.get("count", 0) > 3  # 有足够 FPS 采样说明主线程在跑

    if block_agg and block_agg.get("maxMs", 0) > 200:
        best_attr = None
        for e in block_events:
            attr = (e.payload or {}).get("attribution")
            if attr and (attr.get("scriptUrl") or attr.get("invoker")):
                best_attr = attr
                break

        if only_worker_block and fps_active and not has_raf_block:
            # 主线程持续繁忙但未冻结——Worker 心跳超时是副产物，不是真阻塞
            findings.append({
                "id": "block",
                "severity": "warning",
                "category": "主线程繁忙（非冻结）",
                "title": f"Worker 心跳 {block_agg['count']} 次超时（最长 {block_agg['maxMs']:.0f}ms），但 rAF 仍在触发",
                "evidence": f"全部来源 worker，无 raf 来源；FPS 仍有 {fps_agg['count']} 次采样，说明主线程在跑只是繁忙",
                "suggestion": "这不是真正的线程冻结，而是主线程持续高负载导致 Worker 消息处理延迟。真正问题在下方'渲染负载'诊断——每帧渲染过重拖慢了整体帧率。修复方向是减少每帧工作量，而非找阻塞脚本。",
                "suspects": [],
            })
        else:
            severity = "critical" if block_agg["maxMs"] > 1000 else "error"
            suspects = []
            if best_attr:
                if best_attr.get("scriptUrl"):
                    suspects.append(f"脚本: {best_attr['scriptUrl']}")
                if best_attr.get("invoker"):
                    suspects.append(f"调用方: {best_attr['invoker']}")
                if best_attr.get("functionName"):
                    suspects.append(f"函数: {best_attr['functionName']}")
            findings.append({
                "id": "block",
                "severity": severity,
                "category": "主线程冻结",
                "title": f"主线程最长冻结 {block_agg['maxMs']:.0f}ms（共 {block_agg['count']} 次，来源 {sorted(block_sources)}）",
                "evidence": f"阻塞总时长 {block_agg['totalMs']:.0f}ms",
                "suggestion": "rAF 确认主线程真正冻结。检查 suspects 指向的脚本/函数，常见原因：同步 JSON.parse 大对象、第三方库同步初始化、大循环 CPU 密集计算。考虑拆分到 requestIdleCallback / Web Worker。",
                "suspects": suspects or ["未捕获归因（LoAF 不可用，建议 Chrome 116+ 环境复现）"],
            })

    # ---- 2. 长任务归因（LoAF） ----
    longtask_loaf = [e for e in events if e.kind == "longtask" and e.name == "main-thread.loaf"]
    if longtask_loaf:
        # 按归因脚本聚合
        script_groups: dict[str, list] = defaultdict(list)
        for e in longtask_loaf:
            attr = (e.payload or {}).get("attribution") or {}
            key = attr.get("scriptUrl") or attr.get("invoker") or "unknown"
            script_groups[key].append(e.duration_ms or 0)
        top_scripts = sorted(script_groups.items(), key=lambda x: sum(x[1]), reverse=True)[:3]
        for script, durations in top_scripts:
            findings.append({
                "id": f"loaf:{script[:40]}",
                "severity": "warning" if sum(durations) < 1000 else "error",
                "category": "长任务归因",
                "title": f"脚本累计长任务 {sum(durations):.0f}ms（{len(durations)} 次）",
                "evidence": f"来源: {script}",
                "suggestion": "该脚本是长任务主要来源。考虑：①减少单次工作量 ②拆分为异步分片 ③使用 React.memo/useMemo 避免重复计算 ④对大数据集用虚拟滚动。",
                "suspects": [script],
            })
    elif session.long_task_count > 0:
        findings.append({
            "id": "longtask_no_attr",
            "severity": "warning",
            "category": "长任务归因",
            "title": f"检测到 {session.long_task_count} 次长任务，但无 LoAF 归因",
            "evidence": f"长任务总时长 {session.long_task_total_ms:.0f}ms",
            "suggestion": "当前浏览器不支持 Long Animation Frames API，无法定位卡顿脚本。建议在 Chrome 116+ 复现以获取归因信息。",
            "suspects": [],
        })

    # ---- 3. FPS 掉帧 / 每帧渲染过重 ----
    # 关键场景识别：
    #   FPS 持续低 + longtask=0 + 无 raf block → "每帧渲染过重"（frame budget 超支但无单点阻塞）
    #   FPS 低 + 有长任务/阻塞 → 配合长任务归因定位
    if fps_agg and fps_agg.get("maxMs", 999) < 50:
        fps_min = fps_agg["maxMs"]
        fps_avg = fps_agg.get("avgMs", 0)
        fps_count = fps_agg.get("count", 0)
        longtask_total = session.long_task_count or 0
        has_real_freeze = has_raf_block or (block_agg and block_agg.get("maxMs", 0) > 1000 and not only_worker_block)

        if longtask_total == 0 and not has_real_freeze:
            # 持续低 FPS 但无长任务无真冻结 → 每帧渲染过重（温水煮青蛙式卡顿）
            findings.append({
                "id": "fps_heavy_render",
                "severity": "error" if fps_min < 30 else "warning",
                "category": "渲染负载（每帧过重）",
                "title": f"持续低帧率 {fps_min:.0f}fps（平均 {fps_avg:.0f}），但无 >50ms 长任务，疑似每帧渲染过重",
                "evidence": f"{fps_count} 次采样全部 <50fps，longtask=0，无 rAF 冻结。60fps 预算每帧 16.7ms，当前 {fps_avg:.0f}fps 意味着每帧实际耗时约 {1000/max(1,fps_avg):.0f}ms",
                "suggestion": (
                    "这是'温水煮青蛙'式卡顿——没有任何单点超过 50ms（所以 longtask 不触发），但每帧都超支预算。"
                    "重点排查方向：\n"
                    "① 大列表未虚拟化——每帧渲染数千 DOM 节点（最常见元凶，检查角色/场景/分镜列表是否一次性渲染全部）\n"
                    "② React 全树 re-render——父组件 state 变化导致子树重渲染，用 React DevTools Profiler 的 Record 功能确认哪些组件在每帧重渲染\n"
                    "③ 动画触发布局重排——动画用了 width/height/top/left（触发 layout）而非 transform/opacity（只触发 composite）\n"
                    "④ 高频 state 更新——Zustand store 在 requestAnimationFrame 或短间隔 setInterval 里频繁更新\n"
                    "⑤ 每帧执行昂贵计算——深拷贝大对象、大 JSON.parse、未 memo 的计算，每帧都重来一遍\n"
                    "建议：打开 Chrome DevTools → Performance → Record 5 秒，查看每帧的 Scripting + Rendering 耗时分布"
                ),
                "suspects": [],
            })
        else:
            findings.append({
                "id": "fps",
                "severity": "error" if fps_min < 30 else "warning",
                "category": "帧率",
                "title": f"FPS 最低 {fps_min:.0f}，平均 {fps_avg:.0f}",
                "evidence": f"{fps_count} 次采样",
                "suggestion": "掉帧伴随长任务或线程冻结，配合上方的长任务归因/阻塞诊断定位具体脚本。",
                "suspects": [],
            })

    # ---- 4. 慢请求（前端 measure） ----
    slow_api = []
    for name, agg in agg_map.items():
        if name.startswith("api") and agg.get("maxMs", 0) > 200:
            slow_api.append((name, agg))
    slow_api.sort(key=lambda x: x[1]["maxMs"], reverse=True)
    for name, agg in slow_api[:5]:
        findings.append({
            "id": f"slowapi:{name[:40]}",
            "severity": "error" if agg["maxMs"] > 2000 else "warning",
            "category": "慢请求",
            "title": f"{name} 最大耗时 {agg['maxMs']:.0f}ms（P95 {agg['p95Ms']:.0f}ms）",
            "evidence": f"调用 {agg['count']} 次",
            "suggestion": "后端接口慢。检查对应路由：是否同步阻塞调用未走 run_in_executor、是否 N+1 查询、是否缺少索引、是否调用外部 API 未设超时。配合后端慢请求中间件告警交叉验证。",
            "suspects": [name],
        })

    # ---- 5. 后端告警（slow.request / eventloop.blocked） ----
    backend_alerts = [a for a in alerts if a.metric in ("slow.request", "eventloop.blocked")]
    for a in backend_alerts[:5]:
        findings.append({
            "id": f"backend:{a.metric}",
            "severity": a.level,
            "category": "后端",
            "title": a.message,
            "evidence": f"{a.metric}: 实际 {a.actual} / 阈值 {a.threshold}",
            "suggestion": (
                "事件循环阻塞：检查后端是否有同步 IO（requests、time.sleep、同步文件操作）未走 run_in_executor。"
                if a.metric == "eventloop.blocked"
                else "慢请求：检查该路由的 DB 查询、外部 API 调用、CPU 密集计算。"
            ),
            "suspects": [a.message],
        })

    # ---- 6. 队列饱和 ----
    queue = get_queue_depth()
    if queue.get("saturated"):
        findings.append({
            "id": "queue_saturated",
            "severity": "warning",
            "category": "任务队列",
            "title": f"生成任务队列饱和（{queue['active_tasks']}/{queue['semaphore_max']}）",
            "evidence": f"信号量剩余 {queue['semaphore_available']}",
            "suggestion": "并发任务已达上限，新任务会排队等待。若用户感觉'卡'，可能是生成任务排队而非前端卡顿。可在设置中调大 max_concurrent 或检查是否有任务卡住未释放。",
            "suspects": [],
        })

    # ---- 7. 内存 ----
    if session.mem_limit_mb and session.mem_used_mb:
        ratio = session.mem_used_mb / session.mem_limit_mb
        if ratio > 0.85:
            findings.append({
                "id": "memory",
                "severity": "error" if ratio > 0.95 else "warning",
                "category": "内存",
                "title": f"JS 堆内存 {session.mem_used_mb}/{session.mem_limit_mb}MB（{ratio*100:.0f}%）",
                "evidence": f"totalJSHeapSize {session.mem_total_mb}MB",
                "suggestion": "内存占用高，可能存在泄漏。检查：事件监听器未清理、闭包持有大对象、图片/视频 blob 未 URL.revokeObjectURL、Zustand store 累积历史数据未清理。",
                "suspects": [],
            })

    # 严重度汇总
    severity_order = {"critical": 4, "error": 3, "warning": 2, "overall": 1}
    top_severity = "overall"
    for f in findings:
        if severity_order.get(f["severity"], 0) > severity_order.get(top_severity, 0):
            top_severity = f["severity"]

    # 完整报告（供复制喂给任意 AI）
    report = {
        "session_id": session_id,
        "started_at": session.started_at,
        "duration_s": duration_s,
        "summary": {
            "long_task_count": session.long_task_count,
            "long_task_total_ms": session.long_task_total_ms,
            "mem_used_mb": session.mem_used_mb,
            "mem_limit_mb": session.mem_limit_mb,
        },
        "measure_aggregates": aggs,
        "counters": counters,
        "alerts": [
            {"metric": a.metric, "level": a.level, "message": a.message, "actual": a.actual, "threshold": a.threshold}
            for a in alerts
        ],
        "queue_depth": queue,
        "findings": findings,
    }

    return {
        "session_id": session_id,
        "severity": top_severity,
        "findings": findings,
        "report": report,
    }

