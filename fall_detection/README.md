# CSI fall-detection experiment

This folder starts the offline dataset-validation stage. It does not change the
ESP32 firmware or claim to detect falls. Inference/training must wait until
there are enough complete, correctly labeled recordings to create a
session-aware train/validation/test split.

## Audit existing recordings

From the repository root:

```bash
python3 fall_detection/audit_dataset.py
python3 fall_detection/audit_dataset.py --json
python3 -m unittest discover -s fall_detection/tests -v
```

Pass another recordings directory as the positional argument to audit a
different dataset. The tool uses only the Python standard library.

An eligible take must have a complete metadata record, a non-empty label,
positive frame and subcarrier counts, and a matching I/Q CSV with one
well-formed row per metadata frame. Eligibility is structural only: it does not
certify that the label is correct, that the take is representative, or that
there is enough data to train a useful model.

Labels are not inferred from activity names or folder names. In particular,
the audit must not relabel arbitrary existing takes as `fall` or `normal`.

## Current collection gate

The existing `kosong` recording is structurally complete (198 frames and 164
subcarriers). The `tes` recording is incomplete and has no CSI subcarriers.
There are no verified fall-labeled takes, so supervised training is blocked.
Collect additional data only with a documented, safe, supervised protocol;
this prototype is not a safety or medical device.

## Next stages

1. Define a safe collection protocol and consistent labels/session metadata.
2. Collect and audit normal activities and supervised fall simulations,
   including activities that may resemble a fall.
3. Build an offline feature pipeline and compare Random Forest with Gradient
   Boosting using splits grouped by session/person.
4. Evaluate recall, precision, false alarms per monitoring time, missed falls,
   and latency; use validation data to select models and thresholds.
5. Only then test temporal confirmation and real-time inference.
