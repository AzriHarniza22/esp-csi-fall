/*
 * Shared CSI dataset helpers for the web monitor and Node tests.
 * Browser: global CsiRecorder. Node: module.exports.
 *
 * v3 (recording-pipeline-implementation.md):
 * - exactly two output files per take: <id>.frames.csv + <id>.meta.json
 * - eight activity labels with fixed 10 s timelines and Indonesian cues
 * - events/annotations/audio-cue status live inside meta.json
 * - legacy derived-file builders (csi_data/iq/raw_iq/events) remain exported
 *   for MANUAL export only; the recorder never runs them automatically.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.CsiRecorder = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* Activity labels (spec §7)                                           */
  /* ------------------------------------------------------------------ */

  const ACTIVITY_LABELS = [
    "fall_forward", "fall_backward", "fall_left", "fall_right",
    "walking", "fast_sitting", "bending", "object_drop",
  ];

  const BINARY_LABELS = {
    fall_forward: "fall",
    fall_backward: "fall",
    fall_left: "fall",
    fall_right: "fall",
    walking: "non_fall",
    fast_sitting: "non_fall",
    bending: "non_fall",
    object_drop: "non_fall",
  };

  const FALL_DIRECTIONS = {
    fall_forward: "depan",
    fall_backward: "belakang",
    fall_left: "kiri",
    fall_right: "kanan",
  };

  const PRE_ACTIONS = ["still", "walking"];
  const POST_ACTIONS = ["still", "crawl", "walk_slow"];

  const TARGET_DURATION_S = 10;

  function binaryLabelOf(label) {
    return BINARY_LABELS[label] || null;
  }

  function isFallLabel(label) {
    return binaryLabelOf(label) === "fall";
  }

  function isKnownActivity(label) {
    return Object.prototype.hasOwnProperty.call(BINARY_LABELS, String(label || ""));
  }

  /*
   * Phase boundaries per activity (spec §9). Walking has a fixed timeline;
   * the others take pre/post action choices that must be resolved BEFORE the
   * recording starts so the timeline never changes mid-take.
   */
  const TIMELINE_DEFS = {
    fall_forward: { kind: "fall", boundaries: [0, 4, 6, 10] },
    fall_backward: { kind: "fall", boundaries: [0, 4, 6, 10] },
    fall_left: { kind: "fall", boundaries: [0, 4, 6, 10] },
    fall_right: { kind: "fall", boundaries: [0, 4, 6, 10] },
    walking: { kind: "walking", boundaries: [0, 3, 7, 10] },
    fast_sitting: { kind: "fast_sitting", boundaries: [0, 4, 6, 10] },
    bending: { kind: "bending", boundaries: [0, 3, 7, 10] },
    object_drop: { kind: "object_drop", boundaries: [0, 4, 6, 10] },
  };

  const PHASE_IDS = {
    fall_forward: ["pre_action", "fall_action", "post_action"],
    fall_backward: ["pre_action", "fall_action", "post_action"],
    fall_left: ["pre_action", "fall_action", "post_action"],
    fall_right: ["pre_action", "fall_action", "post_action"],
    walking: ["pre_action", "walking", "post_action"],
    fast_sitting: ["pre_action", "action", "post_action"],
    bending: ["pre_action", "action", "post_action"],
    object_drop: ["pre_action", "action", "post_action"],
  };

  /*
   * Validate and normalise the per-activity phase choices. Returns
   * { pre_action, post_action } or null when the combination is invalid for
   * the label. walking and fast_sitting have restricted option sets.
   */
  function buildActivityOptions(label, options) {
    const opts = options || {};
    if (!isKnownActivity(label)) {
      return null;
    }
    const def = TIMELINE_DEFS[label];
    if (def.kind === "walking") {
      return { pre_action: "still", post_action: "still" };
    }
    const pre = String(opts.pre_action || "still");
    if (PRE_ACTIONS.indexOf(pre) < 0) {
      return null;
    }
    if (def.kind === "fall") {
      const post = String(opts.post_action || "still");
      if (POST_ACTIONS.indexOf(post) < 0) {
        return null;
      }
      return { pre_action: pre, post_action: post };
    }
    if (def.kind === "fast_sitting") {
      /* Post-action is always "diam" (spec §9.3). */
      return { pre_action: pre, post_action: "still" };
    }
    /* bending and object_drop: pre and post are both selectable (still|walking). */
    const post = String(opts.post_action || "still");
    if (PRE_ACTIONS.indexOf(post) < 0) {
      return null;
    }
    return { pre_action: pre, post_action: post };
  }

  const PRE_INSTRUCTION = {
    still: "Tetap diam",
    walking: "Berjalan seperti biasa",
  };

  /*
   * Timeline of phases with offsets in seconds and the visual instruction
   * shown in the GUI (spec §9). Built once before the recording starts.
   */
  function buildActivityTimeline(label, options) {
    const opts = buildActivityOptions(label, options);
    if (!opts) {
      return null;
    }
    const def = TIMELINE_DEFS[label];
    const ids = PHASE_IDS[label];
    const phases = [];
    for (let i = 0; i < ids.length; i++) {
      phases.push({
        phase: ids[i],
        start_offset_s: def.boundaries[i],
        end_offset_s: def.boundaries[i + 1],
        instruction: phaseInstruction(label, ids[i], opts),
      });
    }
    return phases;
  }

  function phaseInstruction(label, phaseId, opts) {
    const def = TIMELINE_DEFS[label];
    if (phaseId === "pre_action") {
      return PRE_INSTRUCTION[opts.pre_action] || PRE_INSTRUCTION.still;
    }
    if (phaseId === "fall_action") {
      return `Jatuh ke ${FALL_DIRECTIONS[label]} sekarang!`;
    }
    if (phaseId === "walking") {
      return "Berjalan";
    }
    if (phaseId === "action") {
      if (def.kind === "fast_sitting") {
        return "Jongkok atau duduk cepat";
      }
      if (def.kind === "bending") {
        return "Membungkuk lalu berdiri";
      }
      return "Jatuhkan benda";
    }
    /* post_action */
    if (def.kind === "walking") {
      return "Berhenti dan diam";
    }
    if (def.kind === "fall") {
      if (opts.post_action === "crawl") return "Merangkak perlahan";
      if (opts.post_action === "walk_slow") return "Bergerak perlahan";
      return "Tetap diam";
    }
    return opts.post_action === "walking" ? "Berjalan" : "Tetap diam";
  }

  function phaseAtOffset(label, timeline, offsetS) {
    if (!Array.isArray(timeline)) {
      return null;
    }
    for (const phase of timeline) {
      if (offsetS >= phase.start_offset_s && offsetS < phase.end_offset_s) {
        return phase;
      }
    }
    return timeline.length ? timeline[timeline.length - 1] : null;
  }

  /* ------------------------------------------------------------------ */
  /* Audio + visual cue text (spec §10.4)                                */
  /* ------------------------------------------------------------------ */

  const PRE_SPEECH = {
    still: "Tetap diam.",
    walking: "Berjalan seperti biasa.",
  };

  const FALL_POST_SPEECH = {
    still: "Selesai jatuh. Tetap diam.",
    crawl: "Selesai jatuh. Mulai merangkak perlahan.",
    walk_slow: "Selesai jatuh. Bergerak perlahan.",
  };

  const GENERIC_POST_SPEECH = {
    still: "Selesai. Tetap diam.",
    walking: "Selesai. Mulai berjalan.",
  };

  const CUE_END_TEXT = "Rekaman selesai.";

  /*
   * Tone patterns for the Web Audio scheduler: [frequencyHz, durationS] pairs
   * played back to back. `action` (the fall/impact phase) gets a distinct
   * urgent pattern so it is recognisable without looking at the screen.
   */
  const TONE_PATTERNS = {
    start: [[880, 0.12]],
    phase: [[660, 0.12]],
    action: [[880, 0.09], [1174.7, 0.09], [1568, 0.14]],
    end: [[523.25, 0.35]],
  };

  /*
   * Build the ordered cue plan for one take. Every entry has:
   *   cue_id, kind ("speech"|"tone"), scheduled_offset_s, text (speech only),
   *   tone (pattern name), phase (phase id the cue belongs to).
   * The recorder fires each cue when the monotonic clock passes its offset;
   * playback status is recorded per cue in meta.audio_cues.events.
   */
  function buildActivityCues(label, options) {
    const opts = buildActivityOptions(label, options);
    if (!opts) {
      return null;
    }
    const def = TIMELINE_DEFS[label];
    const b = def.boundaries;
    const cues = [];
    const push = (cue) => cues.push(cue);

    /* t=0: start */
    push({ cue_id: "start", kind: "speech", scheduled_offset_s: b[0], phase: "pre_action", text: `Mulai. ${PRE_SPEECH[opts.pre_action]}` });
    push({ cue_id: "start_tone", kind: "tone", scheduled_offset_s: b[0], phase: "pre_action", tone: "start" });

    if (def.kind === "walking") {
      push({ cue_id: "walk_begin", kind: "speech", scheduled_offset_s: b[1], phase: "walking", text: "Mulai berjalan sekarang!" });
      push({ cue_id: "walk_begin_tone", kind: "tone", scheduled_offset_s: b[1], phase: "walking", tone: "action" });
      push({ cue_id: "walk_end", kind: "speech", scheduled_offset_s: b[2], phase: "post_action", text: "Berhenti berjalan. Tetap diam." });
      push({ cue_id: "walk_end_tone", kind: "tone", scheduled_offset_s: b[2], phase: "post_action", tone: "phase" });
    } else if (def.kind === "fall") {
      push({ cue_id: "fall_action", kind: "speech", scheduled_offset_s: b[1], phase: "fall_action", text: `Jatuh ke ${FALL_DIRECTIONS[label]} sekarang!` });
      push({ cue_id: "fall_action_tone", kind: "tone", scheduled_offset_s: b[1], phase: "fall_action", tone: "action" });
      push({ cue_id: "post_action", kind: "speech", scheduled_offset_s: b[2], phase: "post_action", text: FALL_POST_SPEECH[opts.post_action] });
      push({ cue_id: "post_action_tone", kind: "tone", scheduled_offset_s: b[2], phase: "post_action", tone: "phase" });
    } else if (def.kind === "fast_sitting") {
      push({ cue_id: "action", kind: "speech", scheduled_offset_s: b[1], phase: "action", text: "Jongkok atau duduk cepat sekarang!" });
      push({ cue_id: "action_tone", kind: "tone", scheduled_offset_s: b[1], phase: "action", tone: "action" });
      push({ cue_id: "post_action", kind: "speech", scheduled_offset_s: b[2], phase: "post_action", text: GENERIC_POST_SPEECH.still });
      push({ cue_id: "post_action_tone", kind: "tone", scheduled_offset_s: b[2], phase: "post_action", tone: "phase" });
    } else if (def.kind === "bending") {
      push({ cue_id: "action", kind: "speech", scheduled_offset_s: b[1], phase: "action", text: "Mulai membungkuk, lalu berdiri!" });
      push({ cue_id: "action_tone", kind: "tone", scheduled_offset_s: b[1], phase: "action", tone: "action" });
      push({ cue_id: "post_action", kind: "speech", scheduled_offset_s: b[2], phase: "post_action", text: "Kembali ke posisi awal." });
      push({ cue_id: "post_action_tone", kind: "tone", scheduled_offset_s: b[2], phase: "post_action", tone: "phase" });
    } else {
      /* object_drop */
      push({ cue_id: "action", kind: "speech", scheduled_offset_s: b[1], phase: "action", text: "Jatuhkan benda sekarang!" });
      push({ cue_id: "action_tone", kind: "tone", scheduled_offset_s: b[1], phase: "action", tone: "action" });
      push({ cue_id: "post_action", kind: "speech", scheduled_offset_s: b[2], phase: "post_action", text: GENERIC_POST_SPEECH[opts.post_action === "walking" ? "walking" : "still"] });
      push({ cue_id: "post_action_tone", kind: "tone", scheduled_offset_s: b[2], phase: "post_action", tone: "phase" });
    }

    push({ cue_id: "end_tone", kind: "tone", scheduled_offset_s: b[3], phase: "end", tone: "end" });
    push({ cue_id: "end", kind: "speech", scheduled_offset_s: b[3], phase: "end", text: CUE_END_TEXT });
    return cues;
  }

  /* ------------------------------------------------------------------ */
  /* Annotations (spec §11)                                              */
  /* ------------------------------------------------------------------ */

  /*
   * Annotation bookkeeping. Offsets come from the monotonic clock relative to
   * capture start; timestamp_utc is derived from the recording start anchor.
   * Nothing is ever auto-filled from the cue schedule.
   */
  function makeAnnotator(isFall, startedDateMs) {
    const state = { fall_start: null, fall_impact: null };
    return {
      mark(kind, monotonicNowMs, captureStartMonotonicMs) {
        if (!isFall) {
          return false;
        }
        if (kind !== "fall_start" && kind !== "fall_impact") {
          return false;
        }
        if (state[kind]) {
          /* first valid click wins; duplicates are ignored (spec §11) */
          return false;
        }
        const offsetS = (Number(monotonicNowMs) - Number(captureStartMonotonicMs)) / 1000;
        if (!Number.isFinite(offsetS) || offsetS < 0) {
          return false;
        }
        const utcMs = Number(startedDateMs) + offsetS * 1000;
        state[kind] = {
          offset_s: Math.round(offsetS * 1000) / 1000,
          timestamp_utc: new Date(utcMs).toISOString(),
        };
        return true;
      },
      snapshot() {
        return {
          fall_start: state.fall_start,
          fall_impact: state.fall_impact,
          annotation_complete: Boolean(state.fall_start && state.fall_impact),
        };
      },
    };
  }

  /* ------------------------------------------------------------------ */
  /* Sampling-interval statistics (addendum §I)                          */
  /* ------------------------------------------------------------------ */

  /*
   * Measure the ACTUAL sampling interval distribution from the device clock
   * (callback_timestamp_us). Never resample; never conflate target and actual.
   * Returns null when fewer than two usable timestamps are available.
   */
  function computeIntervalStats(timestampsUs, targetPeriodMs) {
    const ts = (Array.isArray(timestampsUs) ? timestampsUs : [])
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v) && v > 0)
      .sort((a, b) => a - b);
    if (ts.length < 2) {
      return null;
    }
    const deltas = [];
    for (let i = 1; i < ts.length; i++) {
      const d = (ts[i] - ts[i - 1]) / 1000; /* us -> ms */
      if (d >= 0) {
        deltas.push(d);
      }
    }
    if (!deltas.length) {
      return null;
    }
    const count = deltas.length;
    const mean = deltas.reduce((a, b) => a + b, 0) / count;
    const sorted = deltas.slice().sort((a, b) => a - b);
    const median = count % 2
      ? sorted[(count - 1) / 2]
      : (sorted[count / 2 - 1] + sorted[count / 2]) / 2;
    let variance = 0;
    for (const d of deltas) {
      variance += (d - mean) * (d - mean);
    }
    const std_dev = Math.sqrt(variance / count);
    const target = Number(targetPeriodMs) > 0 ? Number(targetPeriodMs) : null;
    let deviating = 0;
    if (target !== null) {
      for (const d of deltas) {
        if (Math.abs(d - target) > 0.2 * target) {
          deviating++;
        }
      }
    }
    const round = (v) => Math.round(v * 1000) / 1000;
    return {
      target_period_ms: target,
      count,
      mean_ms: round(mean),
      median_ms: round(median),
      min_ms: round(sorted[0]),
      max_ms: round(sorted[count - 1]),
      jitter_ms: round(std_dev),
      deviating_count: target === null ? null : deviating,
      deviating_threshold: target === null ? null : "±20% of target",
    };
  }

  /* ------------------------------------------------------------------ */
  /* meta.json v3 (spec §6)                                              */
  /* ------------------------------------------------------------------ */

  const SCHEMA_VERSION = 3;

  const PAYLOAD_SEMANTICS = {
    raw: "unfiltered driver CSI buffer (wifi_csi_info_t.buf, includes invalid subcarriers); stored verbatim as base64 in frames.csv raw_b64",
    valid: "esp-radar component-filtered payload, layout LLTF | HT-LTF | STBC-HT-LTF; stored verbatim as base64 in frames.csv valid_b64",
    valid_selection_rule: "esp-radar concatenates the enabled LTF sub-ranges of the driver buffer according to csi_config (lltf_en, htltf_en, stbc_htltf2_en); the vendored patch makes that concatenation first_word_invalid-aware, so when the flag is true any range reaching raw bytes 0..3 is clamped to start at byte 4 and the invalid leading pair is not copied. Apart from that clamp no bytes are added, reordered or padded by the recorder",
    data_type: "0 = int8 (1 byte per component), 1 = int16 little-endian (2 bytes per component)",
    iq_byte_order: "imaginary first, then real (ESP-IDF v5.5.3 api-guides/wifi.rst)",
    decoding: "pairs of (imag, real) components in payload order; slice the LLTF as the leading lltf_len bytes (lltf_len/2 pairs for int8, lltf_len/4 for int16), never a fixed 52 - HT-LTF follows the LLTF segment. No trimming, padding, smoothing or resampling is applied in the browser",
    first_word_invalid: "when true the first four bytes of the driver CSI buffer (raw_b64) are invalid per ESP-IDF v5.5.3 esp_wifi_types_native.h: 2 complex pairs for int8 (data_type 0), 1 pair for int16 (data_type 1). raw_b64 keeps those bytes verbatim; valid_b64 is now produced by a first_word_invalid-aware esp-radar compaction so the invalid leading pair is excluded, which shortens lltf_len/valid_len by 2 bytes (int8) for layouts whose LLTF sub-range reaches raw byte 2 (ESP32 secondary-channel NONE). Consumers reconstruct subcarrier position from lltf_source_ranges + first_word_invalid rather than assuming a fixed 52-pair LLTF",
    lltf_source_ranges: "ESP32 byte offsets into raw_b64 copied into the LLTF segment of valid_b64, before the first_word_invalid clamp: secondary NONE {{76,128},{2,54}} (so recorded LLTF pair 26 was raw pair 1 = bytes 2-3, the invalid word); secondary BELOW/ABOVE {{12,64},{66,118}} (never touch bytes 0-3). int8 pair k occupies raw bytes 2k..2k+1. When first_word_invalid the range start 2 becomes 4, dropping that pair",
    field_provenance: "frames.csv columns seq..rx_gain_compensation, first_word_invalid and rx_seq are native driver/firmware values forwarded verbatim; recording_id, frame_sequence, host_receive_monotonic_ns, payload_ok are host-computed; dropped is the device-side app instrumentation counter value at emission time",
    clocks: "callback_timestamp_us and rx_ctrl_timestamp_us use the device monotonic clock (esp_timer, us); host_receive_monotonic_ns uses the browser performance.now() clock (ms * 1e6); started_at_utc uses the host wall clock. meta.clock_anchor stores a same-instant (performance_now_ms, date_now_ms) pair so host monotonic offsets can be converted to UTC",
  };

  /*
   * Build the single metadata file for one take. `fields` supplies measured
   * values only; anything unavailable must be null, never guessed.
   * Required fields: recording_id, activity_label, started_at_utc,
   * ended_at_utc, actual_duration_s, status, timeline, activity options.
   */
  function buildMetaV3(fields) {
    const id = fields.recording_id;
    const label = fields.activity_label;
    const meta = {
      schema_version: SCHEMA_VERSION,
      recording_id: id,
      activity_label: label,
      created_at_utc: fields.created_at_utc || new Date().toISOString(),
      started_at_utc: fields.started_at_utc || null,
      ended_at_utc: fields.ended_at_utc || null,
      target_duration_s: TARGET_DURATION_S,
      actual_duration_s: Number.isFinite(Number(fields.actual_duration_s))
        ? Math.round(Number(fields.actual_duration_s) * 1000) / 1000
        : null,
      status: fields.status || null,

      clock_anchor: fields.clock_anchor || null,

      wifi: Object.assign({
        channel: null,
        secondary_channel: null,
        ap_mac: null,
      }, fields.wifi || {}),

      acquisition: Object.assign({
        csi_period_ms: null,
        csi_period_note: "csi_period_ms is the firmware CSI-stream throttle reported in the hello message; 0 means unthrottled (emit on every CSI callback), >0 throttles emission to that many ms. Actual intervals are measured in quality.sampling_intervals_ms and may differ.",
        csi_config: fields.csi_config || null,
      }, fields.acquisition || {}),

      /*
       * Traffic stimulus for the HTTP-vs-Ping comparison experiment (spec §7).
       * Counters are measured values captured from the firmware `stimulus`
       * message at recording start and stop; anything the firmware does not
       * surface stays null with an explanatory reason, never backfilled with
       * the configured value.
       */
      stimulus: (function (st) {
        st = st || {};
        return {
          mode: st.mode === undefined ? null : st.mode,
          target_type: st.target_type === undefined ? null : st.target_type,
          target_ip: st.target_ip === undefined ? null : st.target_ip,
          configured_frequency_hz: st.configured_frequency_hz === undefined ? null : st.configured_frequency_hz,
          configured_interval_ms: st.configured_interval_ms === undefined ? null : st.configured_interval_ms,
          actual_frequency_hz: st.actual_frequency_hz === undefined ? null : st.actual_frequency_hz,
          csi_hz_x10: st.csi_hz_x10 === undefined ? null : st.csi_hz_x10,
          http: Object.assign({
            endpoint: "http://speed.cloudflare.com/__down",
            burst_bytes: null,
            read_chunk_bytes: 4096,
            pause_ms: null,
            timeout_ms: 15000,
            requests: null,
            burst_success: null,
            burst_failed: null,
            bytes_requested: null,
            bytes_received: null,
            active_ms: null,
            idle_ms: null,
            errors: null,
          }, st.http || {}),
          ping: Object.assign({
            ping_request_count: null,
            ping_reply_count: null,
            ping_timeout_count: null,
            rtt_ms: null,
            metrics_reason: "aggregate FSM ping counters come from the firmware stimulus message; per-reply seqno/rtt/timeout detail is captured separately in meta.events.ping when the diagnostic take ran (Prioritas 1, vendored esp_wifi_sensing per-reply callback)",
          }, st.ping || {}),
          started_at_utc: st.started_at_utc === undefined ? null : st.started_at_utc,
          stopped_at_utc: st.stopped_at_utc === undefined ? null : st.stopped_at_utc,
          counters_scope: "cumulative since the mode was applied at recording start (firmware resets HTTP counters on SET_STIMULUS_MODE)",
        };
      })(fields.stimulus),

      recording: Object.assign({
        frames: 0,
        dropped_on_device: null,
        dropped_delta: null,
        complete: false,
      }, fields.recording || {}),

      activity: Object.assign({
        pre_action: null,
        post_action: null,
      }, fields.activity || {}),

      timeline: Array.isArray(fields.timeline) ? fields.timeline : [],

      annotations: Object.assign({
        fall_start: null,
        fall_impact: null,
        annotation_complete: false,
      }, fields.annotations || {}),

      audio_cues: Object.assign({
        enabled: false,
        mode: "voice_and_tone",
        language: "id-ID",
        voice: null,
        volume: null,
        preflight: null,
        protocol_deviation: null,
        events: [],
      }, fields.audio_cues || {}),

      quality: Object.assign({
        payload_ok_frames: null,
        payload_bad_frames: null,
        rx_seq_gaps: null,
        first_word_invalid_frames: null,
        sampling_intervals_ms: null,
      }, fields.quality || {}),

      payload_semantics: PAYLOAD_SEMANTICS,

      events: Object.assign({
        segments: [],
        motion_samples: [],
      }, fields.events || {}),

      /* Prioritas 1 diagnostics: per-event ping/csi_diag live inside events
       * (see fields.events.ping / fields.events.csi_diag); session_stats and
       * boundary are scalar summaries. Absent (null) for recordings that never
       * ran the diagnostic path, so old datasets and HTTP recordings stay valid. */
      session_stats: fields.session_stats || null,
      boundary: fields.boundary || null,

      batch: fields.batch || null,

      files: {
        frames_csv: fields.files && fields.files.frames_csv ? fields.files.frames_csv : `${id}.frames.csv`,
        meta_json: fields.files && fields.files.meta_json ? fields.files.meta_json : `${id}.meta.json`,
      },
    };
    return meta;
  }

  /*
   * The whole-take activity segment, merged into meta.events.segments
   * (replaces the separate events.json file; spec §5, §15).
   */
  function buildActivitySegment({ label, started, ended, startedOffsetS, endedOffsetS }) {
    const startOffset = Number.isFinite(Number(startedOffsetS)) ? Number(startedOffsetS) : 0;
    const endOffset = Number.isFinite(Number(endedOffsetS))
      ? Number(endedOffsetS)
      : (Number(ended) - Number(started)) / 1000;
    return {
      type: "activity_segment",
      label: String(label || ""),
      binary_label: binaryLabelOf(label),
      start_offset_s: Math.round(startOffset * 1000) / 1000,
      end_offset_s: Math.round(endOffset * 1000) / 1000,
      started_at_utc: new Date(started).toISOString(),
      ended_at_utc: new Date(ended).toISOString(),
      source: "recorder_session",
    };
  }

  /* ------------------------------------------------------------------ */
  /* frames.csv (unchanged 32-column contract, spec §4)                  */
  /* ------------------------------------------------------------------ */

  const FRAMES_HEADER = [
    "recording_id", "frame_sequence", "seq", "rx_seq", "mac", "dmac", "rssi",
    "noise_floor", "channel", "secondary_channel", "sig_mode", "mcs", "rate",
    "bandwidth", "stbc", "data_type", "raw_len", "valid_len", "lltf_len",
    "ht_ltf_len", "stbc_ht_ltf_len", "first_word_invalid", "agc_gain",
    "fft_gain", "rx_gain_compensation", "callback_timestamp_us",
    "rx_ctrl_timestamp_us", "host_receive_monotonic_ns", "dropped",
    "payload_ok", "raw_b64", "valid_b64",
  ].join(",");

  const FRAMES_COLUMNS = FRAMES_HEADER.split(",");

  const NA = "na";

  function numOrNa(value) {
    if (value === null || value === undefined || value === "") {
      return NA;
    }
    const n = Number(value);
    return Number.isFinite(n) ? String(n) : NA;
  }

  function boolOrNa(value) {
    if (value === true) return "true";
    if (value === false) return "false";
    return NA;
  }

  function bytesToBase64(bytes) {
    if (!bytes || !bytes.length) {
      return "";
    }
    if (typeof btoa === "function") {
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i] & 0xff);
      }
      return btoa(binary);
    }
    /* Node (tests, manual export tools) */
    return Buffer.from(bytes).toString("base64");
  }

  function base64ToBytes(text) {
    const b64 = String(text || "");
    if (!b64) {
      return new Uint8Array(0);
    }
    if (typeof atob === "function") {
      const binary = atob(b64);
      const out = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        out[i] = binary.charCodeAt(i);
      }
      return out;
    }
    return new Uint8Array(Buffer.from(b64, "base64"));
  }

  function buildFramesCsv(recordingId, frames) {
    const lines = [FRAMES_HEADER];
    for (let i = 0; i < frames.length; i++) {
      const frame = frames[i];
      const rawB64 = bytesToBase64(frame.rawBytes);
      const validB64 = bytesToBase64(frame.validBytes);
      const rawOk = frame.rawBytes && frame.rawBytes.length === Number(frame.raw_len);
      const validOk = !frame.validBytes || !frame.validBytes.length ||
        frame.validBytes.length === Number(frame.valid_len);
      lines.push([
        csvEscape(recordingId),
        i,
        numOrNa(frame.seq),
        numOrNa(frame.rx_seq),
        csvEscape(frame.mac || NA),
        csvEscape(frame.dmac || NA),
        numOrNa(frame.rssi),
        numOrNa(frame.noise_floor),
        numOrNa(frame.channel),
        numOrNa(frame.secondary_channel),
        numOrNa(frame.sig_mode),
        numOrNa(frame.mcs),
        numOrNa(frame.rate),
        numOrNa(frame.bandwidth),
        numOrNa(frame.stbc),
        numOrNa(frame.data_type),
        numOrNa(frame.raw_len),
        numOrNa(frame.valid_len),
        numOrNa(frame.lltf_len),
        numOrNa(frame.ht_ltf_len),
        numOrNa(frame.stbc_ht_ltf_len),
        boolOrNa(frame.first_word_invalid),
        numOrNa(frame.agc_gain),
        numOrNa(frame.fft_gain),
        numOrNa(frame.rx_gain_compensation),
        numOrNa(frame.ts_us),
        numOrNa(frame.local_timestamp),
        numOrNa(frame.host_receive_monotonic_ns),
        numOrNa(frame.dropped),
        boolOrNa(rawOk && validOk),
        rawB64,
        validB64,
      ].join(","));
    }
    return lines.join("\n") + "\n";
  }

  /*
   * Minimal CSV row splitter honouring double-quoted fields (frames.csv only
   * quotes mac/dmac/recording_id in practice, but be safe).
   */
  function splitCsvLine(line) {
    const out = [];
    let cur = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            cur += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          cur += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        out.push(cur);
        cur = "";
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out;
  }

  function naToNull(text) {
    return text === NA || text === "" ? null : text;
  }

  function naToNumber(text) {
    if (text === NA || text === "") {
      return null;
    }
    const n = Number(text);
    return Number.isFinite(n) ? n : null;
  }

  /*
   * Parse a stored frames.csv back into frame records with decoded payloads.
   * Used by the GUI visualisation (replacing iq.csv parsing) and by tests to
   * prove the file round-trips losslessly.
   */
  function parseFramesCsv(text) {
    const lines = String(text || "").split(/\r?\n/).filter((l) => l && !l.startsWith("#"));
    if (lines.length < 2) {
      return { frames: [], columns: [] };
    }
    const header = splitCsvLine(lines[0]);
    const idx = {};
    header.forEach((name, i) => { idx[name] = i; });
    const frames = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = splitCsvLine(lines[i]);
      const get = (name) => (idx[name] === undefined ? null : cols[idx[name]]);
      const rawBytes = base64ToBytes(get("raw_b64"));
      const validBytes = base64ToBytes(get("valid_b64"));
      frames.push({
        recording_id: get("recording_id"),
        frame_sequence: naToNumber(get("frame_sequence")),
        seq: naToNumber(get("seq")),
        rx_seq: naToNumber(get("rx_seq")),
        mac: naToNull(get("mac")),
        dmac: naToNull(get("dmac")),
        rssi: naToNumber(get("rssi")),
        noise_floor: naToNumber(get("noise_floor")),
        channel: naToNumber(get("channel")),
        secondary_channel: naToNumber(get("secondary_channel")),
        sig_mode: naToNumber(get("sig_mode")),
        mcs: naToNumber(get("mcs")),
        rate: naToNumber(get("rate")),
        bandwidth: naToNumber(get("bandwidth")),
        stbc: naToNumber(get("stbc")),
        data_type: naToNumber(get("data_type")),
        raw_len: naToNumber(get("raw_len")),
        valid_len: naToNumber(get("valid_len")),
        lltf_len: naToNumber(get("lltf_len")),
        ht_ltf_len: naToNumber(get("ht_ltf_len")),
        stbc_ht_ltf_len: naToNumber(get("stbc_ht_ltf_len")),
        first_word_invalid: get("first_word_invalid") === "true" ? true
          : get("first_word_invalid") === "false" ? false : null,
        agc_gain: naToNumber(get("agc_gain")),
        fft_gain: naToNumber(get("fft_gain")),
        rx_gain_compensation: naToNumber(get("rx_gain_compensation")),
        ts_us: naToNumber(get("callback_timestamp_us")),
        local_timestamp: naToNumber(get("rx_ctrl_timestamp_us")),
        host_receive_monotonic_ns: naToNumber(get("host_receive_monotonic_ns")),
        dropped: naToNumber(get("dropped")),
        payload_ok: get("payload_ok") === "true" ? true
          : get("payload_ok") === "false" ? false : null,
        rawBytes,
        validBytes,
      });
    }
    return { frames, columns: header };
  }

  /* ------------------------------------------------------------------ */
  /* Legacy identifiers and helpers still used by the GUI                 */
  /* ------------------------------------------------------------------ */

  const INDEX_HEADER =
    "id,activity_label,binary_label,started_at_utc,target_duration_s,actual_duration_s,frames,complete,status";

  function slugLabel(label) {
    const slug = String(label || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
    return slug.slice(0, 48);
  }

  function resolveLabel(preset, custom) {
    const presetText = String(preset || "").trim();
    if (presetText && isKnownActivity(presetText)) {
      return presetText;
    }
    const customText = String(custom || "").trim();
    if (customText) {
      return customText;
    }
    return "";
  }

  function isSafeRecordingId(id) {
    return typeof id === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$/.test(id);
  }

  function csvEscape(value) {
    const text = String(value ?? "");
    if (/[",\n\r]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  }

  /*
   * ESP-IDF v5.5.3 (api-guides/wifi.rst, Wi-Fi CSI): "Each item is stored as
   * two bytes: imaginary part followed by real part." decodePairs keeps the
   * legacy [byte0, byte1] order used by the v1 CSVs and the firmware
   * classifier, so callers must treat pair[0] as imaginary and pair[1] as
   * real. Legacy v1 iq.csv headers (scNNN_i first) are swapped with respect
   * to that documentation and are kept unchanged for backward compatibility.
   */
  function decodePairs(bytes, dataType) {
    const sampleBytes = Number(dataType) === 1 ? 2 : 1;
    const pairs = [];
    if (!bytes || bytes.length < sampleBytes * 2) {
      return pairs;
    }
    const view = bytes.buffer
      ? new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
      : new DataView(Uint8Array.from(bytes).buffer);
    for (let index = 0; index + sampleBytes * 2 <= bytes.length; index += sampleBytes * 2) {
      const real = sampleBytes === 2 ? view.getInt16(index, true) : view.getInt8(index);
      const imag = sampleBytes === 2 ? view.getInt16(index + sampleBytes, true) : view.getInt8(index + 1);
      pairs.push([real, imag]);
    }
    return pairs;
  }

  function decodePairsDocOrder(bytes, dataType) {
    return decodePairs(bytes, dataType).map((pair) => ({
      imag: pair[0],
      real: pair[1],
    }));
  }

  function framePayloadBytes(frame) {
    if (frame.validBytes && frame.validBytes.length) {
      return { bytes: frame.validBytes, source: "valid_data" };
    }
    return { bytes: frame.rawBytes || [], source: "raw_data" };
  }

  function recordingCompleteness({ frames, droppedStart, droppedEnd, disconnected, stimulusOn }) {
    const count = Array.isArray(frames) ? frames.length : Number(frames || 0);
    const droppedDelta = Math.max(0, Number(droppedEnd || 0) - Number(droppedStart || 0));
    const complete = count > 0 && !disconnected && droppedDelta === 0 && stimulusOn !== false;
    return { complete, frames: count, dropped_delta: droppedDelta };
  }

  /*
   * Batch settings: duration is FIXED at 10 s (spec §8) and no longer
   * user-configurable; takes/gap remain configurable.
   */
  function parseBatchSettings({ takes, gapS }) {
    const count = Number(takes);
    const gap = Number(gapS);
    if (
      !Number.isInteger(count) || count < 1 || count > 100 ||
      !Number.isInteger(gap) || gap < 0 || gap > 60
    ) {
      return null;
    }
    return { takes: count, durationS: TARGET_DURATION_S, gapS: gap };
  }

  function utcStamp(date) {
    const d = date instanceof Date ? date : new Date(date);
    return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  }

  function makeRecordingId(label, date, seq) {
    const slug = slugLabel(label) || "unlabeled";
    const nnn = String(seq || 1).padStart(3, "0");
    return `${utcStamp(date)}_${slug}_${nnn}`;
  }

  function makeMotionSample(message) {
    if (!message || message.type !== "sample") {
      return null;
    }
    const sample = {
      ts_ms: Number(message.ts_ms),
      peer: String(message.peer || ""),
      motion_status: message.motion_status,
      smooth_scaled: Number(message.smooth_scaled),
      enter_level_scaled: Number(message.enter_level_scaled),
      exit_level_scaled: Number(message.exit_level_scaled),
    };
    if (
      !Number.isFinite(sample.ts_ms) ||
      typeof sample.motion_status !== "boolean" ||
      !Number.isFinite(sample.smooth_scaled) ||
      !Number.isFinite(sample.enter_level_scaled) ||
      !Number.isFinite(sample.exit_level_scaled)
    ) {
      return null;
    }
    return sample;
  }

  function downsampleHeatmap(iqFrames, maxCols) {
    const limit = Math.max(1, maxCols || 400);
    if (!iqFrames.length) {
      return [];
    }
    const step = Math.max(1, Math.ceil(iqFrames.length / limit));
    const out = [];
    for (let i = 0; i < iqFrames.length; i += step) {
      const frame = iqFrames[i];
      out.push((frame.iq || []).map((pair) => Math.hypot(pair[0] || 0, pair[1] || 0)));
    }
    return out;
  }

  /* ------------------------------------------------------------------ */
  /* LEGACY derived-file builders — MANUAL EXPORT ONLY (spec §5).        */
  /* The recorder never calls these automatically and never writes the   */
  /* results into a take directory. Kept so old datasets stay readable   */
  /* and for ad-hoc conversion/debug exports.                            */
  /* ------------------------------------------------------------------ */

  const CSI_DATA_HEADER =
    "type,sequence,timestamp,taget_seq,target,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,agc_gain,fft_gain,len,first_word,data";

  const RAW_IQ_HEADER = [
    "frame_sequence", "seq", "source", "data_type", "subcarriers", "iq",
  ].join(",");

  const PRESET_LABELS = ["kosong", "duduk", "berdiri", "jongkok", "jatuh", "berjalan"];

  function buildRawIqCsv(frames) {
    const lines = [RAW_IQ_HEADER];
    for (let i = 0; i < frames.length; i++) {
      const frame = frames[i];
      const payloads = [
        ["raw_data", frame.rawBytes],
        ["valid_data", frame.validBytes],
      ];
      for (const [source, bytes] of payloads) {
        if (!bytes || !bytes.length) {
          continue;
        }
        const pairs = decodePairsDocOrder(bytes, frame.data_type);
        lines.push([
          i,
          numOrNa(frame.seq),
          source,
          numOrNa(frame.data_type),
          pairs.length,
          csvEscape(pairs.map((p) => `${p.imag}|${p.real}`).join(";")),
        ].join(","));
      }
    }
    return lines.join("\n") + "\n";
  }

  function buildEvents({ recordingId, label, started, ended, motionSamples, motionPeer }) {
    const segments = [{
      type: "activity_segment",
      label: String(label || ""),
      start_offset_s: 0,
      end_offset_s: (Number(ended) - Number(started)) / 1000,
      started_at_utc: new Date(started).toISOString(),
      ended_at_utc: new Date(ended).toISOString(),
      source: "recorder_session",
    }];
    return {
      schema_version: 2,
      recording_id: recordingId,
      segments,
      motion_peer: motionPeer || "",
      motion_samples: Array.isArray(motionSamples) ? motionSamples : [],
    };
  }

  function bytesToCsvList(bytes) {
    if (!bytes || !bytes.length) {
      return "\"[]\"";
    }
    let inner = String(bytes[0]);
    for (let i = 1; i < bytes.length; i++) {
      inner += `,${bytes[i]}`;
    }
    return `"${inner}"`;
  }

  function iqHeader(subcarriers) {
    const cols = ["timestamp_us", "seq", "mac", "rssi", "data_type", "dropped"];
    for (let i = 0; i < subcarriers; i++) {
      const n = String(i).padStart(3, "0");
      cols.push(`sc${n}_i`, `sc${n}_q`);
    }
    return cols.join(",");
  }

  function buildCsiDataCsv(frames, options) {
    const label = (options && options.label) || "unknown";
    const takeSeq = (options && options.takeSeq) || 1;
    const lines = [CSI_DATA_HEADER];
    for (const frame of frames) {
      const payload = framePayloadBytes(frame);
      lines.push([
        "CSI_DATA",
        Number(frame.seq || 0),
        Number(frame.ts_us || frame.local_timestamp || 0),
        takeSeq,
        csvEscape(label),
        frame.mac || "",
        Number(frame.rssi || 0),
        Number(frame.rate || 0),
        Number(frame.sig_mode || 0),
        Number(frame.mcs || 0),
        Number(frame.bandwidth || 0),
        0,
        0,
        0,
        Number(frame.stbc || 0),
        0,
        0,
        Number(frame.noise_floor || 0),
        0,
        Number(frame.channel || 0),
        Number(frame.secondary_channel || 0),
        Number(frame.local_timestamp || 0),
        0,
        0,
        0,
        Number(frame.agc_gain || 0),
        Number(frame.fft_gain || 0),
        payload.bytes.length,
        0,
        bytesToCsvList(payload.bytes),
      ].join(","));
    }
    return lines.join("\n") + "\n";
  }

  function buildIqCsv(frames) {
    let subcarriers = 0;
    const decoded = frames.map((frame) => {
      const payload = framePayloadBytes(frame);
      const pairs = frame.iq && frame.iq.length
        ? frame.iq
        : decodePairs(payload.bytes, frame.data_type);
      if (pairs.length > subcarriers) {
        subcarriers = pairs.length;
      }
      return { frame, pairs };
    });
    const lines = [iqHeader(subcarriers)];
    for (const row of decoded) {
      const cols = [
        Number(row.frame.ts_us || 0),
        Number(row.frame.seq || 0),
        row.frame.mac || "",
        Number(row.frame.rssi || 0),
        Number(row.frame.data_type || 0),
        Number(row.frame.dropped || 0),
      ];
      for (let i = 0; i < subcarriers; i++) {
        const pair = row.pairs[i] || [0, 0];
        cols.push(pair[0], pair[1]);
      }
      lines.push(cols.join(","));
    }
    return lines.join("\n") + "\n";
  }

  function parseIqCsv(text) {
    const lines = String(text || "").split(/\r?\n/).filter((line) => line && !line.startsWith("#"));
    if (lines.length < 2) {
      return { frames: [], subcarriers: 0 };
    }
    const header = lines[0].split(",");
    const firstIq = header.findIndex((name) => name.startsWith("sc") && name.endsWith("_i"));
    const subcarriers = firstIq >= 0 ? Math.floor((header.length - firstIq) / 2) : 0;
    const frames = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const iq = [];
      for (let sc = 0; sc < subcarriers; sc++) {
        const base = firstIq + sc * 2;
        iq.push([Number(cols[base]), Number(cols[base + 1])]);
      }
      frames.push({
        ts_us: Number(cols[0]),
        seq: Number(cols[1]),
        mac: cols[2],
        rssi: Number(cols[3]),
        iq,
      });
    }
    return { frames, subcarriers };
  }

  function buildMeta(fields) {
    return Object.assign({
      format: "wifi_sensing_demo_csi_v1",
      data_source: "valid_data_preferred_else_raw_data",
    }, fields);
  }

  function buildMetaV2(fields) {
    return Object.assign(buildMeta(fields), {
      schema_version: 2,
      recording_id: fields.id,
      session_id: fields.batch_id || fields.id,
      trial_id: fields.id,
      subject_id: fields.subject_id || null,
      recording_started_at_utc: fields.started_at_utc,
      recording_ended_at_utc: fields.ended_at_utc,
      firmware_target: fields.firmware_target || null,
      acquisition: Object.assign({
        csi_period_ms: null,
        csi_period_note: "csi_period_ms is the firmware CSI-stream throttle reported in the hello message; 0 means unthrottled (emit on every CSI callback), >0 throttles emission to that many ms",
      }, fields.acquisition || {}),
      files: Object.assign({
        frames_csv: `${fields.id}.frames.csv`,
        raw_iq_csv: `${fields.id}.raw_iq.csv`,
        events_json: `${fields.id}.events.json`,
      }, fields.files || {}),
      payload_semantics: {
        raw: "unfiltered driver CSI buffer (wifi_csi_info_t.buf, includes invalid subcarriers)",
        valid: "esp-radar component-filtered payload, layout LLTF | HT-LTF | STBC-HT-LTF",
        iq_byte_order: "imaginary first, then real (ESP-IDF v5.5.3 api-guides/wifi.rst)",
        raw_iq_rows: "raw_iq.csv emits one row per available payload per frame (source=raw_data and/or valid_data); subcarriers is that payload's actual pair count, no zero padding",
        first_word_invalid: "when true the first four bytes of the driver CSI buffer (wifi_csi_info_t.buf, stored as raw_data) are invalid per ESP-IDF v5.5.3 api-guides/wifi.rst: 2 complex pairs for int8 (data_type 0), 1 pair for int16 (data_type 1). valid_data is esp-radar's compacted concatenation of buffer sub-ranges, so its leading pairs are NOT necessarily those bytes - do not trim compacted payloads until the per-layout mapping is verified",
        legacy_iq_csv: "v1 iq.csv scNNN_i/scNNN_q columns are swapped relative to iq_byte_order; kept unchanged for backward compatibility",
      },
      pipeline_versions: {
        recorder: "csi_recorder.js v2",
        baseline_classifier: "52 LLTF complex pairs, 16 log-amplitude-change bands, window 24 frames, stride 12 frames",
      },
    });
  }

  /* ------------------------------------------------------------------ *
   * Ping/CSI diagnostic session (Prioritas 1, plan §18).
   *
   * Host-side model of the device diagnostic stream. All state is driven by
   * serial messages (device is single-source-of-truth), so this is testable in
   * Node without hardware. It implements:
   *   - epoch + boot_id gating and the device timestamp window (§18.10),
   *   - wrap-safe diag_seq gap / out-of-order accounting (§18.13),
   *   - consumer-ack finalisation bound to (epoch, flush_generation) so a
   *     stale STOP ACK from a previous cycle can never close the barrier (§2),
   *   - the per-take soft-cap that stops appending rows once MAX_EVENTS_PER_TAKE
   *     is reached, recording the drop instead of silently losing it (§18.5),
   *   - the columns+delta+enum encoding written to meta.events (§18.1).
   * ------------------------------------------------------------------ */

  /* Ping event type enum (numeric on the wire, per §18.1). */
  const PING_TYPE_ENUM = { success: 1, timeout: 2 };
  /* csi_diag drop_reason enum (post-implementation review §2). 0 keeps the
   * original §18.3 meaning (throttle-dropped callback); 1..4 mark minimal
   * metadata fallbacks for direct-write frame failures. Matches the
   * DIAG_CSI_DROP_* defines in main/web_serial_monitor.c. */
  const CSI_DROP_ENUM = {
    throttle: 0,
    tx_lock_timeout: 1,
    oversized: 2,
    base64_fail: 3,
    uart_write_fail: 4,
  };
  /* Per-take row soft cap (§18.5): ~10 MB columns+delta worst case. */
  const MAX_EVENTS_PER_TAKE = 200000;

  /* Wrap-safe "a is strictly newer than b" for uint32 counters. */
  function seqNewer(a, b) {
    const au = a >>> 0;
    const bu = b >>> 0;
    return au !== bu && ((au - bu) >>> 0) < 0x80000000;
  }

  function asUint32(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n >>> 0 : null;
  }

  function asInt(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  /*
   * createDiagSession({ epoch, runId, bootId, maxEvents }) -> session.
   * epoch: uint32 chosen by the browser for this take.
   */
  function createDiagSession(opts) {
    opts = opts || {};
    const epoch = asUint32(opts.epoch);
    const maxEvents = Number.isFinite(Number(opts.maxEvents)) && Number(opts.maxEvents) > 0
      ? Number(opts.maxEvents)
      : MAX_EVENTS_PER_TAKE;
    return {
      epoch,
      runId: opts.runId || null,
      bootId: opts.bootId === undefined || opts.bootId === null ? null : asUint32(opts.bootId),
      maxEvents,
      phase: "starting",
      /* device-provided anchors (filled from ACKs). */
      gen: null,
      startTsUs: null,
      endTsUs: null,
      /* raw accepted events in arrival order; ts kept absolute until finalize. */
      ping: [],
      csi: [],
      /* device STOP-ACK snapshot for finalize (null until confirmed/failed ack). */
      device: null,
      boundaryConfirmed: false,
      /* Final-audit §2: device-reported diagnostics state (undefined = older
       * firmware, treated as enabled). */
      diagEnabled: true,
      diagReason: null,
      dsMax: null,
      counters: {
        browser_parse_error: 0,
        boundary_ts_rejected: 0,
        epoch_rejected: 0,
        boot_id_mismatch: 0,
        duplicate_ds: 0,
        out_of_order: 0,
        seq_gaps: 0,
        event_overflow: 0,
        stale_ack: 0,
      },
      truncated: false,
    };
  }

  /* Applies a TAKE_BEGIN START ACK. Returns true when accepted. */
  function diagNoteStartAck(session, ack) {
    if (!session || !ack || ack.cmd !== "TAKE_BEGIN" || !ack.ok) {
      return false;
    }
    if (asUint32(ack.epoch) !== session.epoch) {
      session.counters.epoch_rejected += 1;
      return false;
    }
    session.gen = asUint32(ack.gen);
    if (ack.boot_id !== undefined && ack.boot_id !== null) {
      session.bootId = asUint32(ack.boot_id);
    }
    /* Final-audit §2: explicit degraded-diagnostics reporting. The take still
     * proceeds (CSI recording works); only the diagnostic streams go null. */
    if (ack.diagnostics_enabled !== undefined) {
      session.diagEnabled = ack.diagnostics_enabled === true;
    }
    if (ack.reason) {
      session.diagReason = String(ack.reason);
    }
    const ts = asInt(ack.start_ts_us);
    if (ts !== null) {
      session.startTsUs = ts;
    }
    if (session.phase === "starting") {
      session.phase = "recording";
    }
    return true;
  }

  /* Marks STOP requested; events keep flowing until the STOP ACK arrives. */
  function diagNoteStopping(session) {
    if (session && session.phase === "recording") {
      session.phase = "stopping";
    }
  }

  /*
   * Applies a TAKE_END STOP ACK. The consumer-ack is accepted ONLY when it
   * matches BOTH the active epoch AND the flush_generation captured at start
   * (§2). A stale ACK (previous cycle's epoch, or a mismatched generation, or a
   * re-delivery after finalisation) is counted as stale_ack and never closes the
   * barrier.
   */
  function diagNoteStopAck(session, ack) {
    if (!session) {
      return { accepted: false, reason: "no_session" };
    }
    if (session.phase === "finalized") {
      session.counters.stale_ack += 1;
      return { accepted: false, reason: "already_finalized" };
    }
    if (!ack || ack.cmd !== "TAKE_END") {
      session.counters.browser_parse_error += 1;
      return { accepted: false, reason: "bad_ack" };
    }
    if (asUint32(ack.epoch) !== session.epoch || asUint32(ack.gen) !== session.gen) {
      session.counters.stale_ack += 1;
      return { accepted: false, reason: "stale" };
    }
    session.endTsUs = asInt(ack.end_ts_us);
    session.device = ack;
    if (ack.diagnostics_enabled !== undefined) {
      session.diagEnabled = ack.diagnostics_enabled === true;
    }
    /* Final-audit §3: confirmation requires each device-side stage to be
     * TRUE (an absent/undefined flag never confirms), plus a parsed-complete
     * ACK — the browser only ever receives this object when the whole JSON
     * line arrived intact, so a short-written ACK cannot reach here as
     * confirmed. The device never claims browser receipt; this is only the
     * device-side boundary. */
    session.boundaryConfirmed = ack.ok === true
      && ack.barrier_ok === true
      && ack.tx_drained === true;
    session.phase = "finalized";
    return { accepted: true, reason: session.boundaryConfirmed ? "confirmed" : "unconfirmed" };
  }

  function diagUpdateDs(session, ds) {
    if (session.dsMax === null) {
      session.dsMax = ds;
      return;
    }
    if (ds === session.dsMax) {
      session.counters.duplicate_ds += 1;
      return;
    }
    if (seqNewer(ds, session.dsMax)) {
      const missing = ((ds - session.dsMax) >>> 0) - 1;
      if (missing > 0 && missing < 0x80000000) {
        session.counters.seq_gaps += missing;
      }
      session.dsMax = ds;
    } else {
      session.counters.out_of_order += 1;
    }
  }

  /*
   * Classifies and stores one incoming `type==="diag"` serial message.
   * Returns a reason string for tests. Never throws.
   */
  function diagAcceptEvent(session, msg) {
    if (!session || session.phase === "finalized") {
      return "closed";
    }
    if (!msg || msg.type !== "diag" || !msg.et) {
      session.counters.browser_parse_error += 1;
      return "parse_error";
    }
    if (asUint32(msg.e) !== session.epoch) {
      session.counters.epoch_rejected += 1;
      return "epoch_rejected";
    }
    if (session.bootId !== null && msg.bid !== undefined && msg.bid !== null
        && asUint32(msg.bid) !== session.bootId) {
      session.counters.boot_id_mismatch += 1;
      return "boot_mismatch";
    }
    const ts = asInt(msg.ts);
    const ds = asUint32(msg.ds);
    if (ts === null || ds === null) {
      session.counters.browser_parse_error += 1;
      return "parse_error";
    }
    if (session.ping.length + session.csi.length >= session.maxEvents) {
      session.truncated = true;
      session.counters.event_overflow += 1;
      return "capped";
    }
    if (msg.et === "ping") {
      session.ping.push({
        ds,
        ts,
        success: msg.st === true,
        seqno: asInt(msg.sn),
        seqno_valid: msg.sv === true,
        timegap_ms: asInt(msg.tg),
        ttl: asInt(msg.ttl),
        recv_size: asInt(msg.sz),
        transmitted: asInt(msg.tx),
        received: asInt(msg.rx),
      });
    } else if (msg.et === "csi") {
      session.csi.push({
        ds,
        ts,
        cb: asInt(msg.cb),
        mac: msg.mac || "",
        dmac: msg.dm || "",
        rx_seq: asInt(msg.rq),
        sig_mode: asInt(msg.sm),
        mcs: asInt(msg.mc),
        rssi: asInt(msg.rs),
        bandwidth: asInt(msg.bw),
        stbc: asInt(msg.sb),
        payload_len: asInt(msg.pl),
        /* Post-implementation review §2: firmware seq_id of the failed direct
         * write (fallback rows only) and the drop reason. Missing `dr` on
         * older firmware means the throttle case (0). */
        seq_id: asInt(msg.sid),
        drop_reason: asInt(msg.dr) === null ? CSI_DROP_ENUM.throttle : asInt(msg.dr),
      });
    } else {
      session.counters.browser_parse_error += 1;
      return "parse_error";
    }
    diagUpdateDs(session, ds);
    return "accepted";
  }

  /* Applies the device ts window; returns {rows, rejected}. */
  function windowFilter(session, rows) {
    const lo = session.startTsUs;
    const hi = session.boundaryConfirmed ? session.endTsUs : null;
    let rejected = 0;
    const kept = rows.filter((r) => {
      if (lo !== null && r.ts < lo) {
        rejected += 1;
        return false;
      }
      if (hi !== null && r.ts > hi) {
        rejected += 1;
        return false;
      }
      return true;
    });
    return { rows: kept, rejected };
  }

  /* Encodes a row list into the columns+delta+enum shape (§18.1). Rows are
   * sorted by absolute device ts; ts_base_us is the FIRST event's own esp_timer
   * value so base + Σ ts_delta_us reconstructs every event exactly. */
  function encodeStream(rows, columns, mapper) {
    if (rows.length === 0) {
      return { columns, rows: [], ts_base_us: null, ts_unit: "us", ts_monotonic: "esp_timer" };
    }
    const ordered = rows.slice().sort((a, b) => a.ts - b.ts);
    const tsBase = ordered[0].ts;
    const out = [];
    let prev = ordered[0].ts;
    for (const r of ordered) {
      const delta = r.ts - prev;
      out.push(mapper(r, delta));
      prev = r.ts;
    }
    return {
      columns,
      rows: out,
      ts_base_us: tsBase,
      ts_unit: "us",
      ts_monotonic: "esp_timer",
    };
  }

  /* Specific reason a boundary is NOT confirmed (final audit §3). Derived only
   * from device-reported flags — never inferred from "the UART looked idle",
   * and never claiming the browser received everything. */
  function boundaryFailureReason(session) {
    if (session.boundaryConfirmed) {
      return null;
    }
    const ack = session.device;
    if (!ack) {
      return session.phase === "stopping" ? "stop_ack_timeout" : "stop_ack_not_received";
    }
    if (ack.tx_drained === undefined) {
      /* ACK predates the per-stage drain flags: confirmation cannot be graded,
       * so the unconfirmed case stays attributed to the missing evidence. */
      return "stop_ack_missing_drain_flags";
    }
    if (ack.tx_drained === false) {
      return "serial_tx_not_drained(fflush_ok=" + String(ack.fflush_ok)
        + ",fsync_ok=" + String(ack.fsync_ok) + ")";
    }
    if (ack.barrier_ok === false) {
      return "mpsc_barrier_incomplete(queue_pending=" + (Number(ack.queue_pending) || 0)
        + ",drain_inflight=" + (Number(ack.drain_inflight) || 0)
        + ",inflight_at_close=" + (Number(ack.inflight_at_close) || 0) + ")";
    }
    return "device_reported_failure";
  }

  /* Produces {ping, csi_diag, session_stats, boundary} for meta. */
  function diagFinalize(session) {
    /* Final-audit §2: degraded device (diagnostics plumbing failed at init).
     * Event streams and device-derived metrics are UNAVAILABLE (null), never
     * zero — zero would silently claim "no ping events happened". Host-side
     * counters still describe what the browser observed (nothing). */
    if (session.diagEnabled === false) {
      const reason = session.diagReason || "unknown";
      return {
        ping: null,
        csi_diag: null,
        session_stats: {
          diagnostics_unavailable: true,
          diagnostics_unavailable_reason: reason,
          configured_interval_ms: null,
          request_accepted_by_stack: null,
          echo_reply_received: null,
          success_callback_count: null,
          timeout_callback_count: null,
          event_overflow_count: session.counters.event_overflow,
          diag_queue_overflow_count: null,
          csi_callback_count: null,
          csi_event_persisted_count: null,
          ping_event_persisted_count: null,
          diag_tx_failure_count: null,
          diagnostic_event_loss_count: null,
          loss_accounting: null,
          truncated: session.truncated,
          host_counters: {
            browser_parse_error: session.counters.browser_parse_error,
            boundary_ts_rejected: session.counters.boundary_ts_rejected,
            epoch_rejected: session.counters.epoch_rejected,
            boot_id_mismatch: session.counters.boot_id_mismatch,
            duplicate_ds: session.counters.duplicate_ds,
            out_of_order: session.counters.out_of_order,
            seq_gaps: session.counters.seq_gaps,
            stale_ack: session.counters.stale_ack,
          },
        },
        boundary: {
          epoch: session.epoch,
          boot_id: session.bootId,
          flush_generation: session.gen,
          confirmed: session.boundaryConfirmed,
          status: session.boundaryConfirmed ? "confirmed" : "boundary_unconfirmed",
          unconfirmed_reason: boundaryFailureReason(session),
          diagnostics_enabled: false,
          diagnostics_unavailable_reason: reason,
          start_ts_us: session.startTsUs,
          end_ts_us: session.endTsUs,
          diag_seq_max: null,
          device_high_waters: null,
          queue_pending: null,
          inflight_at_close: null,
          barrier_ok: false,
          tx_drained: false,
        },
      };
    }

    const pingWin = windowFilter(session, session.ping);
    const csiWin = windowFilter(session, session.csi);
    session.counters.boundary_ts_rejected += pingWin.rejected + csiWin.rejected;

    const pingColumns = [
      "type", "ds", "ts_delta_us", "seqno", "seqno_valid",
      "timegap_ms", "ttl", "recv_size", "transmitted", "received",
    ];
    const csiColumns = [
      "cb", "ds", "ts_delta_us", "mac", "dmac", "rx_seq", "sig_mode",
      "mcs", "rssi", "bandwidth", "stbc", "payload_len", "firmware_seq",
      "drop_reason",
    ];

    const pingEnc = encodeStream(pingWin.rows, pingColumns, (r, delta) => [
      r.success ? PING_TYPE_ENUM.success : PING_TYPE_ENUM.timeout,
      r.ds,
      delta,
      r.seqno,
      r.seqno_valid ? 1 : 0,
      /* A timeout has no reply, so reply-derived fields are null, not 0. */
      r.success ? r.timegap_ms : null,
      r.success ? r.ttl : null,
      r.success ? r.recv_size : null,
      r.transmitted,
      r.received,
    ]);
    pingEnc.type_enum = { success: PING_TYPE_ENUM.success, timeout: PING_TYPE_ENUM.timeout };

    const csiEnc = encodeStream(csiWin.rows, csiColumns, (r, delta) => [
      r.cb, r.ds, delta, r.mac, r.dmac, r.rx_seq, r.sig_mode, r.mcs,
      r.rssi, r.bandwidth, r.stbc, r.payload_len,
      /* fallback-only fields; null on throttle rows (no direct write ever ran
       * for a callback that was throttled before formatting). */
      r.seq_id, r.drop_reason,
    ]);
    csiEnc.mac_format = "12-hex lowercase, no colons";
    csiEnc.drop_reason_enum = {
      throttle: CSI_DROP_ENUM.throttle,
      tx_lock_timeout: CSI_DROP_ENUM.tx_lock_timeout,
      oversized: CSI_DROP_ENUM.oversized,
      base64_fail: CSI_DROP_ENUM.base64_fail,
      uart_write_fail: CSI_DROP_ENUM.uart_write_fail,
    };

    const successCallbackCount = pingWin.rows.filter((r) => r.success).length;
    const timeoutCallbackCount = pingWin.rows.filter((r) => !r.success).length;

    const dev = session.device || {};
    const devCounters = dev.counters || {};
    /* Final-audit §1: STAGED reconciliation, one identity per stage, each event
     * landing in exactly ONE term:
     *   stage 1  assigned            = enqueued + queue_overflow (+residual)
     *   stage 2  enqueued            = tx_success + tx_failure + pending_at_close
     *   stage 3  tx_success          = browser_received_unique + unaccounted transport
     *   stage 4  browser_received    = persisted + window_rejected + truncated
     * Device per-take counters: enqueued = ping_event_persisted +
     * csi_event_persisted (incremented ONLY on xQueueSend success, so an
     * overflowed event is never also "enqueued"); tx_failure =
     * diag_emit_failed; pending_at_close = queue_pending.
     * Nothing is summed twice: the browser-side window/truncation terms live
     * on stage 4 only, and the total loss adds stage-1/2/3 losses once. */
    const assignedHw = Number(dev.diag_seq_assigned_max) || 0;
    const enqueuedTotal = (Number(devCounters.ping_event_persisted) || 0)
      + (Number(devCounters.csi_event_persisted) || 0);
    const queueOverflow = Number(devCounters.diag_queue_overflow) || 0;
    const txFailed = Number(devCounters.diag_emit_failed) || 0;
    const pendingAtClose = session.device ? (Number(dev.queue_pending) || 0) : null;
    const txSuccess = session.device
      ? Math.max(0, enqueuedTotal - txFailed - pendingAtClose)
      : null;
    const receivedDs = new Set();
    for (const r of session.ping) receivedDs.add(r.ds);
    for (const r of session.csi) receivedDs.add(r.ds);
    /* Stage 4's identity is exact against STORED arrivals: every stored event
     * is either persisted (in window), window-rejected, or capped before
     * storage. The unique-ds view sits next to it as the dedup signal — a
     * unique count below the received count means the same diag_seq arrived
     * more than once, which is a delivery anomaly, not a loss. */
    const browserReceivedCount = session.ping.length + session.csi.length;
    const browserReceivedUnique = receivedDs.size;
    const browserPersisted = pingWin.rows.length + csiWin.rows.length;
    const browserWindowRejected = session.counters.boundary_ts_rejected;
    const browserTruncated = session.counters.event_overflow;

    let lossAccounting = null;
    let diagnosticEventLoss = null;
    if (session.device) {
      /* Raw residuals: positive = an identified stage did not explain them
       * (reported as `unaccounted_*`); negative = the counters disagree (the
       * identity is over-determined, e.g. items drained after the snapshot),
       * which is flagged instead of silently inflating a loss term. */
      const stage1Residual = assignedHw - enqueuedTotal - queueOverflow;
      const stage2Residual = enqueuedTotal - txFailed - pendingAtClose - txSuccess;
      const unaccountedTransportRaw = txSuccess - browserReceivedCount;
      const unaccountedTransport = Math.max(0, unaccountedTransportRaw);
      lossAccounting = {
        counter_inconsistent: stage1Residual < 0 || stage2Residual < 0
          || unaccountedTransportRaw < 0,
        stages: {
          /* device side, stages 1-3 */
          diag_assigned_count: assignedHw,
          diag_queue_enqueued_count: enqueuedTotal,
          diag_queue_overflow_count: queueOverflow,
          diag_tx_success_count: txSuccess,
          diag_tx_failure_count: txFailed,
          diag_pending_at_close_count: pendingAtClose,
          diag_unaccounted_stage1_count: Math.max(0, stage1Residual),
          /* stage 3: written to the wire but never arrived intact (framing
           * loss, host stall); the device cannot see its own cause. */
          transport_unaccounted_count: unaccountedTransport,
          /* browser side, stage 4 */
          browser_received_count: browserReceivedCount,
          browser_received_unique_count: browserReceivedUnique,
          browser_parse_error_count: session.counters.browser_parse_error,
          browser_admission_rejected_count: session.counters.epoch_rejected
            + session.counters.boot_id_mismatch,
          browser_window_rejected_count: browserWindowRejected,
          browser_event_truncated_count: browserTruncated,
          browser_persisted_count: browserPersisted,
        },
      };
      /* Total over DISJOINT stages: stage-1 overflow + stage-2 TX failures +
       * stage-2 items still queued at close + stage-3 unaccounted transport +
       * stage-4 browser truncation. Window-rejected events are NOT a loss:
       * they arrived and are reported on their own counter. */
      diagnosticEventLoss = queueOverflow + txFailed + pendingAtClose
        + unaccountedTransport + browserTruncated;
    }

    const sessionStats = {
      diagnostics_unavailable: false,
      diagnostics_unavailable_reason: null,
      configured_interval_ms: null,
      request_accepted_by_stack: null,
      echo_reply_received: null,
      success_callback_count: successCallbackCount,
      timeout_callback_count: timeoutCallbackCount,
      event_overflow_count: session.counters.event_overflow,
      diag_queue_overflow_count: Number(devCounters.diag_queue_overflow) || 0,
      csi_callback_count: Number(devCounters.csi_callback) || 0,
      csi_event_persisted_count: Number(devCounters.csi_event_persisted) || 0,
      ping_event_persisted_count: Number(devCounters.ping_event_persisted) || 0,
      diag_tx_failure_count: txFailed,
      diagnostic_event_loss_count: diagnosticEventLoss,
      loss_accounting: lossAccounting,
      truncated: session.truncated,
      host_counters: {
        browser_parse_error: session.counters.browser_parse_error,
        boundary_ts_rejected: session.counters.boundary_ts_rejected,
        epoch_rejected: session.counters.epoch_rejected,
        boot_id_mismatch: session.counters.boot_id_mismatch,
        duplicate_ds: session.counters.duplicate_ds,
        out_of_order: session.counters.out_of_order,
        seq_gaps: session.counters.seq_gaps,
        stale_ack: session.counters.stale_ack,
      },
    };

    const boundary = {
      epoch: session.epoch,
      boot_id: session.bootId,
      flush_generation: session.gen,
      confirmed: session.boundaryConfirmed,
      status: session.boundaryConfirmed ? "confirmed" : "boundary_unconfirmed",
      unconfirmed_reason: boundaryFailureReason(session),
      diagnostics_enabled: session.diagEnabled !== false,
      start_ts_us: session.startTsUs,
      end_ts_us: session.endTsUs,
      diag_seq_max: session.dsMax,
      loss_accounting: lossAccounting,
      device_high_waters: session.device ? {
        assigned: Number(dev.diag_seq_assigned_max) || 0,
        enqueued: Number(dev.diag_seq_enqueued_max) || 0,
        emitted: Number(dev.diag_seq_emitted_max) || 0,
      } : null,
      queue_pending: session.device ? Number(dev.queue_pending) || 0 : null,
      inflight_at_close: session.device ? Number(dev.inflight_at_close) || 0 : null,
      barrier_ok: session.device ? dev.barrier_ok === true : false,
      tx_drained: session.device ? dev.tx_drained === true : false,
    };

    return { ping: pingEnc, csi_diag: csiEnc, session_stats: sessionStats, boundary };
  }

  /*
   * Pure mirror of the firmware TAKE_BEGIN lifecycle gate (post-implementation
   * review §1): TAKE_BEGIN may only open a new epoch once the previous session
   * is closed AND quiescent — no pending queue items, no producer inflight, no
   * drain inflight. Used by the host tests to pin the contract the device
   * enforces (device-side state polling lives in web_serial_monitor.c).
   */
  function diagTakeBeginAllowed(state) {
    const s = state || {};
    if (s.takeOpen) {
      return { allowed: false, reason: "take_open" };
    }
    if ((Number(s.queuePending) || 0) > 0
        || (Number(s.inflight) || 0) > 0
        || (Number(s.drainInflight) || 0) > 0) {
      return { allowed: false, reason: "prev_not_quiescent" };
    }
    return { allowed: true, reason: "quiescent" };
  }

  return {
    /* v3 activity system */
    ACTIVITY_LABELS,
    BINARY_LABELS,
    FALL_DIRECTIONS,
    PRE_ACTIONS,
    POST_ACTIONS,
    TIMELINE_DEFS,
    TONE_PATTERNS,
    TARGET_DURATION_S,
    binaryLabelOf,
    isFallLabel,
    isKnownActivity,
    buildActivityOptions,
    buildActivityTimeline,
    buildActivityCues,
    phaseAtOffset,
    makeAnnotator,
    computeIntervalStats,
    buildMetaV3,
    buildActivitySegment,
    PAYLOAD_SEMANTICS,
    /* frames.csv */
    FRAMES_HEADER,
    FRAMES_COLUMNS,
    SCHEMA_VERSION,
    INDEX_HEADER,
    buildFramesCsv,
    parseFramesCsv,
    splitCsvLine,
    base64ToBytes,
    bytesToBase64,
    /* shared helpers */
    slugLabel,
    resolveLabel,
    isSafeRecordingId,
    csvEscape,
    decodePairs,
    decodePairsDocOrder,
    framePayloadBytes,
    recordingCompleteness,
    parseBatchSettings,
    utcStamp,
    makeRecordingId,
    makeMotionSample,
    downsampleHeatmap,
    /* legacy (manual export / old-dataset readers only) */
    PRESET_LABELS,
    CSI_DATA_HEADER,
    RAW_IQ_HEADER,
    buildCsiDataCsv,
    buildIqCsv,
    buildRawIqCsv,
    buildEvents,
    parseIqCsv,
    buildMeta,
    buildMetaV2,
    /* Prioritas 1 diagnostic session (plan §18) */
    PING_TYPE_ENUM,
    CSI_DROP_ENUM,
    MAX_EVENTS_PER_TAKE,
    seqNewer,
    createDiagSession,
    diagNoteStartAck,
    diagNoteStopping,
    diagNoteStopAck,
    diagAcceptEvent,
    diagFinalize,
    diagTakeBeginAllowed,
  };
});
