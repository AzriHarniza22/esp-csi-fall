# CSI recordings

Dataset takes written by `tools/csi_recorder_server.py` from the CSI Recorder
panel in `tools/web_serial_monitor.html`.

Each take is a folder named after the sanitised label, with three files:

- `*.csi_data.csv` — header matching esp-radar `console_test` `CSI_DATA` rows
- `*.iq.csv` — one row per frame, I/Q columns per subcarrier
- `*.meta.json` — label, countdown, duration, frame count, completeness

`index.csv` lists every take. CSV payloads are gitignored; keep this README.
