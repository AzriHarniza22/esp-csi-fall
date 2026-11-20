#!/usr/bin/env node
"use strict";

/*
 * Synthetic verification for the durable diagnostic archive.
 *
 * Builds the same wire shapes the firmware emits for the 2026-11-12 run:
 * 193 records (seq 0-192), one checkpoint with 3 channels, batched
 * DIAGNOSTIC_RECORDS chunks (<= 4 records), and one CAPTURE_MANIFEST.
 */
const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { encodeChunk, decodeDiagnosticWire } = require("../diagnostic_protocol.js");
const {
  buildArchive, validateArchive, serializeArchive, parseArchive, makeArchiveFilename,
} = require("../diagnostic_archive.js");

const BOOT_ID = 3550930125;
const CAPTURE_ID = 1;
const RECORD_COUNT = 193;
const CHANNELS = 3;

class Writer {
  constructor(size) {
    this.buf = Buffer.alloc(size);
    this.offset = 0;
  }
  u8(value) { this.buf.writeUInt8(value >>> 0, this.offset); this.offset += 1; return this; }
  u16(value) { this.buf.writeUInt16LE(value >>> 0, this.offset); this.offset += 2; return this; }
  u32(value) { this.buf.writeUInt32LE(value >>> 0, this.offset); this.offset += 4; return this; }
  i32(value) { this.buf.writeInt32LE(value | 0, this.offset); this.offset += 4; return this; }
  u64(value) { this.buf.writeBigUInt64LE(BigInt(value), this.offset); this.offset += 8; return this; }
  i64(value) { this.buf.writeBigInt64LE(BigInt(value), this.offset); this.offset += 8; return this; }
  f32(value) { this.buf.writeFloatLE(value, this.offset); this.offset += 4; return this; }
  mac(value) {
    for (let index = 0; index < 6; index += 1) {
      this.buf[this.offset + index] = value[index];
    }
    this.offset += 6;
    return this;
  }
}

function makeRecordWire(bootId, captureId, recordSeq) {
  const writer = new Writer(12 + 204);
  /* 12-byte wire header: magic u32, version u16, type u8, reserved u8, length u32. */
  writer.u32(0x33574d48).u16(1).u8(1).u8(0).u32(204);
  writer.u32(bootId).u32(captureId).u32(recordSeq)
    .u32(recordSeq + 1000).u32(recordSeq + 2000).u32(recordSeq + 3000)
    .u32(1000 + recordSeq);
  writer.i64(1000000 + recordSeq).i64(1000100 + recordSeq)
    .i64(1000200 + recordSeq).i64(1000300 + recordSeq);
  writer.u32(100 + recordSeq).f32(1.5 + recordSeq * 0.01).u8(1).u8(2)
    .mac([0xe2, 0x0a, 0x68, 0x1d, 0xb5, 0x16]);
  writer.u32(recordSeq * 10).u32(recordSeq * 10 + 9).u32(10)
    .u32(1000 + recordSeq).u32(1010 + recordSeq).u32(10).u32(0);
  writer.u8(1).u32(recordSeq);
  writer.u8(0).u8(0).u8(0).u8(0).u8(0).u32(0).i64(1000000 + recordSeq);
  writer.u8(0).u32(1).u16(0).u16(1);
  writer.u32(100 + recordSeq).u32(50 + recordSeq).u32(0).u32(5);
  writer.i32(10 + recordSeq).i32(20).i32(5);
  writer.u32(0).u8(0).u8(0);
  writer.u32(100 + recordSeq).u32(50 + recordSeq).u32(0).u32(5);
  writer.i32(10 + recordSeq).i32(20).i32(5);
  writer.u32(0).u8(0).u8(0).u8(0);
  assert.strictEqual(writer.offset, writer.buf.length);
  return writer.buf;
}

function makeCheckpointWire(bootId, captureId, channels) {
  const channelBytes = 353;
  const itemBytes = 74;
  const pendingChannels = 1;
  const payloadBytes = 36 + channels * channelBytes + pendingChannels * itemBytes;
  const writer = new Writer(12 + payloadBytes);
  writer.u32(0x33574d48).u16(1).u8(2).u8(0).u32(payloadBytes);
  writer.u32(1).u32(bootId).u32(captureId).u32(22).u32(924)
    .u32(channels).u32(payloadBytes - 12).i64(95166132);
  for (let channel = 0; channel < channels; channel += 1) {
    /* Field order follows diag_wire_checkpoint() in main/web_serial_monitor.c,
     * not the C struct order: presence history comes after user_config and
     * pending_offset is absent from the wire. */
    const pendingCount = channel < pendingChannels ? 1 : 0;
    writer.mac([0xe2, 0x0a, 0x68, 0x1d, 0xb5, 0x16 + channel]);
    writer.u8(0).u8(0);
    writer.u32(100 + channel).u32(50).u32(0).u32(5).u32(0).u32(0);
    writer.u64(0).u32(0).i64(0);
    writer.u32(0).u32(0).u32(0);
    writer.i32(0);
    writer.f32(1).f32(2).f32(3).f32(4);
    writer.u8(0);
    writer.u32(700 + channel).u32(5 + channel);
    writer.f32(1.25 + channel).f32(2.5 + channel);
    writer.u8(0).u8(0);
    writer.i32(11 + channel).i32(12).i32(13);
    writer.i64(9000 + channel);
    writer.u8(0);
    writer.u32(20).u32(0).u32(0).u32(0).u32(0);
    writer.u8(3).u32(pendingCount);
    writer.f32(0.5 + channel).f32(0.25).f32(0.125).u32(900 + channel);
    for (let index = 0; index < 25; index += 1) writer.f32(index + 0.5 + channel);
    for (let index = 0; index < 16; index += 1) writer.f32(index + 0.25);
    for (let index = 0; index < 6; index += 1) writer.u32(1000 + index);
    if (pendingCount) {
      writer.u32(1234).u32(11).u32(12).u32(13);
      writer.i64(100000).i64(100100);
      writer.u32(14).u32(15);
      writer.u8(1).f32(0.75);
      writer.u32(16).u32(17).u32(2).u32(18).u32(19).u32(1).u32(0);
      writer.u8(1);
    }
  }
  assert.strictEqual(writer.offset, writer.buf.length);
  return writer.buf;
}

function makeManifest(recordCount, overrides) {
  return Object.assign({
    protocol_version: 1,
    boot_id: BOOT_ID,
    capture_id: CAPTURE_ID,
    status: 2,
    integrity: 0,
    overflow_count: 0,
    record_count: recordCount,
    diag_capture_enabled: false,
    diag_queue_ready: true,
    diag_start_result: 0,
    feature_callback_count: 48,
    fsm_enqueued: 972,
    fsm_dequeued: 972,
    fsm_processed: 972,
    diag_emit_attempted: recordCount,
    diag_emit_skipped_disabled: 0,
    diag_emit_skipped_queue_null: 0,
    diag_emit_stored: recordCount,
    diag_emit_failed: 0,
    diag_queue_pending_at_stop: 0,
  }, overrides || {});
}

function toTransportChunk(chunk) {
  return {
    chunk_seq: chunk.chunk_seq,
    chunk_type: chunk.chunk_type,
    protocol_version: chunk.protocol_version,
    boot_id: chunk.boot_id,
    capture_id: chunk.capture_id,
    record_count: chunk.record_count,
    first_record_seq: chunk.first_record_seq,
    last_record_seq: chunk.last_record_seq,
    payload_length: chunk.payload_length,
    crc32: chunk.crc32,
    payload_base64: chunk.payload,
  };
}

function makeFixture(options) {
  const opts = options || {};
  const recordWires = [];
  for (let seq = 0; seq < RECORD_COUNT; seq += 1) {
    recordWires.push(makeRecordWire(BOOT_ID, CAPTURE_ID, seq));
  }
  const checkpointWire = makeCheckpointWire(BOOT_ID, CAPTURE_ID, CHANNELS);
  const chunks = [];
  let chunkSeq = 0;
  chunks.push(encodeChunk({
    bootId: BOOT_ID, captureId: CAPTURE_ID, chunkSeq: chunkSeq++,
    chunkType: "CHECKPOINT", payload: checkpointWire, recordCount: 0,
  }));
  for (let start = 0; start < recordWires.length; start += 4) {
    const batch = recordWires.slice(start, start + 4);
    chunks.push(encodeChunk({
      bootId: BOOT_ID, captureId: CAPTURE_ID, chunkSeq: chunkSeq++,
      chunkType: "DIAGNOSTIC_RECORDS", payload: Buffer.concat(batch),
      firstRecordSeq: start, lastRecordSeq: start + batch.length - 1,
      recordCount: batch.length,
    }));
  }
  const manifest = opts.manifest || makeManifest(RECORD_COUNT);
  chunks.push(encodeChunk({
    bootId: BOOT_ID, captureId: CAPTURE_ID, chunkSeq: chunkSeq++,
    chunkType: "CAPTURE_MANIFEST", payload: Buffer.from(JSON.stringify(manifest)),
    recordCount: 0,
  }));
  const transportChunks = chunks.map(toTransportChunk);
  const report = {
    status: opts.reportStatus || "complete",
    reason: null,
    doneOk: true,
    timeout: false,
    chunkCount: transportChunks.length,
    duplicates: 0,
    rejected: 0,
    crcFailures: 0,
    missingChunks: [],
    lastChunkSeq: transportChunks.length - 1,
    identity: { bootId: BOOT_ID, captureId: CAPTURE_ID },
    manifest,
    /* Mirrors what the live page keeps: header-only, camelCase, no channels.
     * buildArchive must re-decode the full checkpoint from checkpointWire. */
    checkpoint: {
      checkpointVersion: 1,
      bootId: BOOT_ID,
      captureId: CAPTURE_ID,
      lifecycleSeq: 22,
      batchSeq: 924,
      channelCount: CHANNELS,
      requiredSize: checkpointWire.length - 12,
      timestampUs: 95166132,
    },
    checkpointWire,
    checkpointBytes: checkpointWire.length,
    checkpointChannels: CHANNELS,
    recordWires,
    recordCount: RECORD_COUNT,
    recordSeqGaps: 0,
    integrity: "COMPLETE",
    deviceStatus: "STOPPED_COMPLETE",
    overflowCount: 0,
    queuePendingAtStop: 0,
    counters: {
      attempted: RECORD_COUNT, stored: RECORD_COUNT, failed: 0,
      skippedDisabled: 0, skippedQueueNull: 0,
    },
    transportChunks,
  };
  return { report, transportChunks, manifest, recordWires, checkpointWire };
}

const fixture = makeFixture();
const archive = buildArchive({
  report: fixture.report,
  recordingId: "20261112T163029Z_empty_room_013",
  activityLabel: "empty_room",
  generatedAt: "2026-11-13T00:00:00.000Z",
  filename: "20261112T163029Z_empty_room_013.diag-archive.b3550930125-c1.20261113T000000Z.json",
});

/* 1. 193 records, seq 0-192, checkpoint/chunks/manifest/decoded records present. */
assert.strictEqual(archive.status, "complete");
assert.strictEqual(archive.transport.chunks.length, fixture.transportChunks.length);
assert.strictEqual(archive.records.length, RECORD_COUNT);
assert.strictEqual(archive.records[0].record_seq, 0);
assert.strictEqual(archive.records[RECORD_COUNT - 1].record_seq, 192);
assert.strictEqual(archive.manifest.record_count, RECORD_COUNT);
assert.strictEqual(archive.checkpoint.decoded.channel_count, CHANNELS);
/* Field-level check that the decoder follows the firmware wire order (presence
 * history after user_config), not the C struct order. */
const channelZero = archive.checkpoint.decoded.channels[0];
assert.strictEqual(channelZero.presence_total_samples, 700);
assert.strictEqual(channelZero.presence_write_index, 5);
assert.ok(Math.abs(channelZero.presence_wander_average - 1.25) < 1e-6);
assert.ok(Math.abs(channelZero.presence_someone_threshold - 2.5) < 1e-6);
assert.strictEqual(channelZero.diff_scaled, 11);
assert.strictEqual(channelZero.active_hold_until_us, 9000);
assert.strictEqual(channelZero.transition_reason, 3);
assert.strictEqual(channelZero.pending_count, 1);
assert.ok(Math.abs(channelZero.user_config.sensitivity - 0.5) < 1e-6);
assert.strictEqual(channelZero.user_config.active_filter_ms, 900);
assert.ok(Math.abs(channelZero.presence_wander_history[24] - 24.5) < 1e-6);
assert.ok(Math.abs(channelZero.runtime_config[15] - 15.25) < 1e-6);
assert.strictEqual(channelZero.runtime_uint_config[5], 1005);
assert.strictEqual(channelZero.pending.length, 1);
assert.strictEqual(channelZero.pending[0].raw_feature, 1234);
assert.strictEqual(channelZero.pending[0].rx_timestamp_ms, 13);
assert.strictEqual(channelZero.pending[0].window_status, 1);
const channelOne = archive.checkpoint.decoded.channels[1];
assert.strictEqual(channelOne.pending_count, 0);
assert.strictEqual(channelOne.presence_total_samples, 701);
assert.ok(Math.abs(channelOne.presence_wander_average - 2.25) < 1e-6);
assert.ok(archive.checkpoint.wire_base64.length > 0);
/* The host recorder's decoder must agree with the archive decoder and with the
 * firmware wire order, otherwise diagnostic_recorder.js persists wrong values. */
const protocolCheckpoint = decodeDiagnosticWire(fixture.checkpointWire).checkpoint;
assert.strictEqual(protocolCheckpoint.channels[0].presence_total_samples, 700);
assert.strictEqual(protocolCheckpoint.channels[0].user_config.active_filter_ms, 900);
assert.ok(Math.abs(protocolCheckpoint.channels[0].presence_wander_history[24] - 24.5) < 1e-6);
assert.strictEqual(protocolCheckpoint.channels[0].pending[0].raw_feature, 1234);
assert.ok(archive.record_wires_base64.length === RECORD_COUNT);
assert.strictEqual(archive.verification.record_count, RECORD_COUNT);
assert.strictEqual(archive.verification.chunk_count, fixture.transportChunks.length);
assert.strictEqual(archive.verification.chunk_crc, true);
assert.strictEqual(archive.verification.record_sequence_contiguous, true);
assert.strictEqual(archive.verification.manifest_record_count_match, true);
assert.strictEqual(archive.verification.integrity_complete, true);
assert.strictEqual(archive.verification.overflow_zero, true);

/* 2. Serialize -> read from a real file -> parse -> validate again. */
const text = serializeArchive(archive);
/* Optional artefact for manual/browser verification; the temp-file read-back
 * below stays the automated proof. */
if (process.env.DIAG_ARCHIVE_OUT) {
  fs.writeFileSync(process.env.DIAG_ARCHIVE_OUT, text);
  console.log(`diagnostic_archive: wrote ${process.env.DIAG_ARCHIVE_OUT} (${text.length} bytes)`);
}
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "diag-archive-"));
const tempFile = path.join(tempDir, archive.export.filename);
fs.writeFileSync(tempFile, text);
const readBack = fs.readFileSync(tempFile, "utf8");
const parsed = parseArchive(readBack);
assert.strictEqual(parsed.validation.ok, true);
assert.strictEqual(parsed.validation.status, "complete");
assert.strictEqual(parsed.validation.checks.record_count, RECORD_COUNT);
assert.strictEqual(parsed.validation.checks.record_seq_first, 0);
assert.strictEqual(parsed.validation.checks.record_seq_last, 192);
assert.strictEqual(parsed.validation.checks.chunk_count, fixture.transportChunks.length);
assert.strictEqual(parsed.archive.records.length, RECORD_COUNT);
assert.strictEqual(parsed.archive.transport.chunks.length, fixture.transportChunks.length);
assert.ok(parsed.archive.checkpoint.wire_base64.length > 0);
fs.rmSync(tempDir, { recursive: true, force: true });

/* 3. CRC corruption is rejected, not silently accepted. */
const crcTampered = JSON.parse(text);
crcTampered.transport.chunks[5].crc32 = "00000000";
const crcValidation = validateArchive(crcTampered);
assert.strictEqual(crcValidation.ok, false);
assert.strictEqual(crcValidation.status, "incomplete");
assert.ok(crcValidation.errors.some((message) => message.includes("CRC mismatch")));

/* 4. Missing chunk is rejected. */
const missingTampered = JSON.parse(text);
missingTampered.transport.chunks.splice(5, 1);
const missingValidation = validateArchive(missingTampered);
assert.strictEqual(missingValidation.ok, false);
assert.ok(missingValidation.errors.some((message) => message.includes("missing chunk_seq")));

/* 5. Manifest record_count mismatch is rejected. */
const countTampered = JSON.parse(text);
countTampered.manifest.record_count = RECORD_COUNT + 1;
const countValidation = validateArchive(countTampered);
assert.strictEqual(countValidation.ok, false);
assert.ok(countValidation.errors.some((message) => message.includes("manifest copy mismatch") ||
  message.includes("manifest record_count")));

/* 6. Identity mismatch is rejected. */
const identityTampered = JSON.parse(text);
identityTampered.transport.chunks[4].boot_id = BOOT_ID + 1;
const identityValidation = validateArchive(identityTampered);
assert.strictEqual(identityValidation.ok, false);
assert.ok(identityValidation.errors.some((message) => message.includes("identity mismatch")));

/* 7. Incomplete archive: manifest absent never becomes COMPLETE. */
const noManifestReport = JSON.parse(JSON.stringify(fixture.report));
noManifestReport.manifest = null;
const noManifestChunks = noManifestReport.transportChunks.filter((chunk) =>
  chunk.chunk_type !== "CAPTURE_MANIFEST");
noManifestReport.transportChunks = noManifestChunks;
noManifestReport.chunkCount = noManifestChunks.length;
noManifestReport.lastChunkSeq = noManifestChunks.length - 1;
const noManifestArchive = buildArchive({
  report: noManifestReport,
  recordingId: "20261112T163029Z_empty_room_013",
  activityLabel: "empty_room",
});
assert.strictEqual(noManifestArchive.status, "incomplete");
assert.ok(String(noManifestArchive.reason).includes("manifest"));

/* 8. Invalid integrity / overflow never becomes COMPLETE even if transport is intact. */
const badIntegrityFixture = makeFixture({ manifest: makeManifest(RECORD_COUNT, { integrity: 1 }) });
const badIntegrityArchive = buildArchive({
  report: badIntegrityFixture.report,
  recordingId: "20261112T163029Z_empty_room_013",
  activityLabel: "empty_room",
});
assert.strictEqual(badIntegrityArchive.status, "incomplete");
assert.ok(String(badIntegrityArchive.reason).includes("integrity"));
const overflowFixture = makeFixture({ manifest: makeManifest(RECORD_COUNT, { overflow_count: 3 }) });
const overflowArchive = buildArchive({
  report: overflowFixture.report,
  recordingId: "20261112T163029Z_empty_room_013",
  activityLabel: "empty_room",
});
assert.strictEqual(overflowArchive.status, "incomplete");
assert.ok(String(overflowArchive.reason).includes("overflow"));

/* 9. Record sequence gap is rejected. */
const gapReport = JSON.parse(JSON.stringify(fixture.report));
const gapChunks = gapReport.transportChunks.filter((chunk) =>
  chunk.chunk_type !== "DIAGNOSTIC_RECORDS" || chunk.chunk_seq !== 3);
gapReport.transportChunks = gapChunks;
gapReport.chunkCount = gapChunks.length;
gapReport.lastChunkSeq = gapChunks[gapChunks.length - 1].chunk_seq;
const gapArchive = buildArchive({
  report: gapReport,
  recordingId: "20261112T163029Z_empty_room_013",
  activityLabel: "empty_room",
});
assert.strictEqual(gapArchive.status, "incomplete");
assert.ok(gapArchive.verification.record_count < RECORD_COUNT);

/* 10. Filename is unique per timestamp and carries capture identity. */
const first = makeArchiveFilename({
  recordingId: "20261112T163029Z_empty_room_013",
  identity: { bootId: BOOT_ID, captureId: CAPTURE_ID },
  now: new Date("2026-11-13T00:00:00Z"),
});
const second = makeArchiveFilename({
  recordingId: "20261112T163029Z_empty_room_013",
  identity: { bootId: BOOT_ID, captureId: CAPTURE_ID },
  now: new Date("2026-11-13T00:00:01Z"),
});
assert.notStrictEqual(first, second);
assert.ok(first.includes("20261112T163029Z_empty_room_013"));
assert.ok(first.includes(`b${BOOT_ID}-c${CAPTURE_ID}`));
assert.ok(first.endsWith(".json"));

/* 11. An archive stripped of its decoded records cannot be COMPLETE even when
 * every transport chunk still validates. */
const stripped = JSON.parse(text);
delete stripped.records;
const strippedValidation = validateArchive(stripped);
assert.strictEqual(strippedValidation.ok, false);
assert.ok(strippedValidation.errors.some((message) => message.includes("archive.records")));

console.log("diagnostic_archive: 11 PASS");
