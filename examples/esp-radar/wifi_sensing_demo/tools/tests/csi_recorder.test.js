#!/usr/bin/env node
const path = require("path");
const CsiRecorder = require("../csi_recorder.js");
const { report } = require("./harness.js");

function main() {
  console.log("csi_recorder.js");

  report("slug collapses punctuation", CsiRecorder.slugLabel("Jatuh!!  1") === "jatuh_1");
  report("empty label is empty slug", CsiRecorder.slugLabel("   ") === "");
  report("custom label wins", CsiRecorder.resolveLabel("duduk", "jongkok dalam") === "jongkok dalam");
  report("preset used when custom blank", CsiRecorder.resolveLabel("berdiri", "  ") === "berdiri");
  report("safe id accepts generated names", CsiRecorder.isSafeRecordingId("20261022T014532Z_duduk_001"));
  report("unsafe id rejects traversal", CsiRecorder.isSafeRecordingId("../etc/passwd") === false);

  const bytes = new Int8Array([1, 2, 3, 4]);
  const iq = CsiRecorder.decodePairs(bytes, 0);
  report("int8 pairs", iq.length === 2 && iq[0][0] === 1 && iq[0][1] === 2 && iq[1][0] === 3 && iq[1][1] === 4);

  const frames = [
    {
      seq: 1,
      ts_us: 100,
      mac: "aa:bb:cc:dd:ee:ff",
      rssi: -40,
      data_type: 0,
      dropped: 0,
      validBytes: bytes,
      iq,
    },
  ];
  const csiCsv = CsiRecorder.buildCsiDataCsv(frames, { label: "duduk", takeSeq: 1 });
  report("CSI_DATA header matches console_test", csiCsv.startsWith(CsiRecorder.CSI_DATA_HEADER + "\n"));
  report("CSI_DATA row tagged", csiCsv.includes("CSI_DATA,1,100,1,duduk,aa:bb:cc:dd:ee:ff"));

  const iqCsv = CsiRecorder.buildIqCsv(frames);
  const headerCols = iqCsv.split("\n")[0].split(",");
  report("I/Q columns are 2 per subcarrier", headerCols.filter((name) => name.startsWith("sc")).length === 4);

  const parsed = CsiRecorder.parseIqCsv(iqCsv);
  report("parseIqCsv roundtrip", parsed.subcarriers === 2 && parsed.frames[0].iq[1][1] === 4);

  const heat = CsiRecorder.downsampleHeatmap(parsed.frames, 400);
  report("heatmap amplitude", heat.length === 1 && heat[0].length === 2 && Math.abs(heat[0][0] - Math.hypot(1, 2)) < 1e-9);

  const incomplete = CsiRecorder.recordingCompleteness({
    frames: [],
    droppedStart: 0,
    droppedEnd: 0,
    disconnected: false,
    stimulusOn: true,
  });
  report("zero frames incomplete", incomplete.complete === false);

  const dropped = CsiRecorder.recordingCompleteness({
    frames: frames,
    droppedStart: 1,
    droppedEnd: 5,
    disconnected: false,
    stimulusOn: true,
  });
  report("dropped delta incomplete", dropped.complete === false && dropped.dropped_delta === 4);

  const ok = CsiRecorder.recordingCompleteness({
    frames: frames,
    droppedStart: 2,
    droppedEnd: 2,
    disconnected: false,
    stimulusOn: true,
  });
  report("clean take complete", ok.complete === true);

  const id = CsiRecorder.makeRecordingId("duduk", new Date("2026-10-22T01:45:32.000Z"), 1);
  report("recording id shape", id === "20261022T014532Z_duduk_001");

  if (process.exitCode) {
    console.error(`GAGAL: ${path.basename(__filename)}`);
  }
}

main();
