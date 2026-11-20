/*
 * Diagnostic archive export/validation for the Web Serial recorder.
 *
 * The page already assembles the device's bounded diagnostic stream in memory
 * (checkpoint, DIAGNOSTIC_RECORDS chunks, CAPTURE_MANIFEST). This module turns
 * that report into one self-contained JSON document and re-validates it from
 * the raw transport bytes, so a file can be checked again after the page is
 * reopened without trusting the live page state.
 *
 * It is intentionally dependency-free and works in both the browser (global
 * `DiagnosticArchive`) and Node (CommonJS) so the unit tests exercise the same
 * code that ships in the page.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.DiagnosticArchive = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ARCHIVE_SCHEMA = "esp-wifi-sensing.diagnostic-archive";
  const ARCHIVE_SCHEMA_VERSION = 1;
  const WIRE_MAGIC = 0x33574d48;
  const WIRE_VERSION = 1;
  const WIRE_RECORD = 1;
  const WIRE_CHECKPOINT = 2;
  const MAX_PAYLOAD_BYTES = 1536;
  const RECORD_PAYLOAD_BYTES = 204;
  const CHECKPOINT_FIXED_BYTES = 36;
  const CHECKPOINT_CHANNEL_BYTES = 353;
  const CHECKPOINT_PENDING_BYTES = 74;

  function asBytes(value) {
    if (value instanceof Uint8Array) {
      return value;
    }
    if (typeof ArrayBuffer !== "undefined" && value instanceof ArrayBuffer) {
      return new Uint8Array(value);
    }
    if (typeof ArrayBuffer !== "undefined" && ArrayBuffer.isView(value)) {
      return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }
    return new Uint8Array(value);
  }

  function bytesFromBase64(text) {
    if (typeof text !== "string" || text.length % 4 !== 0 ||
        !/^[A-Za-z0-9+/]*={0,2}$/.test(text)) {
      throw new Error("invalid base64 payload");
    }
    if (typeof Buffer !== "undefined") {
      return new Uint8Array(Buffer.from(text, "base64"));
    }
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  function base64FromBytes(value) {
    const bytes = asBytes(value);
    if (typeof Buffer !== "undefined") {
      return Buffer.from(bytes).toString("base64");
    }
    let binary = "";
    const chunk = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(offset, offset + chunk));
    }
    return btoa(binary);
  }

  function utf8FromBytes(value) {
    const bytes = asBytes(value);
    if (typeof TextDecoder !== "undefined") {
      return new TextDecoder().decode(bytes);
    }
    return Buffer.from(bytes).toString("utf8");
  }

  function crc32(value) {
    const bytes = asBytes(value);
    let crc = 0xffffffff;
    for (const byte of bytes) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit += 1) {
        crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
      }
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function crcHex(value) {
    return crc32(value).toString(16).padStart(8, "0").toUpperCase();
  }

  function concatBytes(parts) {
    let total = 0;
    for (const part of parts) {
      total += part.length;
    }
    const joined = new Uint8Array(total);
    let offset = 0;
    for (const part of parts) {
      joined.set(part, offset);
      offset += part.length;
    }
    return joined;
  }

  function bytesEqual(left, right) {
    if (left.length !== right.length) {
      return false;
    }
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] !== right[index]) {
        return false;
      }
    }
    return true;
  }

  function decodeWireHeader(bytes, offset) {
    if (bytes.length < offset + 12) {
      throw new Error("wire header too short");
    }
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    if (view.getUint32(offset, true) !== WIRE_MAGIC) {
      throw new Error("invalid wire magic");
    }
    if (view.getUint16(offset + 4, true) !== WIRE_VERSION) {
      throw new Error("invalid wire version");
    }
    const type = view.getUint8(offset + 6);
    const payloadLength = view.getUint32(offset + 8, true);
    const end = offset + 12 + payloadLength;
    if (end > bytes.length) {
      throw new Error("wire length mismatch");
    }
    return { view, type, payloadLength, payloadStart: offset + 12, end };
  }

  function decodeRecordAt(bytes, start) {
    const header = decodeWireHeader(bytes, start);
    if (header.type !== WIRE_RECORD) {
      throw new Error("invalid diagnostic record type");
    }
    if (header.payloadLength !== RECORD_PAYLOAD_BYTES) {
      throw new Error("diagnostic record payload length mismatch");
    }
    const view = header.view;
    let offset = header.payloadStart;
    const u8 = () => view.getUint8(offset++);
    const u16 = () => { const value = view.getUint16(offset, true); offset += 2; return value; };
    const u32 = () => { const value = view.getUint32(offset, true); offset += 4; return value; };
    const i32 = () => { const value = view.getInt32(offset, true); offset += 4; return value; };
    const i64 = () => { const value = Number(view.getBigInt64(offset, true)); offset += 8; return value; };
    const f32 = () => { const value = view.getFloat32(offset, true); offset += 4; return value; };
    const mac = () => {
      const value = Array.from(bytes.subarray(offset, offset + 6));
      offset += 6;
      return value;
    };
    const record = {};
    for (const name of ["boot_id", "capture_id", "record_seq", "frame_seq",
      "feature_seq", "fsm_seq", "rx_timestamp_ms"]) {
      record[name] = u32();
    }
    for (const name of ["radar_timestamp_us", "enqueue_timestamp_us",
      "dequeue_timestamp_us", "process_timestamp_us"]) {
      record[name] = i64();
    }
    record.raw_feature = u32();
    record.waveform_jitter = f32();
    record.feature_status = u8();
    record.stage = u8();
    record.peer_mac = mac();
    for (const name of ["first_frame_seq", "last_frame_seq", "frame_count",
      "first_rx_timestamp_ms", "last_rx_timestamp_ms", "rx_timestamp_span_ms",
      "frame_gap_count"]) {
      record[name] = u32();
    }
    record.window_status = u8();
    record.lifecycle_seq = u32();
    for (const name of ["lifecycle_event", "lifecycle_reason",
      "lifecycle_reset_type", "lifecycle_state_before",
      "lifecycle_state_after"]) {
      record[name] = u8();
    }
    record.lifecycle_pending_count = u32();
    record.lifecycle_timestamp_us = i64();
    record.discard_reason = u8();
    record.batch_id = u32();
    record.batch_index = u16();
    record.batch_size = u16();
    for (const name of ["before_smooth_scaled", "before_baseline_scaled",
      "before_gold_baseline_scaled", "before_noise_scaled"]) {
      record[name] = u32();
    }
    for (const name of ["before_diff_scaled", "before_enter_threshold",
      "before_exit_threshold"]) {
      record[name] = i32();
    }
    record.before_debounce_counter = u32();
    record.before_init_stage = u8();
    record.before_process_state = u8();
    for (const name of ["after_smooth_scaled", "after_baseline_scaled",
      "after_gold_baseline_scaled", "after_noise_scaled"]) {
      record[name] = u32();
    }
    for (const name of ["after_diff_scaled", "after_enter_threshold",
      "after_exit_threshold"]) {
      record[name] = i32();
    }
    record.after_debounce_counter = u32();
    record.after_init_stage = u8();
    record.after_process_state = u8();
    record.transition_reason = u8();
    if (offset !== header.end) {
      throw new Error("diagnostic record field length mismatch");
    }
    return { record, end: header.end };
  }

  function decodeCheckpointAt(bytes, start) {
    const header = decodeWireHeader(bytes, start);
    if (header.type !== WIRE_CHECKPOINT) {
      throw new Error("invalid checkpoint type");
    }
    if (header.payloadLength < CHECKPOINT_FIXED_BYTES) {
      throw new Error("checkpoint payload too short");
    }
    const view = header.view;
    let offset = header.payloadStart;
    const u8 = () => view.getUint8(offset++);
    const u32 = () => { const value = view.getUint32(offset, true); offset += 4; return value; };
    const i32 = () => { const value = view.getInt32(offset, true); offset += 4; return value; };
    const u64 = () => { const value = Number(view.getBigUint64(offset, true)); offset += 8; return value; };
    const i64 = () => { const value = Number(view.getBigInt64(offset, true)); offset += 8; return value; };
    const f32 = () => { const value = view.getFloat32(offset, true); offset += 4; return value; };
    const mac = () => {
      const value = Array.from(bytes.subarray(offset, offset + 6));
      offset += 6;
      return value;
    };
    const checkpoint = {
      checkpoint_version: u32(),
      boot_id: u32(),
      capture_id: u32(),
      lifecycle_seq: u32(),
      batch_seq: u32(),
      channel_count: u32(),
      required_size: u32(),
      timestamp_us: i64(),
      channels: [],
    };
    for (let channelIndex = 0; channelIndex < checkpoint.channel_count; channelIndex += 1) {
      const channel = { peer_mac: mac() };
      channel.process_state = u8();
      channel.init_stage = u8();
      for (const name of ["raw_feature", "smooth_scaled", "baseline_scaled",
        "gold_baseline_scaled", "noise_level_scaled", "init_counter"]) {
        channel[name] = u32();
      }
      channel.init_avg_sum = u64();
      channel.init_avg_count = u32();
      channel.init_avg_start_us = i64();
      for (const name of ["debounce_counter", "reset_counter", "gold_stable_counter"]) {
        channel[name] = u32();
      }
      channel.last_diff = i32();
      for (const name of ["jitter_value", "wander_value", "train_wander_thr",
        "train_jitter_thr"]) {
        channel[name] = f32();
      }
      channel.train_thresholds_valid = u8();
      /* Wire order is defined by diag_wire_checkpoint() in
       * main/web_serial_monitor.c, which is NOT the struct order: the
       * 25-sample presence history is emitted after user_config, and
       * pending_offset is not sent at all. Keep this exact order or every
       * field after train_thresholds_valid is misassigned. */
      channel.presence_total_samples = u32();
      channel.presence_write_index = u32();
      channel.presence_wander_average = f32();
      channel.presence_someone_threshold = f32();
      channel.presence_ready = u8();
      channel.presence_someone_status = u8();
      for (const name of ["diff_scaled", "enter_threshold", "exit_threshold"]) {
        channel[name] = i32();
      }
      channel.active_hold_until_us = i64();
      channel.last_event = u8();
      for (const name of ["raw_capacity", "raw_read_index", "raw_write_index",
        "raw_count", "fsm_seq"]) {
        channel[name] = u32();
      }
      channel.transition_reason = u8();
      channel.pending_count = u32();
      channel.user_config = {
        sensitivity: f32(),
        presence_sensitivity: f32(),
        active_jitter_min: f32(),
        active_filter_ms: u32(),
      };
      channel.presence_wander_history = Array.from({ length: 25 }, f32);
      channel.runtime_config = Array.from({ length: 16 }, f32);
      channel.runtime_uint_config = Array.from({ length: 6 }, u32);
      channel.pending = [];
      for (let itemIndex = 0; itemIndex < channel.pending_count; itemIndex += 1) {
        const item = {};
        for (const name of ["raw_feature", "feature_seq", "frame_seq",
          "rx_timestamp_ms"]) {
          item[name] = u32();
        }
        for (const name of ["radar_timestamp_us", "enqueue_timestamp_us"]) {
          item[name] = i64();
        }
        item.lifecycle_seq = u32();
        item.fsm_seq = u32();
        item.feature_status = u8();
        item.waveform_jitter = f32();
        for (const name of ["first_frame_seq", "last_frame_seq", "frame_count",
          "first_rx_timestamp_ms", "last_rx_timestamp_ms", "rx_timestamp_span_ms",
          "frame_gap_count"]) {
          item[name] = u32();
        }
        item.window_status = u8();
        channel.pending.push(item);
      }
      checkpoint.channels.push(channel);
    }
    if (offset !== header.end) {
      throw new Error("checkpoint field length mismatch");
    }
    return { checkpoint, end: header.end };
  }

  function decodeCheckpointWire(value) {
    const bytes = asBytes(value);
    const decoded = decodeCheckpointAt(bytes, 0);
    if (decoded.end !== bytes.length) {
      throw new Error("checkpoint wire length mismatch");
    }
    return decoded.checkpoint;
  }

  function decodeRecordWires(wires) {
    return wires.map((wire) => {
      const bytes = asBytes(wire);
      const decoded = decodeRecordAt(bytes, 0);
      if (decoded.end !== bytes.length) {
        throw new Error("record wire length mismatch");
      }
      return decoded.record;
    });
  }

  function makeArchiveFilename({ recordingId, identity, now } = {}) {
    const date = now instanceof Date ? now : new Date(now || Date.now());
    const stamp = date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
    const bootId = identity && Number.isInteger(Number(identity.bootId))
      ? Number(identity.bootId) : "unknown";
    const captureId = identity && Number.isInteger(Number(identity.captureId))
      ? Number(identity.captureId) : "unknown";
    const base = String(recordingId || "capture").replace(/[^A-Za-z0-9._-]/g, "_");
    return `${base}.diag-archive.b${bootId}-c${captureId}.${stamp}.json`;
  }

  function buildArchive({ report, recordingId, activityLabel, generatedAt, filename } = {}) {
    if (!report || typeof report !== "object") {
      throw new Error("diagnostic report is required");
    }
    const identity = report.identity || {};
    const transportChunks = Array.isArray(report.transportChunks)
      ? report.transportChunks.map((chunk) => ({ ...chunk }))
      : [];
    const recordWires = Array.isArray(report.recordWires) ? report.recordWires : [];
    let records = [];
    try {
      records = decodeRecordWires(recordWires);
    } catch (_error) {
      /* Validation below reports the concrete failure; keep the rest of the
       * transport so an incomplete archive still preserves every raw byte. */
      records = [];
    }
    /* Always decode from the wire when it exists. The live page keeps a
     * header-only checkpoint summary in report.checkpoint (camelCase, no
     * channels), so using it here would silently drop every channel. */
    let checkpoint = null;
    if (report.checkpointWire) {
      try {
        checkpoint = decodeCheckpointWire(report.checkpointWire);
      } catch (_error) {
        checkpoint = null;
      }
    }
    if (!checkpoint && report.checkpoint) {
      checkpoint = report.checkpoint;
    }
    const archive = {
      schema: ARCHIVE_SCHEMA,
      schema_version: ARCHIVE_SCHEMA_VERSION,
      generated_at_utc: generatedAt || new Date().toISOString(),
      recording: {
        recording_id: recordingId || null,
        activity_label: activityLabel || null,
      },
      identity: {
        protocol_version: 1,
        boot_id: identity.bootId === undefined ? null : identity.bootId,
        capture_id: identity.captureId === undefined ? null : identity.captureId,
      },
      status: "incomplete",
      reason: null,
      export: {
        method: "browser-download",
        requested: false,
        requested_at_utc: null,
        filename: filename || null,
        note: "A browser download request is not proof that the file reached disk; verify the file in the browser downloads and re-validate it with this page.",
      },
      integrity: {
        transport_status: report.status === undefined ? null : report.status,
        transport_reason: report.reason === undefined ? null : report.reason,
        chunk_count: report.chunkCount === undefined ? transportChunks.length : report.chunkCount,
        last_chunk_seq: report.lastChunkSeq === undefined ? null : report.lastChunkSeq,
        duplicates: report.duplicates === undefined ? 0 : report.duplicates,
        rejected: report.rejected === undefined ? 0 : report.rejected,
        crc_failures: report.crcFailures === undefined ? 0 : report.crcFailures,
        missing_chunks: Array.isArray(report.missingChunks) ? report.missingChunks.slice() : [],
        record_count: report.recordCount === undefined ? records.length : report.recordCount,
        record_seq_gaps: report.recordSeqGaps === undefined ? null : report.recordSeqGaps,
        checkpoint_channels: report.checkpointChannels === undefined ? null : report.checkpointChannels,
        checkpoint_bytes: report.checkpointBytes === undefined ? null : report.checkpointBytes,
        device_status: report.deviceStatus === undefined ? null : report.deviceStatus,
        manifest_integrity: report.integrity === undefined ? null : report.integrity,
        overflow_count: report.overflowCount === undefined ? null : report.overflowCount,
        queue_pending_at_stop: report.queuePendingAtStop === undefined ? null : report.queuePendingAtStop,
        counters: report.counters || null,
      },
      transport: {
        chunk_count: transportChunks.length,
        last_chunk_seq: report.lastChunkSeq === undefined ? null : report.lastChunkSeq,
        chunks: transportChunks,
      },
      checkpoint: {
        wire_base64: report.checkpointWire ? base64FromBytes(report.checkpointWire) : null,
        decoded: checkpoint,
      },
      manifest: report.manifest || null,
      records,
      record_wires_base64: recordWires.map((wire) => base64FromBytes(wire)),
      verification: null,
    };
    const validation = validateArchive(archive);
    archive.status = validation.status;
    archive.reason = validation.reason;
    archive.verification = {
      verified_at_utc: new Date().toISOString(),
      ...validation.checks,
      errors: validation.errors,
    };
    return archive;
  }

  function validateArchive(archive) {
    const errors = [];
    const checks = {};
    const add = (message) => {
      if (!errors.includes(message)) {
        errors.push(message);
      }
    };
    if (!archive || typeof archive !== "object" || Array.isArray(archive)) {
      return {
        ok: false,
        status: "incomplete",
        reason: "invalid_archive",
        errors: ["archive must be a JSON object"],
        checks,
      };
    }
    if (archive.schema !== ARCHIVE_SCHEMA) {
      add("schema mismatch");
    }
    if (archive.schema_version !== ARCHIVE_SCHEMA_VERSION) {
      add("schema_version mismatch");
    }
    /* A durable archive must carry the decoded copies, not only raw transport:
     * without them the file no longer answers "what did the device record?"
     * even if the chunks still validate. */
    if (!archive.manifest || typeof archive.manifest !== "object" ||
        Array.isArray(archive.manifest)) {
      add("archive.manifest missing");
    }
    if (!archive.checkpoint || typeof archive.checkpoint !== "object" ||
        Array.isArray(archive.checkpoint)) {
      add("archive.checkpoint missing");
    }
    if (!Array.isArray(archive.records)) {
      add("archive.records missing");
    }
    const identity = archive.identity && typeof archive.identity === "object"
      ? archive.identity : {};
    const bootId = Number(identity.boot_id);
    const captureId = Number(identity.capture_id);
    if (!Number.isInteger(bootId) || !Number.isInteger(captureId)) {
      add("identity.boot_id/capture_id missing");
    }

    const transport = archive.transport && typeof archive.transport === "object"
      ? archive.transport : {};
    const chunks = Array.isArray(transport.chunks) ? transport.chunks : [];
    if (!chunks.length) {
      add("transport.chunks missing");
    }
    const bySeq = new Map();
    let lastChunkSeq = -1;
    let chunkCrcOk = true;
    let chunkLengthOk = true;
    for (const chunk of chunks) {
      if (!chunk || typeof chunk !== "object") {
        add("transport chunk is not an object");
        continue;
      }
      const seq = Number(chunk.chunk_seq);
      if (!Number.isInteger(seq) || seq < 0) {
        add(`invalid chunk_seq ${chunk.chunk_seq}`);
        continue;
      }
      if (bySeq.has(seq)) {
        add(`duplicate chunk_seq ${seq}`);
      }
      bySeq.set(seq, chunk);
      lastChunkSeq = Math.max(lastChunkSeq, seq);
      if (Number(chunk.boot_id) !== bootId || Number(chunk.capture_id) !== captureId) {
        add(`chunk ${seq} identity mismatch`);
      }
      if (typeof chunk.chunk_type !== "string" || !chunk.chunk_type) {
        add(`chunk ${seq} chunk_type missing`);
      }
      const payloadLength = Number(chunk.payload_length);
      if (!Number.isInteger(payloadLength) || payloadLength < 0 ||
          payloadLength > MAX_PAYLOAD_BYTES) {
        add(`chunk ${seq} payload_length invalid`);
        chunkLengthOk = false;
      }
      let payload;
      try {
        payload = bytesFromBase64(String(chunk.payload_base64 || ""));
      } catch (_error) {
        add(`chunk ${seq} payload_base64 invalid`);
        continue;
      }
      if (payload.length !== payloadLength) {
        add(`chunk ${seq} payload length mismatch`);
        chunkLengthOk = false;
      }
      if (crcHex(payload) !== String(chunk.crc32 || "").toUpperCase()) {
        add(`chunk ${seq} CRC mismatch`);
        chunkCrcOk = false;
      }
    }
    const missingChunks = [];
    for (let seq = 0; seq <= lastChunkSeq; seq += 1) {
      if (!bySeq.has(seq)) {
        missingChunks.push(seq);
      }
    }
    if (missingChunks.length) {
      add(`missing chunk_seq: ${missingChunks.slice(0, 12).join(",")}` +
        (missingChunks.length > 12 ? ",..." : ""));
    }
    checks.chunk_count = chunks.length;
    checks.last_chunk_seq = lastChunkSeq;
    checks.chunk_crc = chunkCrcOk;
    checks.chunk_length = chunkLengthOk;
    checks.chunk_sequence = missingChunks.length === 0;
    checks.missing_chunks = missingChunks;

    let checkpoint = null;
    let checkpointOk = false;
    const checkpointChunks = chunks
      .filter((chunk) => chunk && chunk.chunk_type === "CHECKPOINT")
      .sort((left, right) => Number(left.chunk_seq) - Number(right.chunk_seq));
    if (!checkpointChunks.length) {
      add("checkpoint chunk missing");
    } else {
      try {
        const checkpointWire = concatBytes(checkpointChunks.map((chunk) =>
          bytesFromBase64(String(chunk.payload_base64 || ""))));
        if (archive.checkpoint && archive.checkpoint.wire_base64) {
          const declaredWire = bytesFromBase64(String(archive.checkpoint.wire_base64));
          if (!bytesEqual(declaredWire, checkpointWire)) {
            add("checkpoint wire copy mismatch");
          }
        }
        checkpoint = decodeCheckpointWire(checkpointWire);
        if (Number(checkpoint.boot_id) !== bootId ||
            Number(checkpoint.capture_id) !== captureId) {
          add("checkpoint identity mismatch");
        }
        if (!Number.isInteger(Number(checkpoint.channel_count)) ||
            Number(checkpoint.channel_count) <= 0) {
          add("checkpoint channel_count invalid");
        }
        if (!Number.isInteger(Number(checkpoint.required_size)) ||
            Number(checkpoint.required_size) <= 0) {
          add("checkpoint required_size invalid");
        }
        checkpointOk = true;
      } catch (error) {
        add(`checkpoint decode failed: ${error.message}`);
      }
    }
    checks.checkpoint = checkpointOk;
    checks.checkpoint_channels = checkpoint ? checkpoint.channel_count : null;

    let manifest = null;
    let manifestOk = false;
    const manifestChunks = chunks
      .filter((chunk) => chunk && chunk.chunk_type === "CAPTURE_MANIFEST");
    if (manifestChunks.length !== 1) {
      add(`manifest chunk count ${manifestChunks.length} != 1`);
    } else {
      try {
        manifest = JSON.parse(utf8FromBytes(bytesFromBase64(
          String(manifestChunks[0].payload_base64 || ""))));
        if (Number(manifest.protocol_version) !== 1) {
          add("manifest protocol_version mismatch");
        }
        if (Number(manifest.boot_id) !== bootId ||
            Number(manifest.capture_id) !== captureId) {
          add("manifest identity mismatch");
        }
        if (!Number.isInteger(Number(manifest.record_count))) {
          add("manifest record_count invalid");
        }
        if (!Number.isInteger(Number(manifest.overflow_count))) {
          add("manifest overflow_count invalid");
        }
        if (archive.manifest && typeof archive.manifest === "object") {
          for (const key of ["protocol_version", "boot_id", "capture_id",
            "record_count", "overflow_count", "integrity", "status"]) {
            if (String(archive.manifest[key]) !== String(manifest[key])) {
              add(`manifest copy mismatch (${key})`);
              break;
            }
          }
        }
        manifestOk = true;
      } catch (error) {
        add(`manifest decode failed: ${error.message}`);
      }
    }
    checks.manifest = manifestOk;

    let records = [];
    let recordsOk = false;
    const recordChunks = chunks
      .filter((chunk) => chunk && chunk.chunk_type === "DIAGNOSTIC_RECORDS")
      .sort((left, right) => Number(left.chunk_seq) - Number(right.chunk_seq));
    try {
      for (const chunk of recordChunks) {
        const payload = bytesFromBase64(String(chunk.payload_base64 || ""));
        const decoded = [];
        let offset = 0;
        while (offset < payload.length) {
          const entry = decodeRecordAt(payload, offset);
          decoded.push(entry.record);
          offset = entry.end;
        }
        if (!decoded.length) {
          throw new Error(`chunk ${chunk.chunk_seq} has no records`);
        }
        const expectedCount = chunk.record_count;
        if (expectedCount !== null && expectedCount !== undefined &&
            Number.isInteger(Number(expectedCount)) && decoded.length !== Number(expectedCount)) {
          throw new Error(`chunk ${chunk.chunk_seq} record_count mismatch`);
        }
        const firstSeq = chunk.first_record_seq;
        const lastSeq = chunk.last_record_seq;
        if ((firstSeq !== null && firstSeq !== undefined &&
             decoded[0].record_seq !== Number(firstSeq)) ||
            (lastSeq !== null && lastSeq !== undefined &&
             decoded[decoded.length - 1].record_seq !== Number(lastSeq))) {
          throw new Error(`chunk ${chunk.chunk_seq} record range mismatch`);
        }
        for (const record of decoded) {
          if (Number(record.boot_id) !== bootId ||
              Number(record.capture_id) !== captureId) {
            throw new Error(`record ${record.record_seq} identity mismatch`);
          }
          records.push(record);
        }
      }
      recordsOk = true;
    } catch (error) {
      add(`records: ${error.message}`);
    }
    records.sort((left, right) => left.record_seq - right.record_seq);
    const recordSeqs = records.map((record) => record.record_seq);
    let sequenceOk = recordSeqs.length > 0 && recordSeqs[0] === 0;
    for (let index = 1; index < recordSeqs.length; index += 1) {
      if (recordSeqs[index] !== recordSeqs[index - 1] + 1) {
        sequenceOk = false;
      }
    }
    if (!sequenceOk) {
      add("record_seq is not contiguous from 0");
    }
    if (Array.isArray(archive.records)) {
      if (archive.records.length !== records.length) {
        add("archive.records count mismatch");
      } else {
        const declaredSeqs = archive.records
          .map((record) => Number(record.record_seq))
          .sort((left, right) => left - right);
        if (declaredSeqs.join(",") !== recordSeqs.join(",")) {
          add("archive.records sequence mismatch");
        }
      }
    }
    checks.records = recordsOk;
    checks.record_count = records.length;
    checks.record_seq_first = recordSeqs.length ? recordSeqs[0] : null;
    checks.record_seq_last = recordSeqs.length ? recordSeqs[recordSeqs.length - 1] : null;
    checks.record_sequence_contiguous = sequenceOk;

    let manifestCountOk = false;
    let integrityOk = false;
    let overflowOk = false;
    let statusOk = false;
    if (manifestOk && recordsOk) {
      manifestCountOk = records.length === Number(manifest.record_count);
      if (!manifestCountOk) {
        add(`manifest record_count ${manifest.record_count} != decoded ${records.length}`);
      }
    }
    if (manifestOk) {
      integrityOk = Number(manifest.integrity) === 0;
      if (!integrityOk) {
        add(`manifest integrity ${manifest.integrity} is not COMPLETE`);
      }
      overflowOk = Number(manifest.overflow_count) === 0;
      if (!overflowOk) {
        add(`manifest overflow_count ${manifest.overflow_count} != 0`);
      }
      statusOk = Number(manifest.status) === 2 || Number(manifest.status) === 4;
      if (!statusOk) {
        add(`manifest status ${manifest.status} is not complete`);
      }
    }
    checks.manifest_record_count_match = manifestCountOk;
    checks.integrity_complete = integrityOk;
    checks.overflow_zero = overflowOk;
    checks.status_complete = statusOk;

    const complete = errors.length === 0 && chunkCrcOk && chunkLengthOk &&
      missingChunks.length === 0 && checkpointOk && manifestOk && recordsOk &&
      sequenceOk && manifestCountOk && integrityOk && overflowOk && statusOk;
    return {
      ok: complete,
      status: complete ? "complete" : "incomplete",
      reason: complete ? null : (errors[0] || "incomplete"),
      errors,
      checks,
    };
  }

  function serializeArchive(archive) {
    return `${JSON.stringify(archive, (_key, value) =>
      (typeof value === "bigint" ? Number(value) : value), 2)}\n`;
  }

  function parseArchive(text) {
    const archive = JSON.parse(text);
    return { archive, validation: validateArchive(archive) };
  }

  return {
    ARCHIVE_SCHEMA,
    ARCHIVE_SCHEMA_VERSION,
    buildArchive,
    validateArchive,
    serializeArchive,
    parseArchive,
    makeArchiveFilename,
    crcHex,
  };
});
