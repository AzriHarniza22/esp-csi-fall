#!/usr/bin/env node
/*
 * csi_recorder.js unit checks.
 *
 * v3 focus (docs/recording-pipeline-implementation.md §16): the eleven activity
 * labels + binary mapping, fixed 10 s timelines and boundaries, exact
 * Indonesian cue text, monotonic annotations, measured interval stats, meta v3
 * shape, and the lossless 32-column frames.csv round-trip. The legacy
 * derived-file builders are still exercised because they remain exported for
 * MANUAL export and old-dataset readers.
 */
const path = require("path");
const CsiRecorder = require("../csi_recorder.js");
const { report } = require("./harness.js");

function arraysEqual(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
    a.every((v, i) => v === b[i]);
}

function main() {
  console.log("csi_recorder.js");

  /* ---------------- identity helpers ---------------- */
  report("slug collapses punctuation", CsiRecorder.slugLabel("Jatuh!!  1") === "jatuh_1");
  report("empty label is empty slug", CsiRecorder.slugLabel("   ") === "");
  report("known activity preset wins over custom",
    CsiRecorder.resolveLabel("walking", "anything") === "walking");
  report("custom label used when preset is not a known activity",
    CsiRecorder.resolveLabel("duduk", "jongkok dalam") === "jongkok dalam");
  report("blank preset + blank custom resolves empty",
    CsiRecorder.resolveLabel("berdiri", "  ") === "");
  report("safe id accepts generated names", CsiRecorder.isSafeRecordingId("20261030T000000Z_fall_forward_001"));
  report("unsafe id rejects traversal", CsiRecorder.isSafeRecordingId("../etc/passwd") === false);

  const id = CsiRecorder.makeRecordingId("fall_forward", new Date("2026-10-30T01:45:32.000Z"), 1);
  report("recording id shape", id === "20261030T014532Z_fall_forward_001");

  /* ---------------- activity labels + binary mapping (§7) ---------------- */
  report("eleven activity labels",
    arraysEqual(CsiRecorder.ACTIVITY_LABELS, [
      "fall_forward", "fall_backward", "fall_lemas", "fall_keseleo",
      "walking", "fast_sitting", "bending", "object_drop",
      "empty_room", "still_standing", "still_sitting",
    ]));
  report("four fall classes map to 'fall'",
    ["fall_forward", "fall_backward", "fall_lemas", "fall_keseleo"]
      .every((l) => CsiRecorder.binaryLabelOf(l) === "fall" && CsiRecorder.isFallLabel(l)));
  report("four non-fall activities map to 'non_fall'",
    ["walking", "fast_sitting", "bending", "object_drop"]
      .every((l) => CsiRecorder.binaryLabelOf(l) === "non_fall" && !CsiRecorder.isFallLabel(l)));
  report("idle anchors map to 'non_fall'",
    ["empty_room", "still_standing", "still_sitting"]
      .every((l) => CsiRecorder.binaryLabelOf(l) === "non_fall" && !CsiRecorder.isFallLabel(l)));
  report("unknown label has no binary mapping", CsiRecorder.binaryLabelOf("duduk") === null);

  /* ---------------- activity options (§9) ---------------- */
  report("walking forces still/still",
    JSON.stringify(CsiRecorder.buildActivityOptions("walking", { pre_action: "walking", post_action: "crawl" })) ===
      JSON.stringify({ pre_action: "still", post_action: "still" }));
  report("idle anchors force still/still",
    ["empty_room", "still_standing", "still_sitting"].every((l) =>
      JSON.stringify(CsiRecorder.buildActivityOptions(l, { pre_action: "walking", post_action: "crawl" })) ===
      JSON.stringify({ pre_action: "still", post_action: "still" })));
  report("fall accepts crawl post-action",
    JSON.stringify(CsiRecorder.buildActivityOptions("fall_forward", { pre_action: "walking", post_action: "crawl" })) ===
      JSON.stringify({ pre_action: "walking", post_action: "crawl" }));
  report("fall rejects invalid pre-action",
    CsiRecorder.buildActivityOptions("fall_forward", { pre_action: "crawl" }) === null);
  report("bending rejects crawl post-action",
    CsiRecorder.buildActivityOptions("bending", { post_action: "crawl" }) === null);
  report("bending accepts walking post-action",
    JSON.stringify(CsiRecorder.buildActivityOptions("bending", { pre_action: "still", post_action: "walking" })) ===
      JSON.stringify({ pre_action: "still", post_action: "walking" }));
  report("fast_sitting forces still post-action",
    CsiRecorder.buildActivityOptions("fast_sitting", { pre_action: "walking", post_action: "crawl" }).post_action === "still");
  report("unknown label has no options", CsiRecorder.buildActivityOptions("duduk", {}) === null);

  /* ---------------- timeline boundaries (§9) ---------------- */
  const boundaries = {
    fall_forward: [0, 4, 8, 12],
    fall_backward: [0, 4, 8, 12],
    fall_lemas: [0, 4, 8, 12],
    fall_keseleo: [0, 4, 8, 12],
    walking: [0, 3, 7, 10],
    fast_sitting: [0, 4, 6, 10],
    bending: [0, 3, 7, 10],
    object_drop: [0, 4, 6, 10],
    empty_room: [0, 10],
    still_standing: [0, 10],
    still_sitting: [0, 10],
  };
  for (const label of CsiRecorder.ACTIVITY_LABELS) {
    const timeline = CsiRecorder.buildActivityTimeline(label, { pre_action: "still", post_action: label.startsWith("fall") ? "crawl" : "walking" });
    const edges = [timeline[0].start_offset_s];
    timeline.forEach((p) => edges.push(p.end_offset_s));
    report(`timeline boundaries ${label}`, arraysEqual(edges, boundaries[label]));
    const expectedPhases = boundaries[label].length - 1;
    const lastBoundary = boundaries[label][boundaries[label].length - 1];
    report(`timeline spans 0..${lastBoundary} with ${expectedPhases} phase(s) ${label}`,
      timeline.length === expectedPhases && timeline[0].start_offset_s === 0 &&
      timeline[timeline.length - 1].end_offset_s === lastBoundary);
    report(`per-take duration equals last boundary ${label}`,
      CsiRecorder.durationFromTimeline(timeline) === lastBoundary);
  }
  report("fall_forward action instruction names direction",
    CsiRecorder.buildActivityTimeline("fall_forward", { pre_action: "still", post_action: "still" })[1].instruction ===
      "Jatuh ke depan sekarang!");
  report("manner falls action instruction names manner (no direction)",
    CsiRecorder.buildActivityTimeline("fall_lemas", { pre_action: "still", post_action: "still" })[1].instruction ===
      "Jatuh lemas sekarang!" &&
      CsiRecorder.buildActivityTimeline("fall_keseleo", { pre_action: "walking", post_action: "walk_slow" })[1].instruction ===
        "Jatuh keseleo sekarang!");

  /* phaseAtOffset resolves the active phase from an offset */
  const fallTl = CsiRecorder.buildActivityTimeline("fall_forward", { pre_action: "still", post_action: "crawl" });
  report("phaseAtOffset pre-action at 3s", CsiRecorder.phaseAtOffset("fall_forward", fallTl, 3).phase === "pre_action");
  report("phaseAtOffset fall_action at 5s", CsiRecorder.phaseAtOffset("fall_forward", fallTl, 5).phase === "fall_action");
  report("phaseAtOffset post_action at 10s", CsiRecorder.phaseAtOffset("fall_forward", fallTl, 10).phase === "post_action");

  /* ---------------- exact Indonesian cue text (§10.4) ---------------- */
  const fallCues = CsiRecorder.buildActivityCues("fall_forward", { pre_action: "still", post_action: "crawl" });
  const speech = fallCues.filter((c) => c.kind === "speech");
  report("fall_forward speech cues are exact spec phrases",
    arraysEqual(speech.map((c) => c.text), [
      "Mulai. Tetap diam.",
      "Jatuh ke depan sekarang!",
      "Selesai jatuh. Mulai merangkak perlahan.",
      "Rekaman selesai.",
    ]));
  report("fall cue offsets align to boundaries",
    arraysEqual(speech.map((c) => c.scheduled_offset_s), [0, 4, 8, 12]));
  report("every speech cue is paired with a tone",
    fallCues.filter((c) => c.kind === "tone").length === speech.length);

  const walkCues = CsiRecorder.buildActivityCues("walking", {});
  report("walking start cue keeps the pre-action phrase",
    walkCues.find((c) => c.cue_id === "start").text === "Mulai. Tetap diam.");
  report("walking action cue at 3s",
    walkCues.find((c) => c.cue_id === "walk_begin").scheduled_offset_s === 3 &&
      walkCues.find((c) => c.cue_id === "walk_begin").text === "Mulai berjalan sekarang!");

  const idleCues = CsiRecorder.buildActivityCues("still_standing", {});
  report("idle cues are start + end only",
    idleCues.length === 4 &&
      idleCues.some((c) => c.cue_id === "start" && c.scheduled_offset_s === 0) &&
      idleCues.some((c) => c.cue_id === "end" && c.scheduled_offset_s === 10));
  report("idle hold instruction is label-specific",
    CsiRecorder.buildActivityTimeline("empty_room", {})[0].instruction ===
      "Ruangan kosong — tidak ada orang");

  /* ---------------- annotations (§11) ---------------- */
  const ann = CsiRecorder.makeAnnotator(true, Date.parse("2026-10-30T00:00:00.000Z"));
  const capStart = 1000; /* monotonic ms at capture start */
  report("fall_start records monotonic offset",
    ann.mark("fall_start", 5200, capStart) === true && ann.snapshot().fall_start.offset_s === 4.2);
  report("first fall_start click wins", ann.mark("fall_start", 9000, capStart) === false);
  report("fall_impact recorded separately",
    ann.mark("fall_impact", 6000, capStart) === true && ann.snapshot().fall_impact.offset_s === 5);
  report("annotation_complete once both marked", ann.snapshot().annotation_complete === true);
  report("fall_start timestamp_utc derived from anchor",
    ann.snapshot().fall_start.timestamp_utc === "2026-10-30T00:00:04.200Z");
  report("unknown annotation kind rejected", ann.mark("bogus", 7000, capStart) === false);

  const nonFallAnn = CsiRecorder.makeAnnotator(false, Date.parse("2026-10-30T00:00:00.000Z"));
  report("non-fall takes cannot annotate", nonFallAnn.mark("fall_start", 5000, 1000) === false);

  /* ---------------- measured interval stats (addendum §I) ---------------- */
  const stats = CsiRecorder.computeIntervalStats([1000, 2000, 3000, 4500], 1);
  report("interval stats count deltas", stats.count === 3);
  report("interval stats mean_ms", stats.mean_ms === 1.167);
  report("interval stats flags deviating intervals", stats.deviating_count === 1);
  report("interval stats keeps target separate from measured", stats.target_period_ms === 1);
  report("interval stats needs two timestamps", CsiRecorder.computeIntervalStats([1000], 1) === null);

  /* ---------------- meta v3 (§6) ---------------- */
  const meta = CsiRecorder.buildMetaV3({
    recording_id: "rec_001",
    activity_label: "fall_forward",
    started_at_utc: "2026-10-30T00:00:00.000Z",
    ended_at_utc: "2026-10-30T00:00:10.000Z",
    actual_duration_s: 10.001,
    status: "complete",
    recording: { frames: 5, complete: true },
    activity: { pre_action: "still", post_action: "crawl" },
    timeline: fallTl,
  });
  report("meta v3 schema_version is 3", meta.schema_version === 3 && CsiRecorder.SCHEMA_VERSION === 3);
  report("meta v3 target_duration_s derives from timeline (fall = 12)", meta.target_duration_s === 12);
  report("meta v3 uses activity_label", meta.activity_label === "fall_forward" && meta.label === undefined);
  report("meta v3 nests frame counts under recording", meta.recording.frames === 5 && meta.recording.complete === true);
  report("meta v3 declares exactly two files",
    meta.files.frames_csv === "rec_001.frames.csv" && meta.files.meta_json === "rec_001.meta.json" &&
      Object.keys(meta.files).length === 2);
  report("meta v3 embeds events (no separate events.json)",
    meta.events && Array.isArray(meta.events.segments) && Array.isArray(meta.events.motion_samples));
  report("meta v3 payload_semantics drops discontinued file semantics",
    meta.payload_semantics.legacy_iq_csv === undefined && meta.payload_semantics.raw_iq_rows === undefined);
  report("meta v3 payload_semantics documents imag-first byte order",
    /imaginary first/i.test(meta.payload_semantics.iq_byte_order));
  report("meta v3 has annotation + audio_cues + quality nodes",
    meta.annotations && meta.audio_cues && meta.quality);
  report("meta v3 does not store redundant binary_label", meta.binary_label === undefined);

  /* ---------------- meta v3 stimulus block (comparison spec §7) ---------------- */
  report("meta v3 stimulus defaults to null mode with null measured counters",
    meta.stimulus && meta.stimulus.mode === null &&
      meta.stimulus.http.bytes_received === null &&
      meta.stimulus.http.endpoint === "http://speed.cloudflare.com/__down" &&
      meta.stimulus.ping.rtt_ms === null &&
      typeof meta.stimulus.ping.metrics_reason === "string" &&
      /meta\.events\.ping/.test(meta.stimulus.ping.metrics_reason));

  const metaStim = CsiRecorder.buildMetaV3({
    recording_id: "rec_002",
    activity_label: "fall_forward",
    started_at_utc: "2026-10-30T00:00:00.000Z",
    ended_at_utc: "2026-10-30T00:00:10.000Z",
    recording: { frames: 3, complete: true },
    timeline: fallTl,
    stimulus: {
      mode: "icmp_ping",
      configured_frequency_hz: 100,
      configured_interval_ms: 10,
      target_type: "default_gateway",
      target_ip: "192.168.1.1",
      http: { burst_bytes: 500000, bytes_received: 0 },
    },
  });
  report("meta v3 stimulus keeps measured values supplied by the recorder",
    metaStim.stimulus.mode === "icmp_ping" &&
      metaStim.stimulus.configured_frequency_hz === 100 &&
      metaStim.stimulus.target_ip === "192.168.1.1" &&
      metaStim.stimulus.http.burst_bytes === 500000);
  report("meta v3 ping counters stay null with reason, never backfilled from config",
    metaStim.stimulus.ping.ping_reply_count === null &&
      typeof metaStim.stimulus.ping.metrics_reason === "string" &&
      metaStim.stimulus.actual_frequency_hz === null);

  const segment = CsiRecorder.buildActivitySegment({
    label: "fall_forward",
    started: Date.parse("2026-10-30T00:00:00.000Z"),
    ended: Date.parse("2026-10-30T00:00:10.000Z"),
  });
  report("activity segment carries binary_label + span",
    segment.binary_label === "fall" && segment.start_offset_s === 0 && segment.end_offset_s === 10 &&
      segment.source === "recorder_session");

  /* ---------------- frames.csv lossless round-trip (§4) ---------------- */
  const rawBytes = new Int8Array([1, 2, 3, 4, 5, 6]);
  const validBytes = new Int8Array([1, 2, 3, 4]);
  const v3frames = [
    {
      seq: 7, rx_seq: 99, mac: "aa:bb:cc:dd:ee:ff", dmac: "11:22:33:44:55:66",
      rssi: -55, noise_floor: -97, channel: 6, secondary_channel: 0,
      sig_mode: 1, mcs: 7, rate: 11, bandwidth: 0, stbc: 0, data_type: 0,
      raw_len: rawBytes.length, valid_len: validBytes.length,
      lltf_len: 4, ht_ltf_len: 0, stbc_ht_ltf_len: 0,
      first_word_invalid: false, agc_gain: 3, fft_gain: -1,
      rx_gain_compensation: 0.5, ts_us: 1000, local_timestamp: 900,
      host_receive_monotonic_ns: 123456789, dropped: 0,
      rawBytes, validBytes,
    },
  ];

  report("base64 roundtrip", atob(CsiRecorder.bytesToBase64(rawBytes)) ===
    Array.from(rawBytes, (b) => String.fromCharCode(b & 0xff)).join(""));
  report("empty base64 stays empty", CsiRecorder.bytesToBase64(new Int8Array(0)) === "");

  const framesCsv = CsiRecorder.buildFramesCsv("rec_001", v3frames);
  const framesLines = framesCsv.trim().split("\n");
  report("frames header matches column list", framesLines[0] === CsiRecorder.FRAMES_HEADER);
  report("frames header has 32 columns", CsiRecorder.FRAMES_HEADER.split(",").length === 32);
  report("frames row count", framesLines.length === 2);
  const framesCols = framesLines[0].split(",");
  const framesVals = CsiRecorder.splitCsvLine(framesLines[1]);
  report("frames row column count matches header", framesCols.length === framesVals.length);
  const fRow = Object.fromEntries(framesCols.map((k, i) => [k, framesVals[i]]));
  report("frames keeps both raw and valid base64",
    fRow.raw_b64 === CsiRecorder.bytesToBase64(rawBytes) &&
    fRow.valid_b64 === CsiRecorder.bytesToBase64(validBytes));
  report("frames records all three clocks",
    fRow.callback_timestamp_us === "1000" &&
    fRow.rx_ctrl_timestamp_us === "900" &&
    fRow.host_receive_monotonic_ns === "123456789");
  report("frames marks payload_ok true when lengths match", fRow.payload_ok === "true");

  const badLen = [{ ...v3frames[0], raw_len: 999 }];
  const badRow = CsiRecorder.splitCsvLine(CsiRecorder.buildFramesCsv("rec", badLen).trim().split("\n")[1]);
  report("frames flags payload_ok false on length mismatch",
    badRow[framesCols.indexOf("payload_ok")] === "false");

  const missing = [{ ...v3frames[0], rx_seq: null, first_word_invalid: null }];
  const naRow = CsiRecorder.splitCsvLine(CsiRecorder.buildFramesCsv("rec", missing).trim().split("\n")[1]);
  report("unavailable fields are 'na', never guessed",
    naRow[framesCols.indexOf("rx_seq")] === "na" &&
    naRow[framesCols.indexOf("first_word_invalid")] === "na");

  const parsed = CsiRecorder.parseFramesCsv(framesCsv);
  report("parseFramesCsv round-trips payload bytes losslessly",
    parsed.frames.length === 1 &&
    arraysEqual(Array.from(parsed.frames[0].rawBytes), Array.from(rawBytes.map((b) => b & 0xff))) &&
    arraysEqual(Array.from(parsed.frames[0].validBytes), Array.from(validBytes.map((b) => b & 0xff))));
  report("parseFramesCsv restores metadata + clocks",
    parsed.frames[0].seq === 7 && parsed.frames[0].rx_seq === 99 &&
    parsed.frames[0].ts_us === 1000 && parsed.frames[0].first_word_invalid === false &&
    parsed.frames[0].payload_ok === true);
  report("parseFramesCsv maps 'na' back to null",
    CsiRecorder.parseFramesCsv(CsiRecorder.buildFramesCsv("rec", missing)).frames[0].rx_seq === null);

  /* ---------------- legacy builders (manual export only, §5) ---------------- */
  const bytes = new Int8Array([1, 2, 3, 4]);
  const iq = CsiRecorder.decodePairs(bytes, 0);
  report("int8 pairs keep [imag, real] order", iq.length === 2 && iq[0][0] === 1 && iq[0][1] === 2);
  const docPairs = CsiRecorder.decodePairsDocOrder(new Int8Array([10, 20, 30, 40]), 0);
  report("doc order maps imag first", docPairs[0].imag === 10 && docPairs[0].real === 20);

  const legacyFrames = [{ seq: 1, ts_us: 100, mac: "aa:bb:cc:dd:ee:ff", rssi: -40, data_type: 0, dropped: 0, validBytes: bytes, iq }];
  const csiCsv = CsiRecorder.buildCsiDataCsv(legacyFrames, { label: "duduk", takeSeq: 1 });
  report("legacy CSI_DATA header intact", csiCsv.startsWith(CsiRecorder.CSI_DATA_HEADER + "\n"));
  report("legacy CSI_DATA row tagged", csiCsv.includes("CSI_DATA,1,100,1,duduk,aa:bb:cc:dd:ee:ff"));

  const iqCsv = CsiRecorder.buildIqCsv(legacyFrames);
  report("legacy I/Q columns are 2 per subcarrier",
    iqCsv.split("\n")[0].split(",").filter((n) => n.startsWith("sc")).length === 4);
  const parsedIq = CsiRecorder.parseIqCsv(iqCsv);
  report("legacy parseIqCsv roundtrip", parsedIq.subcarriers === 2 && parsedIq.frames[0].iq[1][1] === 4);

  const rawIqCsv = CsiRecorder.buildRawIqCsv(v3frames);
  const rawIqLines = rawIqCsv.trim().split("\n");
  report("legacy raw_iq emits one row per payload",
    rawIqLines[0] === CsiRecorder.RAW_IQ_HEADER && rawIqLines.length === 3);

  const events = CsiRecorder.buildEvents({
    recordingId: "rec_001", label: "duduk",
    started: new Date("2026-10-27T05:00:00.000Z"),
    ended: new Date("2026-10-27T05:00:05.000Z"),
    motionSamples: [], motionPeer: "ap",
  });
  report("legacy events has one activity segment",
    events.segments.length === 1 && events.segments[0].end_offset_s === 5);

  const metaV2 = CsiRecorder.buildMetaV2({
    id: "rec_001", label: "duduk", batch_id: "batch_9",
    started_at_utc: "2026-10-27T05:00:00.000Z",
    ended_at_utc: "2026-10-27T05:00:05.000Z",
  });
  report("legacy metaV2 stays pinned at schema_version 2", metaV2.schema_version === 2);
  report("legacy metaV2 keeps v1 format key", metaV2.format === "wifi_sensing_demo_csi_v1");

  /* batch: duration is fixed at 10 s and no longer user-configurable (§8) */
  const batchSettings = CsiRecorder.parseBatchSettings({ takes: "100", gapS: "0" });
  report("batch accepts 100 takes and pins duration to 10 s",
    batchSettings?.takes === 100 && batchSettings.durationS === 10 && batchSettings.gapS === 0);
  report("batch rejects over 100 takes",
    CsiRecorder.parseBatchSettings({ takes: 101, gapS: 0 }) === null);
  report("batch rejects negative gap",
    CsiRecorder.parseBatchSettings({ takes: 10, gapS: -1 }) === null);

  /* §8: the configured gap is a pre-roll that runs before every take, including
   * the first one, not only between consecutive takes. */
  const schedule3 = CsiRecorder.buildBatchSchedule({ takes: 3, gapS: 5 });
  report("schedule pre-rolls every take including the first",
    schedule3.length === 3 &&
      schedule3.every((slot, i) => slot.take === i + 1 && slot.pre_roll_s === 5));
  const scheduleSingle = CsiRecorder.buildBatchSchedule({ takes: 1, gapS: 8 });
  report("single take still gets its pre-roll",
    scheduleSingle.length === 1 && scheduleSingle[0].pre_roll_s === 8);
  report("gap 0 yields no pre-roll",
    CsiRecorder.buildBatchSchedule({ takes: 2, gapS: 0 })
      .every((slot) => slot.pre_roll_s === 0));
  report("schedule rejects invalid settings",
    CsiRecorder.buildBatchSchedule({ takes: 101, gapS: 5 }) === null);

  /* §8 / ACTION_PLAN 2.8: monotonic take numbering + batch/session identity */
  const offsetSchedule = CsiRecorder.buildBatchSchedule({ takes: 3, gapS: 0, startTake: 7 });
  report("schedule honours startTake offset (cross-restart monotonic)",
    offsetSchedule.length === 3 &&
      offsetSchedule.map((slot) => slot.take).join(",") === "7,8,9");
  report("schedule defaults to 1 when startTake omitted",
    CsiRecorder.buildBatchSchedule({ takes: 2, gapS: 0 }).map((s) => s.take).join(",") === "1,2");

  report("parseTakeNumber reads trailing _NNN",
    CsiRecorder.parseTakeNumber("20261030T014532Z_fall_forward_012") === 12 &&
      CsiRecorder.parseTakeNumber("no_number_here") === null);
  const libraryRows = [
    { id: "20261030T014532Z_fall_forward_003", activity_label: "fall_forward" },
    { id: "20261030T014600Z_fall_forward_007", activity_label: "fall_forward" },
    { id: "20261030T014610Z_walking_005", activity_label: "walking" },
  ];
  report("nextTakeNumber continues the label's highest take",
    CsiRecorder.nextTakeNumber(libraryRows, "fall_forward") === 8);
  report("nextTakeNumber is label-scoped",
    CsiRecorder.nextTakeNumber(libraryRows, "walking") === 6);
  report("nextTakeNumber starts at 1 for an unseen label",
    CsiRecorder.nextTakeNumber(libraryRows, "bending") === 1);
  report("nextTakeNumber accepts bare id strings",
    CsiRecorder.nextTakeNumber(["..._fall_forward_004"], "fall_forward") === 5);

  report("makeBatchId and makeSessionId are distinct namespaces",
    CsiRecorder.makeBatchId(new Date("2026-11-06T00:00:00.000Z"), "abc123") ===
      "batch_20261106T000000Z_abc123" &&
      CsiRecorder.makeSessionId(new Date("2026-11-06T00:00:00.000Z"), "abc123") ===
      "sess_20261106T000000Z_abc123");

  const meta28 = CsiRecorder.buildMetaV3({
    recording_id: "20261106T000000Z_walking_008",
    activity_label: "walking",
    session_id: "sess_20261106T000000Z_abc123",
    batch: { batch_id: "batch_20261106T000000Z_def456", take: 8, take_count: 1, gap_s: 5 },
    abort: { aborted_slots: [{ take: 9, reason: "cancelled" }], cancelled: true },
  });
  report("meta exposes top-level session_id and batch_id (dataset_io groups on these)",
    meta28.session_id === "sess_20261106T000000Z_abc123" &&
      meta28.batch_id === "batch_20261106T000000Z_def456");
  report("meta records batch for a single take (batch_id mandatory)",
    meta28.batch && meta28.batch.take === 8);
  report("meta carries abort trace",
    meta28.abort && meta28.abort.aborted_slots.length === 1 && meta28.abort.cancelled === true);
  const metaNoAbort = CsiRecorder.buildMetaV3({ recording_id: "x", activity_label: "walking" });
  report("meta abort stays null when nothing was aborted",
    metaNoAbort.abort === null && metaNoAbort.session_id === null && metaNoAbort.batch_id === null);

  /* ACTION_PLAN 4.2/3.3: subject_id must never be blank in new recordings —
   * an unset web field means "subject 1", not "unknown". */
  report("normalizeSubjectId defaults blank/null/whitespace to '1'",
    CsiRecorder.DEFAULT_SUBJECT_ID === "1" &&
      CsiRecorder.normalizeSubjectId(undefined) === "1" &&
      CsiRecorder.normalizeSubjectId(null) === "1" &&
      CsiRecorder.normalizeSubjectId("") === "1" &&
      CsiRecorder.normalizeSubjectId("   ") === "1");
  report("normalizeSubjectId trims and keeps an explicit value as a string",
    CsiRecorder.normalizeSubjectId("  3  ") === "3" &&
      CsiRecorder.normalizeSubjectId("S2") === "S2");
  report("meta defaults subject_id to '1' when the field is empty",
    metaNoAbort.subject_id === "1");
  const metaSubject = CsiRecorder.buildMetaV3({
    recording_id: "x", activity_label: "walking", subject_id: " 2 ",
  });
  report("meta records the operator-supplied subject_id", metaSubject.subject_id === "2");

  const incomplete = CsiRecorder.recordingCompleteness({ frames: [], droppedStart: 0, droppedEnd: 0, disconnected: false, stimulusOn: true });
  report("zero frames incomplete", incomplete.complete === false);
  const dropped = CsiRecorder.recordingCompleteness({ frames: v3frames, droppedStart: 1, droppedEnd: 5, disconnected: false, stimulusOn: true });
  report("dropped delta incomplete", dropped.complete === false && dropped.dropped_delta === 4);

  if (process.exitCode) {
    console.error(`GAGAL: ${path.basename(__filename)}`);
  }
}

main();
