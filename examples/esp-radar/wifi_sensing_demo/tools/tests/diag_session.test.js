#!/usr/bin/env node
/*
 * Ping/CSI diagnostic instrumentation unit checks (Prioritas 1, plan §18).
 *
 * These exercise the host-side session model in csi_recorder.js, which is the
 * authoritative implementation of the browser finalisation logic: epoch/boot_id
 * gating, the device timestamp window, wrap-safe diag_seq gap/out-of-order
 * accounting, the generation-bound consumer acknowledgement, the per-take event
 * soft-cap, and the columns+delta+enum encoding that lands in meta.events.
 *
 * The device STOP-ACK payload is modelled with the exact field names the
 * firmware emits (see handle_take_end in main/web_serial_monitor.c), so this
 * also pins the serial protocol contract for diagnostic events.
 */
const CsiRecorder = require("../csi_recorder.js");
const fs = require("fs");
const path = require("path");
const { report } = require("./harness.js");

/* Firmware degradation invariants (final audit §2): the runtime behaviour of
 * the alloc-failure paths cannot run in Node, so pin the source contract that
 * the host model relies on. Whitespace-insensitive substring checks. */
const FW_SRC = fs.readFileSync(
  path.join(__dirname, "..", "..", "main", "web_serial_monitor.c"), "utf8");
function fwCond(name, re) {
  report(name, re.test(FW_SRC.replace(/\s+/g, " ")));
}

const GEN = 1;
const BOOT = 0xdeadbeef >>> 0;

function started(epoch) {
  const s = CsiRecorder.createDiagSession({ epoch });
  const ok = CsiRecorder.diagNoteStartAck(s, {
    cmd: "TAKE_BEGIN", ok: true, epoch, gen: GEN, boot_id: BOOT, start_ts_us: 1000,
  });
  return { s, ok };
}

function pingMsg(epoch, ds, ts, extra) {
  return Object.assign({
    type: "diag", et: "ping", bid: BOOT, e: epoch, ds, ts,
    st: true, sn: ds, sv: true, tg: 2, ttl: 64, sz: 29, tx: 1, rx: 1,
  }, extra || {});
}

function csiMsg(epoch, ds, ts, extra) {
  return Object.assign({
    type: "diag", et: "csi", bid: BOOT, e: epoch, ds, ts,
    cb: 7, mac: "f8731a5923f4", dm: "3c22fbe1a2b4", rq: 512, sm: 0, mc: 7,
    rs: -59, bw: 0, sb: 0, pl: 128,
  }, extra || {});
}

function stopAck(epoch, extra) {
  return Object.assign({
    cmd: "TAKE_END", ok: true, epoch, gen: GEN, end_ts_us: 9000, boot_id: BOOT,
    barrier_ok: true, tx_drained: true, queue_pending: 0, inflight_at_close: 0,
    diag_seq_assigned_max: 200, diag_seq_enqueued_max: 200, diag_seq_emitted_max: 200,
    counters: {
      diag_queue_overflow: 0, serial_tx_lock_timeout: 0, truncated_msg: 0,
      serial_short_write: 0, csi_throttle_drop: 0, frame_tx_drop: 0,
      csi_callback: 0, csi_event_persisted: 0, ping_event_persisted: 0,
      diag_emit_failed: 0,
    },
  }, extra || {});
}

function main() {
  console.log("diag_session (Prioritas 1)");

  /* ---------------- start/stop ack + phases ---------------- */
  const a = started(10);
  report("START ACK opens recording with device anchors",
    a.ok && a.s.phase === "recording" && a.s.gen === GEN && a.s.bootId === BOOT && a.s.startTsUs === 1000);
  report("START ACK with wrong epoch is rejected",
    CsiRecorder.diagNoteStartAck(
      CsiRecorder.createDiagSession({ epoch: 3 }),
      { cmd: "TAKE_BEGIN", ok: true, epoch: 4, gen: GEN }) === false);

  /* ---------------- ping success/timeout semantics ---------------- */
  const p = started(11);
  CsiRecorder.diagAcceptEvent(p.s, pingMsg(11, 100, 1100, { st: true }));
  CsiRecorder.diagAcceptEvent(p.s, pingMsg(11, 101, 1200, { st: false, tg: 0, ttl: 0, sz: 0, rx: 0 }));
  CsiRecorder.diagNoteStopAck(p.s, stopAck(11, { counters: { ping_event_persisted: 2 } }));
  const pf = CsiRecorder.diagFinalize(p.s);
  report("ping rows carry success/timeout enum",
    pf.ping.rows.length === 2 && pf.ping.rows[0][0] === 1 && pf.ping.rows[1][0] === 2);
  report("timeout nulls reply-derived fields (timegap/ttl/recv_size)",
    pf.ping.rows[1][5] === null && pf.ping.rows[1][6] === null && pf.ping.rows[1][7] === null);
  report("success keeps reply-derived fields",
    pf.ping.rows[0][5] === 2 && pf.ping.rows[0][6] === 64 && pf.ping.rows[0][7] === 29);
  report("ping columns match documented schema",
    JSON.stringify(pf.ping.columns) === JSON.stringify(
      ["type", "ds", "ts_delta_us", "seqno", "seqno_valid", "timegap_ms", "ttl", "recv_size", "transmitted", "received"]));
  report("session_stats counts observed callbacks",
    pf.session_stats.success_callback_count === 1 && pf.session_stats.timeout_callback_count === 1);

  /* ---------------- base + Σ delta reconstructs absolute ts ---------------- */
  const recon = pf.ping.rows.reduce((acc, row, i) => (i === 0 ? [pf.ping.ts_base_us] : acc.concat(acc[acc.length - 1] + row[2])), null);
  report("ts_base_us + Σ delta reconstructs device timestamps",
    pf.ping.ts_base_us === 1100 && recon[1] === 1200);

  /* ---------------- csi_diag encoding ---------------- */
  const c = started(12);
  CsiRecorder.diagAcceptEvent(c.s, csiMsg(12, 300, 1100));
  CsiRecorder.diagNoteStopAck(c.s, stopAck(12, { counters: { csi_event_persisted: 1 } }));
  const cf = CsiRecorder.diagFinalize(c.s);
  report("csi_diag row carries mac/dmac/ps metadata",
    cf.csi_diag.rows[0][3] === "f8731a5923f4" && cf.csi_diag.rows[0][11] === 128 &&
      cf.csi_diag.mac_format === "12-hex lowercase, no colons");

  /* ---------------- epoch + boot_id gating ---------------- */
  const g = started(20);
  report("event from another epoch is rejected",
    CsiRecorder.diagAcceptEvent(g.s, pingMsg(21, 1, 1500)) === "epoch_rejected" &&
      g.s.counters.epoch_rejected === 1 && g.s.ping.length === 0);
  report("event from another boot_id is rejected",
    CsiRecorder.diagAcceptEvent(g.s, pingMsg(20, 1, 1500, { bid: 1 })) === "boot_mismatch" &&
      g.s.counters.boot_id_mismatch === 1);
  report("malformed event counted as parse error",
    CsiRecorder.diagAcceptEvent(g.s, { type: "diag" }) === "parse_error" &&
      g.s.counters.browser_parse_error === 1);

  /* ---------------- out-of-order + gap accounting (wrap-safe) ---------------- */
  const o = started(30);
  CsiRecorder.diagAcceptEvent(o.s, pingMsg(30, 100, 1100));
  CsiRecorder.diagAcceptEvent(o.s, pingMsg(30, 105, 1200)); // gap of 4 (101..104)
  CsiRecorder.diagAcceptEvent(o.s, pingMsg(30, 103, 1150)); // out of order
  CsiRecorder.diagNoteStopAck(o.s, stopAck(30, { counters: { ping_event_persisted: 3 } }));
  const of = CsiRecorder.diagFinalize(o.s);
  report("diag_seq gap counted (bounds, not per-event proof)",
    o.s.counters.seq_gaps === 4);
  report("out-of-order arrival counted but still stored",
    o.s.counters.out_of_order === 1 && of.ping.rows.length === 3);
  report("rows sorted by ts despite out-of-order arrival",
    of.ping.rows[0][2] === 0 && of.ping.rows[1][2] === 50 && of.ping.rows[2][2] === 50);
  report("seqNewer wraps at uint32 boundary",
    CsiRecorder.seqNewer(1, 0xFFFFFFFF) === true && CsiRecorder.seqNewer(0xFFFFFFFF, 1) === false);

  /* ---------------- consumer acknowledgement: stale ACK (§2) ---------------- */
  const k = started(40);
  CsiRecorder.diagAcceptEvent(k.s, pingMsg(40, 1, 1100));
  const staleEpoch = CsiRecorder.diagNoteStopAck(k.s, stopAck(41, {}));
  const staleGen = CsiRecorder.diagNoteStopAck(k.s, stopAck(40, { gen: 99 }));
  report("STOP ACK from another epoch is stale, barrier stays open",
    staleEpoch.accepted === false && staleEpoch.reason === "stale" && k.s.phase !== "finalized");
  report("STOP ACK with wrong flush_generation is stale",
    staleGen.accepted === false && staleGen.reason === "stale" && k.s.phase !== "finalized");
  report("stale acknowledgements counted, never close the drain",
    k.s.counters.stale_ack === 2);
  const good = CsiRecorder.diagNoteStopAck(k.s, stopAck(40, { counters: { ping_event_persisted: 1 } }));
  report("generation-matched STOP ACK finalises",
    good.accepted === true && good.reason === "confirmed" && k.s.phase === "finalized");
  const late = CsiRecorder.diagNoteStopAck(k.s, stopAck(40, {}));
  report("duplicate STOP ACK after finalise is rejected",
    late.accepted === false && late.reason === "already_finalized");
  report("events arriving after finalise are closed out",
    CsiRecorder.diagAcceptEvent(k.s, pingMsg(40, 2, 1200)) === "closed");

  /* ---------------- STOP timeout => boundary_unconfirmed ---------------- */
  const t = started(50);
  CsiRecorder.diagAcceptEvent(t.s, pingMsg(50, 1, 1100));
  CsiRecorder.diagNoteStopping(t.s);
  // no STOP ACK delivered (timeout); finalize still runs
  const tf = CsiRecorder.diagFinalize(t.s);
  report("missing STOP ACK yields boundary_unconfirmed",
    tf.boundary.confirmed === false && tf.boundary.status === "boundary_unconfirmed");
  report("unconfirmed boundary still persists arrived events",
    tf.ping.rows.length === 1 && tf.session_stats.diagnostic_event_loss_count === null);
  report("STOP ACK with ok=false finalises but unconfirmed",
    (function () {
      const s2 = started(51).s;
      CsiRecorder.diagNoteStopAck(s2, stopAck(51, { barrier_ok: false }));
      return s2.phase === "finalized" && s2.boundaryConfirmed === false;
    })());

  /* ---------------- event soft-cap (§18.5) ---------------- */
  const cap = CsiRecorder.createDiagSession({ epoch: 60, maxEvents: 3 });
  CsiRecorder.diagNoteStartAck(cap, { cmd: "TAKE_BEGIN", ok: true, epoch: 60, gen: GEN, boot_id: BOOT, start_ts_us: 1000 });
  for (let i = 0; i < 6; i++) {
    CsiRecorder.diagAcceptEvent(cap, pingMsg(60, 100 + i, 1100 + i));
  }
  const capf = CsiRecorder.diagFinalize(cap);
  report("per-take soft-cap stops appending at maxEvents",
    cap.ping.length === 3 && cap.truncated === true && cap.counters.event_overflow === 3);
  report("soft-cap sets session_stats.truncated",
    capf.session_stats.truncated === true && capf.session_stats.event_overflow_count === 3);

  /* ---------------- staged loss reconciliation (final audit §1) ------------- */
  const loss = started(70);
  CsiRecorder.diagAcceptEvent(loss.s, pingMsg(70, 1, 1100)); // only 1 of 5 arrived
  CsiRecorder.diagNoteStopAck(loss.s, stopAck(70, {
    counters: { ping_event_persisted: 4, csi_event_persisted: 1, diag_queue_overflow: 2 },
  }));
  const lossf = CsiRecorder.diagFinalize(loss.s);
  report("loss = queue_overflow + transport_loss (staged, never admitted-based)",
    lossf.session_stats.diagnostic_event_loss_count === 2 + (5 - 1));
  report("staged accounting exposes each edge separately",
    lossf.session_stats.loss_accounting.stages.diag_queue_overflow_count === 2 &&
      lossf.session_stats.loss_accounting.stages.diag_queue_enqueued_count === 5 &&
      lossf.session_stats.loss_accounting.stages.transport_unaccounted_count === 4 &&
      lossf.session_stats.loss_accounting.stages.browser_received_unique_count === 1);
  report("device counters surface in session_stats",
    lossf.session_stats.diag_queue_overflow_count === 2 &&
      lossf.session_stats.ping_event_persisted_count === 4);

  /* ---------------- timestamp window rejection ---------------- */
  const win = started(80); // start_ts_us = 1000
  CsiRecorder.diagAcceptEvent(win.s, pingMsg(80, 1, 1100)); // in window
  CsiRecorder.diagAcceptEvent(win.s, pingMsg(80, 2, 950));  // before start -> rejected
  CsiRecorder.diagNoteStopAck(win.s, stopAck(80, { end_ts_us: 2000, counters: { ping_event_persisted: 2 } }));
  const winf = CsiRecorder.diagFinalize(win.s);
  report("events before the device start window are rejected",
    winf.boundary.confirmed === true && winf.boundary.end_ts_us === 2000 &&
      winf.session_stats.host_counters.boundary_ts_rejected === 1);

  /* ---------------- serial protocol: real firmware line round-trip ---------------- */
  const wire = 'HMS:{"type":"diag","et":"ping","bid":42,"e":5,"ds":100,"ts":1100,"st":true,"sn":7,"sv":true,"tg":3,"ttl":64,"sz":29,"tx":1,"rx":1}';
  const parsed = JSON.parse(wire.slice(4));
  const w = CsiRecorder.createDiagSession({ epoch: 5 });
  CsiRecorder.diagNoteStartAck(w, { cmd: "TAKE_BEGIN", ok: true, epoch: 5, gen: GEN, boot_id: 42, start_ts_us: 1000 });
  report("firmware diag serial line parses into an accepted ping",
    parsed.type === "diag" && parsed.et === "ping" &&
      CsiRecorder.diagAcceptEvent(w, parsed) === "accepted");

  /* ---------------- meta persistence, two-file, old-compat, HTTP ---------------- */
  const metaWithEvents = CsiRecorder.buildMetaV3({
    recording_id: "rec_diag", activity_label: "walking",
    started_at_utc: "2026-11-01T00:00:00.000Z", ended_at_utc: "2026-11-01T00:00:10.000Z",
    actual_duration_s: 10, status: "complete",
    recording: { frames: 3, complete: true }, timeline: [],
    events: { segments: [], motion_samples: [], ping: pf.ping, csi_diag: cf.csi_diag },
    session_stats: pf.session_stats, boundary: pf.boundary,
  });
  report("meta persists per-event ping stream under events.ping",
    metaWithEvents.events.ping && metaWithEvents.events.ping.rows.length === 2);
  report("meta carries session_stats + boundary scalars",
    metaWithEvents.session_stats && metaWithEvents.session_stats.success_callback_count === 1 &&
      metaWithEvents.boundary.status === "confirmed");
  report("meta keeps exactly the two output files",
    metaWithEvents.files.frames_csv === "rec_diag.frames.csv" &&
      metaWithEvents.files.meta_json === "rec_diag.meta.json" &&
      Object.keys(metaWithEvents.files).length === 2);

  const oldMeta = CsiRecorder.buildMetaV3({
    recording_id: "rec_old", activity_label: "walking",
    started_at_utc: "2026-10-01T00:00:00.000Z", ended_at_utc: "2026-10-01T00:00:10.000Z",
    recording: { frames: 0, complete: true }, timeline: [],
    events: { segments: [], motion_samples: [] },
  });
  report("old recording without diagnostics stays valid (null scalars)",
    oldMeta.session_stats === null && oldMeta.boundary === null && oldMeta.events.ping === undefined);

  const httpMeta = CsiRecorder.buildMetaV3({
    recording_id: "rec_http", activity_label: "walking",
    started_at_utc: "2026-11-01T00:00:00.000Z", ended_at_utc: "2026-11-01T00:00:10.000Z",
    recording: { frames: 5, complete: true }, timeline: [],
    stimulus: { mode: "http", http: { bytes_received: 12345 } },
  });
  report("HTTP-stimulus recording meta remains valid with no ping events",
    httpMeta.stimulus.mode === "http" && httpMeta.stimulus.http.bytes_received === 12345 &&
      httpMeta.events.ping === undefined && httpMeta.session_stats === null);

  /* frames.csv schema must be untouched by the diagnostic work. */
  report("frames.csv header still has exactly 32 columns",
    CsiRecorder.FRAMES_COLUMNS.length === 32);

  /* ---------------- focused review §1: TAKE_BEGIN lifecycle gate ----------------
   * Mirror of the firmware gate (handle_take_begin): a new epoch may only open
   * once the previous session is closed AND queue/producer/drain are idle. */
  const allowed = CsiRecorder.diagTakeBeginAllowed({
    takeOpen: false, queuePending: 0, inflight: 0, drainInflight: 0,
  });
  report("lifecycle: confirmed quiescent STOP allows next TAKE_BEGIN",
    allowed.allowed === true && allowed.reason === "quiescent");
  report("lifecycle: pending queue items reject TAKE_BEGIN",
    CsiRecorder.diagTakeBeginAllowed({ queuePending: 3 }).allowed === false &&
      CsiRecorder.diagTakeBeginAllowed({ queuePending: 3 }).reason === "prev_not_quiescent");
  report("lifecycle: producer inflight rejects TAKE_BEGIN",
    CsiRecorder.diagTakeBeginAllowed({ inflight: 1 }).allowed === false);
  report("lifecycle: drain in-flight rejects TAKE_BEGIN",
    CsiRecorder.diagTakeBeginAllowed({ drainInflight: 1 }).allowed === false);
  report("lifecycle: take still open (no TAKE_END) rejects TAKE_BEGIN",
    CsiRecorder.diagTakeBeginAllowed({
      takeOpen: true, queuePending: 5, inflight: 1, drainInflight: 1,
    }).reason === "take_open");
  report("lifecycle: after recovery drains to idle, TAKE_BEGIN succeeds",
    CsiRecorder.diagTakeBeginAllowed({ takeOpen: false, queuePending: 0, inflight: 0, drainInflight: 0 }).allowed === true);

  const rej = CsiRecorder.createDiagSession({ epoch: 90 });
  const rejOk = CsiRecorder.diagNoteStartAck(rej, {
    cmd: "TAKE_BEGIN", ok: false, epoch: 90,
    detail: "prev_not_quiescent:queue_pending=7;inflight=0;drain_inflight=1",
  });
  report("rejection START ACK keeps session out of recording with no gen anchors",
    rejOk === false && rej.phase === "starting" && rej.gen === null);

  /* ---------------- focused review §2: csi_diag drop_reason fallback ---------------- */
  const fb = started(91);
  CsiRecorder.diagAcceptEvent(fb.s, csiMsg(91, 400, 1100));
  CsiRecorder.diagAcceptEvent(fb.s, csiMsg(91, 401, 1200, { sid: 55, dr: 2 }));
  CsiRecorder.diagAcceptEvent(fb.s, csiMsg(91, 402, 1300, { sid: 56, dr: 4 }));
  CsiRecorder.diagNoteStopAck(fb.s, stopAck(91, { counters: { csi_event_persisted: 3, frame_tx_drop: 2 } }));
  const fbf = CsiRecorder.diagFinalize(fb.s);
  report("throttle rows keep drop_reason=throttle when firmware omits dr",
    fbf.csi_diag.rows[0][13] === CsiRecorder.CSI_DROP_ENUM.throttle && fbf.csi_diag.rows[0][12] === null);
  report("direct-write failure fallback rows carry firmware seq + reason",
    fbf.csi_diag.rows[1][12] === 55 && fbf.csi_diag.rows[1][13] === CsiRecorder.CSI_DROP_ENUM.oversized &&
      fbf.csi_diag.rows[2][13] === CsiRecorder.CSI_DROP_ENUM.uart_write_fail);
  report("csi_diag stream exposes the drop_reason enum mapping",
    JSON.stringify(fbf.csi_diag.drop_reason_enum) === JSON.stringify({
      throttle: 0, tx_lock_timeout: 1, oversized: 2, base64_fail: 3, uart_write_fail: 4,
    }));
  const fbWire = 'HMS:{"type":"diag","et":"csi","bid":42,"e":5,"ds":9,"ts":1100,"cb":3,'
    + '"mac":"f8731a5923f4","dm":"3c22fbe1a2b4","rq":512,"sm":0,"mc":7,"rs":-59,"bw":0,"sb":0,'
    + '"pl":128,"sid":55,"dr":3}';
  const fbParsed = JSON.parse(fbWire.slice(4));
  const fw = CsiRecorder.createDiagSession({ epoch: 5 });
  CsiRecorder.diagNoteStartAck(fw, { cmd: "TAKE_BEGIN", ok: true, epoch: 5, gen: GEN, boot_id: 42, start_ts_us: 1000 });
  report("firmware fallback wire line parses into an accepted csi_diag",
    CsiRecorder.diagAcceptEvent(fw, fbParsed) === "accepted" && fw.csi[0].drop_reason === 3 && fw.csi[0].seq_id === 55);
  report("fallback events feed the same persisted-loss counters (no new loss source)",
    fbf.session_stats.csi_event_persisted_count === 3 &&
      fbf.session_stats.diagnostic_event_loss_count === 0);

  /* ---------------- final audit §1: one event, exactly one stage -------------
   * The stages must stay disjoint: an overflowed event never appears in the
   * enqueued counters (firmware increments them only on xQueueSend success),
   * and an event whose serial write failed is subtracted from the transport
   * gap so it cannot be counted as both tx_failed AND transport_loss. */
  const sEnq = started(100);
  CsiRecorder.diagAcceptEvent(sEnq.s, pingMsg(100, 1, 1100));
  CsiRecorder.diagNoteStopAck(sEnq.s, stopAck(100, {
    diag_seq_assigned_max: 3,
    counters: { ping_event_persisted: 1, diag_queue_overflow: 2 },
  }));
  const sEnqf = CsiRecorder.diagFinalize(sEnq.s);
  report("stage1: enqueue-overflow event is NOT counted again in transport loss",
    sEnqf.session_stats.loss_accounting.stages.transport_unaccounted_count === 0 &&
      sEnqf.session_stats.loss_accounting.stages.diag_queue_overflow_count === 2 &&
      sEnqf.session_stats.diagnostic_event_loss_count === 2);

  const sTx = started(101);
  CsiRecorder.diagAcceptEvent(sTx.s, pingMsg(101, 1, 1100)); // 2 enqueued, 1 emit-failed
  CsiRecorder.diagNoteStopAck(sTx.s, stopAck(101, {
    counters: { ping_event_persisted: 2, diag_emit_failed: 1 },
  }));
  const sTxf = CsiRecorder.diagFinalize(sTx.s);
  report("stage2: serial-write-failure event is NOT counted again in transport loss",
    sTxf.session_stats.loss_accounting.stages.diag_tx_failure_count === 1 &&
      sTxf.session_stats.loss_accounting.stages.transport_unaccounted_count === 0 &&
      sTxf.session_stats.diagnostic_event_loss_count === 1);

  const sWin = started(102);
  CsiRecorder.diagAcceptEvent(sWin.s, pingMsg(102, 1, 1100));      // in window
  CsiRecorder.diagAcceptEvent(sWin.s, pingMsg(102, 2, 950));       // arrived, window-rejected
  CsiRecorder.diagNoteStopAck(sWin.s, stopAck(102, { end_ts_us: 2000, counters: { ping_event_persisted: 2 } }));
  const sWinF = CsiRecorder.diagFinalize(sWin.s);
  report("window-rejected event counted once (browser edge, never as transport loss)",
    sWinF.session_stats.loss_accounting.stages.transport_unaccounted_count === 0 &&
      sWinF.session_stats.loss_accounting.stages.browser_window_rejected_count === 1 &&
      sWinF.session_stats.diagnostic_event_loss_count === 0);

  const sGap = started(103); // device claims 5 enqueued, browser sees 1, no TX failure
  CsiRecorder.diagAcceptEvent(sGap.s, pingMsg(103, 1, 1100));
  CsiRecorder.diagNoteStopAck(sGap.s, stopAck(103, {
    diag_seq_assigned_max: 5, counters: { ping_event_persisted: 5 },
  }));
  const sGapF = CsiRecorder.diagFinalize(sGap.s);
  report("unidentified shortfall is tagged transport_loss with zero unaccounted",
    sGapF.session_stats.loss_accounting.stages.transport_unaccounted_count === 4 &&
      sGapF.session_stats.loss_accounting.stages.diag_unaccounted_stage1_count === 0 &&
      sGapF.session_stats.loss_accounting.counter_inconsistent === false);

  const sAll = started(104);
  for (let i = 0; i < 4; i++) {
    CsiRecorder.diagAcceptEvent(sAll.s, pingMsg(104, 1 + i, 1100 + i));
  }
  CsiRecorder.diagNoteStopAck(sAll.s, stopAck(104, {
    diag_seq_assigned_max: 4, counters: { ping_event_persisted: 4 },
  }));
  const sAllF = CsiRecorder.diagFinalize(sAll.s);
  report("clean run reconciles exactly: all stages zero, persisted = received",
    sAllF.session_stats.diagnostic_event_loss_count === 0 &&
      sAllF.session_stats.loss_accounting.stages.browser_persisted_count === 4 &&
      sAllF.session_stats.loss_accounting.stages.browser_received_unique_count === 4);

  /* A still-queued item at close is a stage-2 loss; it must not also appear as
   * an unaccounted transport loss (it was never written to the wire). */
  const sPend = started(105);
  for (let i = 0; i < 3; i++) {
    CsiRecorder.diagAcceptEvent(sPend.s, pingMsg(105, 1 + i, 1100 + i));
  }
  CsiRecorder.diagNoteStopAck(sPend.s, stopAck(105, {
    diag_seq_assigned_max: 5, queue_pending: 2,
    counters: { ping_event_persisted: 5 },
  }));
  const sPendF = CsiRecorder.diagFinalize(sPend.s);
  report("pending-at-close counted once (stage 2), never again as transport loss",
    sPendF.session_stats.loss_accounting.stages.diag_pending_at_close_count === 2 &&
      sPendF.session_stats.loss_accounting.stages.diag_tx_success_count === 3 &&
      sPendF.session_stats.loss_accounting.stages.transport_unaccounted_count === 0 &&
      sPendF.session_stats.diagnostic_event_loss_count === 2);

  /* Receiving MORE than was transmitted means the counters disagree: clamp the
   * loss at zero and flag it, instead of reporting a negative loss. */
  const sBad = started(106);
  for (let i = 0; i < 4; i++) {
    CsiRecorder.diagAcceptEvent(sBad.s, pingMsg(106, 1 + i, 1100 + i));
  }
  CsiRecorder.diagNoteStopAck(sBad.s, stopAck(106, {
    diag_seq_assigned_max: 2, counters: { ping_event_persisted: 2 },
  }));
  const sBadF = CsiRecorder.diagFinalize(sBad.s);
  report("contradictory counters are flagged, loss clamped at zero",
    sBadF.session_stats.loss_accounting.counter_inconsistent === true &&
      sBadF.session_stats.loss_accounting.stages.transport_unaccounted_count === 0 &&
      sBadF.session_stats.diagnostic_event_loss_count === 0);

  /* Stage 4 must be an exact partition for every finalized session that has a
   * device snapshot: received = persisted + window_rejected + truncated. */
  const stageSet = [lossf, fbf, sEnqf, sTxf, sWinF, sGapF, sAllF, sPendF, sBadF];
  report("stage 4 partitions exactly (received = persisted + window + truncated) in every case",
    stageSet.every((f) => {
      const st = f.session_stats.loss_accounting.stages;
      return st.browser_received_count
        === st.browser_persisted_count + st.browser_window_rejected_count
        + st.browser_event_truncated_count;
    }));

  /* ---------------- final audit §2: degraded diagnostics ---------------------
   * Device-side behaviour is code-audited (producers no-op when the queue is
   * NULL; the barrier skips the MPSC step when diagnostics are disabled).
   * Here: the host model must KEEP the recording and mark the diagnostic
   * streams unavailable (null), never zero, for any of the three allocation
   * failure reasons. */
  for (const reason of ["queue_alloc_failed", "sem_alloc_failed", "drain_task_create_failed"]) {
    const deg = CsiRecorder.createDiagSession({ epoch: 110 });
    const okStart = CsiRecorder.diagNoteStartAck(deg, {
      cmd: "TAKE_BEGIN", ok: true, epoch: 110, gen: GEN, boot_id: BOOT,
      start_ts_us: 1000, diagnostics_enabled: false, reason,
    });
    const df = CsiRecorder.diagFinalize(deg);
    report(`degraded (${reason}): take stays open, device ack is ok`,
      okStart === true && deg.phase === "recording" && deg.gen === GEN);
    report(`degraded (${reason}): event streams null, not zero`,
      df.ping === null && df.csi_diag === null &&
        df.session_stats.success_callback_count === null &&
        df.session_stats.diagnostic_event_loss_count === null &&
        df.session_stats.diagnostics_unavailable === true &&
        df.session_stats.diagnostics_unavailable_reason === reason);
    report(`degraded (${reason}): boundary records the reason`,
      df.boundary.diagnostics_enabled === false &&
        df.boundary.diagnostics_unavailable_reason === reason);
  }
  const degStop = CsiRecorder.createDiagSession({ epoch: 114 });
  CsiRecorder.diagNoteStartAck(degStop, {
    cmd: "TAKE_BEGIN", ok: true, epoch: 114, gen: GEN, boot_id: BOOT,
    start_ts_us: 1000, diagnostics_enabled: false, reason: "queue_alloc_failed",
  });
  const degStopRes = CsiRecorder.diagNoteStopAck(degStop, stopAck(114, {
    diagnostics_enabled: false, tx_drained: true, queue_pending: 0,
  }));
  const degStopF = CsiRecorder.diagFinalize(degStop);
  report("degraded TAKE_END still finalises the recording",
    degStopRes.accepted === true && degStop.phase === "finalized" &&
      degStopF.boundary.confirmed === true);
  report("legacy firmware without diagnostics_enabled keeps null-device behaviour",
    (function () {
      const l = started(115);
      const lf = CsiRecorder.diagFinalize(l.s);
      return l.s.diagEnabled === true && lf.session_stats.diagnostics_unavailable === false &&
        lf.session_stats.diagnostic_event_loss_count === null &&
        lf.session_stats.loss_accounting === null;
    }()));

  /* ---------------- final audit §3: STOP ACK transmission failure ------------
   * Mirror of the firmware flags: `ok` is only true when barrier AND drain
   * succeeded; an fsync failure clears tx_drained; a short/garbled ACK never
   * parses on the host at all. Each case must land as boundary_unconfirmed. */
  const fsyncFail = started(120);
  const fsyncRes = CsiRecorder.diagNoteStopAck(fsyncFail.s, stopAck(120, {
    ok: false, tx_drained: false, fflush_ok: true, fsync_ok: false,
  }));
  report("fsync failure: STOP ACK cannot confirm the boundary",
    fsyncRes.reason === "unconfirmed" && fsyncFail.s.boundaryConfirmed === false);
  report("fsync failure reports the specific unconfirmed reason",
    CsiRecorder.diagFinalize(fsyncFail.s).boundary.unconfirmed_reason
      === "serial_tx_not_drained(fflush_ok=true,fsync_ok=false)");
  const fflushFail = started(121);
  CsiRecorder.diagNoteStopAck(fflushFail.s, stopAck(121, {
    ok: false, tx_drained: false, fflush_ok: false, fsync_ok: true,
  }));
  report("fflush failure: drain proven false, boundary unconfirmed",
    fflushFail.s.boundaryConfirmed === false);
  report("fflush failure names fflush in the reason",
    CsiRecorder.diagFinalize(fflushFail.s).boundary.unconfirmed_reason
      === "serial_tx_not_drained(fflush_ok=false,fsync_ok=true)");
  const barrierFail = started(124);
  CsiRecorder.diagNoteStopAck(barrierFail.s, stopAck(124, {
    ok: false, barrier_ok: false, tx_drained: true, fflush_ok: true, fsync_ok: true,
    queue_pending: 4, drain_inflight: 1, inflight_at_close: 2,
  }));
  report("barrier failure reports queue/drain residue, not a TX problem",
    CsiRecorder.diagFinalize(barrierFail.s).boundary.unconfirmed_reason
      === "mpsc_barrier_incomplete(queue_pending=4,drain_inflight=1,inflight_at_close=2)");
  const missingFlag = started(122);
  const partial = Object.assign(stopAck(122, {}), { tx_drained: undefined });
  const missingRes = CsiRecorder.diagNoteStopAck(missingFlag.s, partial);
  report("absent tx_drained flag never confirms (no claim on UART idle alone)",
    missingRes.reason === "unconfirmed" && missingFlag.s.boundaryConfirmed === false);
  report("missing drain evidence is attributed to the ACK, not to the device",
    CsiRecorder.diagFinalize(missingFlag.s).boundary.unconfirmed_reason
      === "stop_ack_missing_drain_flags");
  const confirmed = started(125);
  CsiRecorder.diagNoteStopAck(confirmed.s, stopAck(125, { fflush_ok: true, fsync_ok: true }));
  report("a confirmed boundary carries no unconfirmed reason",
    CsiRecorder.diagFinalize(confirmed.s).boundary.unconfirmed_reason === null);
  report("STOP ACK that never arrives is reported as a timeout reason",
    (function () {
      const s = started(126).s;
      CsiRecorder.diagNoteStopping(s);
      return CsiRecorder.diagFinalize(s).boundary.unconfirmed_reason === "stop_ack_timeout";
    }()));
  report("short-written ACK: split JSON never parses => no STOP ACK path exists",
    (function () {
      const line = '{"type":"ack","cmd":"TAKE_END","ok":true,"epoch":123,"gen":1,"barrier';
      let threw = false;
      try {
        JSON.parse(line);
      } catch (e) {
        threw = true;
      }
      const s = started(123).s;
      return threw && s.phase === "recording" && s.boundaryConfirmed === false;
    }()));

  /* ---------------- final audit §2 (device side): firmware invariants --------
   * Static pins of the contract the host model above assumes; breaking any of
   * these in the firmware re-introduces a crash / phantom-loss / false-confirm
   * the degraded-mode tests would no longer describe honestly. */
  fwCond("fw init: queue/sem alloc failure nulls handles and records a reason",
    /s_diag_disable_reason = !s_diag_queue \? "queue_alloc_failed" : "sem_alloc_failed";.{0,200}\} else \{/);
  fwCond("fw init: alloc failure never aborts (no ESP_ERROR_CHECK/esp_abort in the failure branch)",
    /if \(!s_diag_queue \|\| !s_drain_idle_sem\) \{ (?:(?!ESP_ERROR_CHECK|esp_abort).){0,700}? \} else \{/);
  fwCond("fw init: drain task failure sets drain_task_create_failed and nulls plumbing",
    /s_diag_disable_reason = "drain_task_create_failed";/);
  fwCond("fw admission: NULL queue returns BEFORE consuming diag_seq or inflight",
    /static bool diag_admit_and_enqueue\(diag_item_t \*it\) \{ .{0,500}? if \(s_diag_queue == NULL\) \{ return false; \} .{0,300}? portENTER_CRITICAL\(&s_epoch_mux\); if \(!s_closing/);
  fwCond("fw TAKE_BEGIN: opens CSI recording even with diagnostics disabled",
    /const bool diag_on = \(s_diag_queue != NULL\) && \(s_drain_task != NULL\); s_take_start_ts_us = esp_timer_get_time\(\);/);
  fwCond("fw TAKE_BEGIN: degraded START ACK carries diagnostics_enabled=false + reason",
    /\\"diagnostics_enabled\\":false,\\"reason\\":\\"%s\\"/);
  fwCond("fw barrier: degraded mode skips the MPSC step instead of blocking forever",
    /if \(!diag_enabled\) \{ drain_ok = true; break; \}/);
  fwCond("fw gate: xQueueReset only runs when a queue exists",
    /if \(s_diag_queue\) \{ xQueueReset\(s_diag_queue\);/);
  fwCond("fw STOP: fsync/fflush results are checked and feed tx_drained + ACK fields",
    /bool fsync_ok = \(fsync\(fileno\(stdout\)\) == 0\); bool tx_drained = \(fflush_result == 0\) && fsync_ok;/);
  fwCond("fw STOP: ok flag requires barrier AND drain (never TX-idle alone)",
    /\\"ok\\":%s.{0,900}barrier_ok && tx_drained \? "true" : "false"/);
  fwCond("fw STOP: confirmation additionally requires the ACK body to have written completely",
    /int ack_written = send_ack_locked\(body\);.{0,300}if \(ack_written > 0\) \{ stop_ack_drained = \(fflush\(stdout\) == 0\) && \(fsync\(fileno\(stdout\)\) == 0\); \}/);
  fwCond("fw writer: fflush EOF is a failed write, not a silent success",
    /size_t written = fwrite\(line, 1, \(size_t\)total_len, stdout\); int flush_result = fflush\(stdout\);.{0,600}if \(flush_result != 0\) \{ s_serial_short_write_count\+\+; return 0; \}/);

  if (process.exitCode) {
    console.error(`GAGAL: ${__filename}`);
  }
}

main();
