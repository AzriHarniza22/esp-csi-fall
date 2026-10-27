# CSI recordings

Dataset takes written by `tools/csi_recorder_server.py` from the CSI Recorder
panel in `tools/web_serial_monitor.html`.

Each take is a folder named after the sanitised label, with three files:

- `*.csi_data.csv` — header matching esp-radar `console_test` `CSI_DATA` rows
- `*.iq.csv` — one row per frame, I/Q columns per subcarrier
- `*.meta.json` — label, countdown, duration, batch ID, inter-take gap,
  frame count, completeness, and `motion_samples` (ESP motion-detector
  telemetry captured during the take)

The Motion graph plots the ESP-reported `smooth_scaled`, enter/exit thresholds,
and active/inactive state. Recordings created before this telemetry was added
do not contain `motion_samples`; re-record them to see this graph. These are
device detector outputs, not motion values reconstructed from CSI.

## Collecting repeated activity takes

The recorder can capture 1–100 consecutive, fixed-duration takes under one
label. Set `Gap between takes (s)` to `0` for continuous acquisition; each
segment is still saved as its own take. Uploads happen while CSI capture
continues, and the library refreshes after the batch. A nonzero gap is useful
when the person needs time to reset pose.

Suggested starting procedure for an activity transition:

1. Use one person and one label for the whole batch. Choose action labels that
   describe the movement, not only the final pose: `berdiri diam`, `berjalan`,
   `duduk` (standing-to-sitting), `jongkok` (standing-to-squat),
   `duduk lalu berdiri`, or `mengayunkan tangan sekali`.
2. Start with 8 seconds per take as an initial collection setting, not an
   established optimum. Keep still in the starting pose briefly, perform one
   action during the middle of each take, and hold the ending pose briefly.
   With gap 0, return to the starting pose before that take ends so the next
   take begins ready. If this is uncomfortable or too rushed, set a gap and
   reset during it.
3. Begin with 10 takes to check positioning and labels. A batch of 100 takes
   at 8 seconds is 13 minutes 20 seconds of capture with no inter-take gaps;
   do not force repetitive movements if tired. Prefer several batches and
   sessions over treating 100 adjacent takes as 100 independent experiments.
4. For every class, collect several separate sessions. Change only one
   condition at a time (for example, distance or body orientation), and record
   session/subject/room details in notes. Keep entire takes or sessions out of
   training when evaluating; do not randomly split overlapping windows.

`jatuh` recordings are not part of a validated safety system. Do not attempt
falls alone or ask a vulnerable person to perform them. Any fall data
collection requires an appropriate supervised research safety protocol;
otherwise use an existing dataset and treat device results as experimental.

`index.csv` lists every take. CSV payloads are gitignored; keep this README.
