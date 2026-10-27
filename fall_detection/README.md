# CSI activity-classification experiment

This folder contains an offline dataset audit and an explicitly experimental
activity-model trainer. The model recognizes labeled activity windows; for
example, `duduk` means the transition from standing to sitting, not a static
sitting pose. It does not detect falls.

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

## Train and export an ESP32 demonstration model

From the repository root:

```bash
python3 fall_detection/train_activity_model.py --algorithm nearest-centroid \
  --class 'berdiri diam=berdiri diam' \
  --class 'berjalan=berjalan' \
  --class 'berdiri ke duduk=duduk' \
  --class 'berdiri ke jongkok=jongkok' \
  --class 'duduk ke berdiri=duduk lalu berdiri' \
  --class 'ayunkan tangan=mengayunkan tangan sekali'
```

Choose `--algorithm` from `nearest-centroid`, `logistic-regression`,
`linear-svm`, `decision-tree`, or `random-forest`. Each run writes only that
model's parameters to
`examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`; then build
and flash the ESP-IDF v5.5.3 project to switch the standalone firmware model.
The same CSI parser, feature extractor, labels, and output interface are used
for every algorithm. Tree depth is limited to 4, and the random forest has 9
trees, to keep these initial embedded candidates small.

To compare all candidates with one command, use `--algorithm all` and provide
held-out take IDs for every class. The command reports the same grouped metrics
for each algorithm and writes separate headers such as
`activity_model_data_random_forest.h`; copy the chosen header over
`activity_model_data.h` before building and flashing:

```bash
python3 fall_detection/train_activity_model.py --algorithm all \
  --test-take TAKE_ID_FOR_CLASS_1 \
  --test-take TAKE_ID_FOR_CLASS_2 \
  --class 'berdiri diam=berdiri diam' \
  --class 'berjalan=berjalan'
```

Replace the example take IDs with actual recording IDs from repeated sessions.
The test takes must cover every output class, and separate training takes must
remain for each class. If those conditions are not met, the command stops
instead of reporting a misleading comparison.

For an honest offline comparison, collect repeated takes per class and hold
out complete take IDs, not overlapping windows:

```bash
python3 fall_detection/train_activity_model.py --algorithm random-forest \
  --test-take 20261023T151024Z_berjalan_001 \
  --class 'berdiri diam=berdiri diam' \
  --class 'berjalan=berjalan' \
  --class 'duduk=duduk' \
  --class 'jongkok=jongkok'
```

Repeat `--test-take` for additional held-out takes. At least one complete
training take per output class must remain. The tool reports accuracy,
per-class precision/recall/F1, and macro-F1 on the held-out takes; these
metrics are not meaningful if the held-out takes do not represent the intended
deployment conditions. Training exports from the remaining training takes.
Use identical class mappings and test-take IDs when comparing algorithms.

The trainer and firmware use the first 104 bytes of `valid_data`, which the
locked `esp-radar` 0.3.4 ESP32 table identifies as the 52-complex-sample LLTF
field for the supported 20 MHz, primary-channel-only packet layouts. The
trainer accepts non-HT/no-STBC frames (104 bytes), HT/no-STBC frames (216
bytes), and HT/STBC frames (328 bytes); it rejects other packet layouts rather
than treating concatenated LLTF/HT-LTF/STBC-HT-LTF data as one CSI spectrum.
The embedded callback also checks the LLTF length and packet metadata before
copying samples to its queue.

All candidates compute 16 log amplitude-change bands over a 24-frame window,
with a 12-frame stride. The selected classifier runs on the ESP32 in a
lower-priority FreeRTOS task. Its model-specific score is only used to rank
classes; it is not a probability or calibrated confidence. The CSI callback
only copies supported frames to a bounded queue.

## Data limitations

The current recording set has one complete take for each of seven activity
classes:
`kosong`, `berdiri diam`, `berjalan`, `duduk` (standing to sitting), `jongkok`
(standing to squatting), `duduk lalu berdiri`, and `mengayunkan tangan sekali`.
The empty-room take has 475 frames; the other takes have 142–162 frames. Their
majority packet layout is HT/STBC, 20 MHz, primary channel, 328-byte CSI; the
shared LLTF segment is used. Some activity takes also contain a few non-HT
frames, which contribute their supported LLTF segment. There is one session
per class; take-level action labels cover pre-action and post-action frames, so
overlapping windows are weakly labeled and correlated. This is enough to exercise the end-to-end training/export/inference path, not
to claim useful accuracy or generalization. With one take per class, there is
not enough data to both train and hold out complete takes for a valid
comparison. Collect repeated sessions and hold out entire takes before
relying on any class output.

The older `tes` recording is incomplete and has no CSI subcarriers. There are
no verified fall-labeled takes; no fall model has been trained. This trainer
currently supports the activity classes supplied by recordings, not a
validated fall detector. Do not use this classifier as a safety feature.

## Next stages

1. Record multiple labeled takes per activity, with a consistent start pose
   and action timing; add harmless confounding activities.
2. Evaluate on complete takes/sessions not used for training before calling
   the classifier useful. Report per-class precision/recall, macro-F1,
   confusion matrix, false classifications per time, and action-to-result
   latency.
3. Define a safe supervised protocol before collecting any fall simulations.
4. For future fall work, compare models with participant/session-grouped splits
   and report recall, false alarms per monitoring time, missed falls, and
   latency.
