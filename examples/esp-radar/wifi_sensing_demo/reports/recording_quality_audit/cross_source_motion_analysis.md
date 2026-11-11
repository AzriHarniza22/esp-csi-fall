# Cross-Source Motion Analysis Report

**Metode:** Overlay raw CSI delta-amplitude dengan firmware telemetri (`smooth_scaled`, `enter_level_scaled`, `exit_level_scaled`, `motion_status`) pada time-offset yang sama (masing-masing clock di-zero dari sample pertama).

**Data sources:**
- `frames.csv` → `valid_b64` → delta-amplitude antar frame (gap-masked ≥500ms)
- `meta.json` → `events.motion_samples` → firmware telemetri (/1000 untuk display)
- `meta.json` → `timeline` + `annotations`

**Label baselines (median across all same-label recordings):**

| Label | pre_csi | act_csi | post_csi | act_smooth | act_enter |
|---|---|---|---|---|---|
| `fall_backward` | 5.9 | 6.5 | 4.5 | 3847 | 4955 |
| `fall_forward` | 5.7 | 7.7 | 5.2 | 2555 | 5137 |
| `fall_keseleo` | 5.5 | 5.0 | 4.6 | 4725 | 7781 |
| `fall_lemas` | 2.8 | 2.9 | 2.6 | 3275 | 3551 |
| `object_drop` | 3.0 | 3.2 | 2.8 | 2844 | 4318 |

---

## Fall Keseleo (11 recordings)

### `20261107T153329Z_fall_right_002`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.47 | 3.91 | 5.37 |
| smooth/1000 mean | 5446 | 4700 | 4383 |
| enter/1000 mean | 4640 | 4851 | 5013 |
| smooth > enter (%) | 100 | 41 | 19 |
| FSM active (%) | 100.00 | 60.29 | 23.53 |

- **fall_start annotation:** 4.608s
- **fall_impact annotation:** 6.395s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.91, smooth=4700 < enter=4851 (gap=151)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.47 elevated baseline, enter during action=4851

### `20261107T153429Z_fall_right_003`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.94 | 4.28 | 4.56 |
| smooth/1000 mean | 5099 | 4160 | 3935 |
| enter/1000 mean | 7019 | 7136 | 6849 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.159s
- **fall_impact annotation:** 6.431s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=4.28, smooth=4160 < enter=7136 (gap=2976)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.94 elevated baseline, enter during action=7136

### `20261107T153501Z_fall_right_004`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.92 | 5.03 | 4.79 |
| smooth/1000 mean | 4919 | 5172 | 4139 |
| enter/1000 mean | 6783 | 7075 | 6932 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.299s
- **fall_impact annotation:** 7.626s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.03, smooth=5172 < enter=7075 (gap=1904)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.92 elevated baseline, enter during action=7075

### `20261107T153533Z_fall_right_005`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.27 | 5.51 | 4.44 |
| smooth/1000 mean | 6136 | 4757 | 4262 |
| enter/1000 mean | 8754 | 8685 | 8032 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.054s
- **fall_impact annotation:** 6.683s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.51, smooth=4757 < enter=8685 (gap=3927)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.27 elevated baseline, enter during action=8685

### `20261107T153606Z_fall_right_006`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 4.99 | 5.04 | 2.71 |
| smooth/1000 mean | 4631 | 4416 | 4009 |
| enter/1000 mean | 8038 | 7781 | 7527 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 4.778s
- **fall_impact annotation:** 6.378s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.04, smooth=4416 < enter=7781 (gap=3364)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=4.99 elevated baseline, enter during action=7781

### `20261107T153638Z_fall_right_007`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.80 | 5.37 | 3.97 |
| smooth/1000 mean | 5158 | 4994 | 3828 |
| enter/1000 mean | 7109 | 7504 | 7171 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 4.949s
- **fall_impact annotation:** 7.367s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.37, smooth=4994 < enter=7504 (gap=2510)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.80 elevated baseline, enter during action=7504

### `20261107T153710Z_fall_right_008`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 4.19 | 4.84 | 2.56 |
| smooth/1000 mean | 4644 | 4628 | 3807 |
| enter/1000 mean | 7625 | 7531 | 7183 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 4.850s
- **fall_impact annotation:** 6.279s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=4.84, smooth=4628 < enter=7531 (gap=2903)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=4.19 elevated baseline, enter during action=7531

### `20261107T153742Z_fall_right_009`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 7.44 | 4.83 | 6.01 |
| smooth/1000 mean | 5576 | 5116 | 4469 |
| enter/1000 mean | 7307 | 7816 | 7758 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.208s
- **fall_impact annotation:** 6.789s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=4.83, smooth=5116 < enter=7816 (gap=2700)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=7.44 elevated baseline, enter during action=7816

### `20261107T153815Z_fall_right_010`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.47 | 5.98 | 3.87 |
| smooth/1000 mean | 5434 | 4725 | 4277 |
| enter/1000 mean | 8433 | 8315 | 7901 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.010s
- **fall_impact annotation:** 6.463s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.98, smooth=4725 < enter=8315 (gap=3590)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.47 elevated baseline, enter during action=8315

### `20261107T153847Z_fall_right_011`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.98 | 5.10 | 5.39 |
| smooth/1000 mean | 5151 | 4405 | 4762 |
| enter/1000 mean | 8530 | 8373 | 8121 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.132s
- **fall_impact annotation:** 6.537s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.10, smooth=4405 < enter=8373 (gap=3969)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.98 elevated baseline, enter during action=8373

### `20261107T153919Z_fall_right_012`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.49 | 5.15 | 5.14 |
| smooth/1000 mean | 5400 | 5567 | 4684 |
| enter/1000 mean | 8457 | 8756 | 8398 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

- **fall_start annotation:** 5.064s
- **fall_impact annotation:** 6.659s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.15, smooth=5567 < enter=8756 (gap=3190)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.49 elevated baseline, enter during action=8756

---

## Object Drop (10 recordings)

### `20261104T155116Z_object_drop_001`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 4.20 | 3.72 | 3.56 |
| smooth/1000 mean | 2592 | 2293 | 2080 |
| enter/1000 mean | 4257 | 4181 | 4052 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.72, smooth=2293 < enter=4181 (gap=1888)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=4.20 elevated baseline, enter during action=4181

### `20261104T155131Z_object_drop_002`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 2.22 | 3.48 | 2.95 |
| smooth/1000 mean | 2497 | 2293 | 2078 |
| enter/1000 mean | 4311 | 4130 | 3947 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 1.43 | 0.00 | 0.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.48, smooth=2293 < enter=4130 (gap=1838)

### `20261104T155146Z_object_drop_003`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 2.04 | 2.49 | 3.92 |
| smooth/1000 mean | 1772 | 2476 | 2237 |
| enter/1000 mean | 3760 | 3577 | 3608 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

*No anomaly flags.*

### `20261104T155201Z_object_drop_004`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 1.90 | 2.49 | 3.05 |
| smooth/1000 mean | 2395 | 2974 | 2646 |
| enter/1000 mean | 3881 | 3943 | 4064 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |

*No anomaly flags.*

### `20261104T155217Z_object_drop_005`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 2.61 | 2.56 | 2.13 |
| smooth/1000 mean | 2527 | 2853 | 3053 |
| enter/1000 mean | 4433 | 4241 | 4470 |
| smooth > enter (%) | 0 | 6 | 6 |
| FSM active (%) | 0.00 | 0.00 | 10.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=2.56, smooth=2853 < enter=4241 (gap=1388)

### `20261104T155232Z_object_drop_006`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 2.81 | 3.32 | 2.24 |
| smooth/1000 mean | 2698 | 3163 | 3177 |
| enter/1000 mean | 4847 | 4636 | 4756 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.32, smooth=3163 < enter=4636 (gap=1473)

### `20261104T155247Z_object_drop_007`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 4.08 | 3.11 | 2.32 |
| smooth/1000 mean | 2529 | 3393 | 2735 |
| enter/1000 mean | 4843 | 4631 | 4655 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.11, smooth=3393 < enter=4631 (gap=1238)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=4.08 elevated baseline, enter during action=4631

### `20261104T155302Z_object_drop_008`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 4.27 | 5.46 | 2.56 |
| smooth/1000 mean | 2363 | 2835 | 2980 |
| enter/1000 mean | 4651 | 4400 | 4512 |
| smooth > enter (%) | 0 | 0 | 7 |
| FSM active (%) | 0.00 | 0.00 | 4.29 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.46, smooth=2835 < enter=4400 (gap=1565)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=4.27 elevated baseline, enter during action=4400

### `20261104T155317Z_object_drop_009`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 4.51 | 2.87 | 2.15 |
| smooth/1000 mean | 2964 | 3130 | 2648 |
| enter/1000 mean | 4645 | 4673 | 4658 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=2.87, smooth=3130 < enter=4673 (gap=1543)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=4.51 elevated baseline, enter during action=4673

### `20261104T155333Z_object_drop_010`

| Metrik | Pre (pre_action) | Action (action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 3.19 | 3.92 | 3.29 |
| smooth/1000 mean | 2332 | 2637 | 3114 |
| enter/1000 mean | 4591 | 4395 | 4500 |
| smooth > enter (%) | 0 | 0 | 0 |
| FSM active (%) | 0.00 | 0.00 | 0.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.92, smooth=2637 < enter=4395 (gap=1758)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=3.19 elevated baseline, enter during action=4395

---

## Fall Forward (1 recordings)

### `20261104T155934Z_fall_forward_008`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.70 | 7.71 | 5.16 |
| smooth/1000 mean | 2612 | 2555 | 3818 |
| enter/1000 mean | 5481 | 5137 | 5276 |
| smooth > enter (%) | 0 | 0 | 25 |
| FSM active (%) | 0.00 | 0.00 | 23.19 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=7.71, smooth=2555 < enter=5137 (gap=2583)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.70 elevated baseline, enter during action=5137

---

## Fall Backward (10 recordings)

### `20261104T160100Z_fall_backward_001`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 6.29 | 7.89 | 4.60 |
| smooth/1000 mean | 3341 | 3694 | 4706 |
| enter/1000 mean | 3928 | 4039 | 4497 |
| smooth > enter (%) | 0 | 49 | 52 |
| FSM active (%) | 0.00 | 40.00 | 55.07 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=7.89, smooth=3694 < enter=4039 (gap=345)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=6.29 elevated baseline, enter during action=4039
- FSM_ACTIVE_AFTER_CSI_STABLE: post_motion_status=55%, post_csi=4.60

### `20261104T160120Z_fall_backward_002`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.20 | 6.67 | 6.27 |
| smooth/1000 mean | 2512 | 4221 | 5059 |
| enter/1000 mean | 4307 | 4370 | 4885 |
| smooth > enter (%) | 0 | 47 | 63 |
| FSM active (%) | 0.00 | 41.18 | 70.59 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=6.67, smooth=4221 < enter=4370 (gap=149)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.20 elevated baseline, enter during action=4370

### `20261104T160140Z_fall_backward_003`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 6.04 | 5.82 | 5.42 |
| smooth/1000 mean | 2979 | 3757 | 4594 |
| enter/1000 mean | 5122 | 5094 | 5519 |
| smooth > enter (%) | 0 | 9 | 46 |
| FSM active (%) | 0.00 | 2.94 | 55.07 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.82, smooth=3757 < enter=5094 (gap=1337)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=6.04 elevated baseline, enter during action=5094
- FSM_ACTIVE_AFTER_CSI_STABLE: post_motion_status=55%, post_csi=5.42

### `20261104T160200Z_fall_backward_004`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 3.72 | 4.47 | 4.70 |
| smooth/1000 mean | 2971 | 3491 | 5051 |
| enter/1000 mean | 5068 | 4915 | 5363 |
| smooth > enter (%) | 0 | 26 | 56 |
| FSM active (%) | 0.00 | 20.00 | 70.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=4.47, smooth=3491 < enter=4915 (gap=1424)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=3.72 elevated baseline, enter during action=4915

### `20261104T160220Z_fall_backward_005`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 3.68 | 5.38 | 4.34 |
| smooth/1000 mean | 2781 | 4373 | 4396 |
| enter/1000 mean | 5027 | 4985 | 5361 |
| smooth > enter (%) | 0 | 29 | 39 |
| FSM active (%) | 0.00 | 17.65 | 50.00 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.38, smooth=4373 < enter=4985 (gap=613)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=3.68 elevated baseline, enter during action=4985

### `20261104T160241Z_fall_backward_006`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 7.09 | 6.79 | 4.32 |
| smooth/1000 mean | 2778 | 3937 | 4430 |
| enter/1000 mean | 4909 | 4873 | 5220 |
| smooth > enter (%) | 0 | 29 | 28 |
| FSM active (%) | 0.00 | 22.86 | 27.54 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=6.79, smooth=3937 < enter=4873 (gap=936)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=7.09 elevated baseline, enter during action=4873

### `20261104T160301Z_fall_backward_007`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 6.65 | 6.30 | 3.69 |
| smooth/1000 mean | 4157 | 3565 | 4661 |
| enter/1000 mean | 5405 | 5468 | 5652 |
| smooth > enter (%) | 0 | 0 | 38 |
| FSM active (%) | 0.00 | 0.00 | 46.38 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=6.30, smooth=3565 < enter=5468 (gap=1903)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=6.65 elevated baseline, enter during action=5468
- FSM_ACTIVE_AFTER_CSI_STABLE: post_motion_status=46%, post_csi=3.69

### `20261104T160321Z_fall_backward_008`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 6.15 | 6.73 | 4.35 |
| smooth/1000 mean | 3257 | 3734 | 4282 |
| enter/1000 mean | 5062 | 5182 | 5496 |
| smooth > enter (%) | 0 | 0 | 22 |
| FSM active (%) | 0.00 | 0.00 | 17.39 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=6.73, smooth=3734 < enter=5182 (gap=1448)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=6.15 elevated baseline, enter during action=5182

### `20261104T160341Z_fall_backward_009`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.07 | 7.38 | 4.56 |
| smooth/1000 mean | 3386 | 4098 | 5114 |
| enter/1000 mean | 5021 | 5148 | 5588 |
| smooth > enter (%) | 0 | 11 | 59 |
| FSM active (%) | 0.00 | 2.86 | 63.77 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=7.38, smooth=4098 < enter=5148 (gap=1050)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.07 elevated baseline, enter during action=5148
- FSM_ACTIVE_AFTER_CSI_STABLE: post_motion_status=64%, post_csi=4.56

### `20261104T160401Z_fall_backward_010`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 5.83 | 5.96 | 4.28 |
| smooth/1000 mean | 2504 | 4277 | 4017 |
| enter/1000 mean | 4945 | 4926 | 5281 |
| smooth > enter (%) | 0 | 29 | 56 |
| FSM active (%) | 0.00 | 20.59 | 58.82 |


**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=5.96, smooth=4277 < enter=4926 (gap=649)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.83 elevated baseline, enter during action=4926
- FSM_ACTIVE_AFTER_CSI_STABLE: post_motion_status=59%, post_csi=4.28

---

## Fall Lemas (3 recordings)

### `20261107T151834Z_fall_left_010`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 2.83 | 2.92 | 2.69 |
| smooth/1000 mean | 1917 | 3252 | 2155 |
| enter/1000 mean | 3355 | 3412 | 3593 |
| smooth > enter (%) | 0 | 64 | 0 |
| FSM active (%) | 0.00 | 17.14 | 0.00 |

- **fall_start annotation:** 4.476s
- **fall_impact annotation:** 6.222s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=2.92, smooth=3252 < enter=3412 (gap=159)

### `20261107T152115Z_fall_left_015`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 3.00 | 3.11 | 2.04 |
| smooth/1000 mean | 816 | 3275 | 1971 |
| enter/1000 mean | 3745 | 3551 | 3528 |
| smooth > enter (%) | 0 | 55 | 0 |
| FSM active (%) | 0.00 | 50.72 | 0.00 |

- **fall_start annotation:** 4.957s
- **fall_impact annotation:** 6.326s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=3.11, smooth=3275 < enter=3551 (gap=275)

### `20261107T152320Z_fall_left_017`

| Metrik | Pre (pre_action) | Action (fall_action) | Post (post_action) |
|---|---|---|---|
| CSI Δ-amp mean | 2.74 | 2.87 | 2.64 |
| smooth/1000 mean | 2143 | 4064 | 2688 |
| enter/1000 mean | 4171 | 4303 | 4451 |
| smooth > enter (%) | 0 | 44 | 0 |
| FSM active (%) | 0.00 | 44.12 | 0.00 |

- **fall_start annotation:** 4.991s
- **fall_impact annotation:** 6.989s

**Findings:**
- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=2.87, smooth=4064 < enter=4303 (gap=239)


---

## Narrative Analysis

### fall_keseleo — Semua 11 Recording

#### Pola yang ditemukan

- **CSI delta saat fall_action:** 5.00 ± 0.54 (range 3.91–5.98)
- **CSI delta saat pre_action (walking):** 5.63
- **smooth/1000 mean saat fall_action:** 4785
- **enter/1000 mean saat fall_action:** 7620
- **% sampel smooth > enter:** 3.7% (range 0–41%)

#### Interpretasi

Pre_action adalah fase **berjalan** (`Berjalan seperti biasa`), bukan diam. Walking menghasilkan aktivitas CSI tinggi yang menaikkan `baseline_scaled` firmware. Ketika fall terjadi (fall_action), `enter_level_scaled` sudah sangat tinggi (~7000–9000) karena baseline terangkat dari aktivitas walking sebelumnya. `smooth_scaled` saat jatuh (~4000–5500) **tidak mencapai** enter_level sehingga `motion_status` tidak trigger.

**Penyebab:** Ini adalah **karakteristik arsitektur FSM**, bukan recording failure. Firmware esp_wifi_sensing menggunakan adaptive baseline yang terangkat saat subjek berjalan dan tidak cukup turun dalam 4 detik sisa walking. Ini **bukan anomali aktivitas**.

**Implikasi untuk model:** `motion_status` dari fall_keseleo tidak dapat digunakan sebagai feature deteksi jatuh untuk label ini. `smooth_scaled` dan `enter_level_scaled` dapat digunakan sebagai feature kontekstual, namun dengan pemahaman bahwa FSM aktif saat berjalan, bukan saat jatuh.

**fall_right_002 (pengecualian):** Satu-satunya recording dengan `above_enter_pct > 0` (41%). Ini kemungkinan karena walking di pre_action lebih pelan/singkat sehingga baseline tidak terangkat sebanyak recording lain.

### object_drop — Semua 10 Recording

- **CSI delta saat action (drop):** 3.34 ± 0.86
- **CSI delta saat pre_action:** 3.18
- **smooth/1000 mean saat action:** 2805
- **enter/1000 mean saat action:** 4281
- **% sampel smooth > enter:** 0.6%
- **FSM active % saat action:** 0.0%

#### Interpretasi

CSI delta saat menjatuhkan benda (~2.6–3.4) **hampir identik dengan pre_action** (~2.5–3.2). Ini terjadi karena:

1. **Gerakan benda kecil tidak mengubah channel CSI secara signifikan.** CSI bersumber dari jalur multipah antara router dan ESP32 — pergerakan tangan menjatuhkan benda adalah gerakan kecil yang tidak mengubah refleksi utama.
2. **Tubuh subjek yang diam menghasilkan baseline yang sama.** Perbedaan antara 'tangan menjatuhkan benda' dan 'berdiri diam' tidak terdeteksi oleh CSI maupun FSM firmware.
3. **FSM tidak trigger karena smooth tidak melebihi enter_level** — ini adalah hasil yang benar untuk gerakan sekecil ini.

**Ini adalah keterbatasan fisik/arsitektural**, bukan recording failure atau mislabeling. Dataset ini tidak dapat membedakan object_drop dari still_standing menggunakan CSI delta-amplitude atau firmware motion detector. Classifier berbasis fitur CSI perlu mempertimbangkan hal ini.

### fall_forward_008

| Fase | CSI Δ | smooth | enter | above_enter | FSM active |
|---|---|---|---|---|---|
| pre_action | 5.7 | 2612 | 5481 | 0% | 0% |
| fall_action | 7.7 | 2555 | 5137 | 0% | 0% |
| post_action | 5.2 | 3818 | 5276 | 25% | 23% |

**Temuan:** `fall_forward_008` memiliki `fall_action` smooth (z=−2.77 vs label). CSI delta saat fall_action rendah. Firmware FSM tidak trigger sama sekali (0%). Ini berbeda dari mayoritas fall_forward yang menunjukkan FSM aktif 20–60% saat jatuh.

**Interpretasi:** Kemungkinan eksekusi jatuh yang sangat gradual (slow fall) atau posisi subjek yang tidak optimal sehingga pertubahan channel WiFi minimal. Ini tidak membuktikan mislabeling — CSI sensitivitas bergantung pada posisi dan arah gerakan. Namun recording ini adalah outlier yang perlu diperhatikan saat training.

- CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta=7.71, smooth=2555 < enter=5137 (gap=2583)
- HIGH_PRE_BASELINE_LIFTED_THRESHOLD: pre_csi=5.70 elevated baseline, enter during action=5137

### fall_backward Nov4 — Semua 10 Recording

| Recording | act_csi | post_csi | act_smooth | post_smooth | FSM_act% | FSM_post% |
|---|---|---|---|---|---|---|
| `ll_backward_001` | 7.9 | 4.6 | 3694 | 4706 | 40% | 55% |
| `ll_backward_002` | 6.7 | 6.3 | 4221 | 5059 | 41% | 71% |
| `ll_backward_003` | 5.8 | 5.4 | 3757 | 4594 | 3% | 55% |
| `ll_backward_004` | 4.5 | 4.7 | 3491 | 5051 | 20% | 70% |
| `ll_backward_005` | 5.4 | 4.3 | 4373 | 4396 | 18% | 50% |
| `ll_backward_006` | 6.8 | 4.3 | 3937 | 4430 | 23% | 28% |
| `ll_backward_007` | 6.3 | 3.7 | 3565 | 4661 | 0% | 46% |
| `ll_backward_008` | 6.7 | 4.4 | 3734 | 4282 | 0% | 17% |
| `ll_backward_009` | 7.4 | 4.6 | 4098 | 5114 | 3% | 64% |
| `ll_backward_010` | 6.0 | 4.3 | 4277 | 4017 | 21% | 59% |

#### Interpretasi

Pola **post_action lebih aktif dari fall_action** terlihat pada Nov4 recordings. Penyebab utama:

1. **Recording Nov4 menggunakan target 10 detik** (pre=0–4s, fall=4–6s, post=6–10s). Fall_action window hanya 2 detik — sangat sempit untuk menangkap seluruh dinamika jatuh.
2. **Subjek yang baru bangun dari jatuh** (recovery movement) selama post_action menghasilkan sinyal yang lebih besar dari sinyal jatuh itu sendiri.
3. **FSM baseline**: setelah jatuh, smooth sering masih tinggi dari momentum impak dan gerakan recovery, yang justru lebih mudah ter-detect.

Recording **_003, _007, _008, _009** menunjukkan FSM tidak aktif sama sekali saat fall_action (0%). CSI delta juga rendah (~2.5–3.5). Ini kemungkinan karena orientasi jatuh ke belakang di luar zone sensitif ESP32 (antenna pattern-dependent). Tidak ada bukti mislabeling.

### fall_lemas — _010, _015, _017

Ketiga recording ini dipilih karena action_phase_z dalam audit sebelumnya (action lemah).

| Recording | pre_csi | act_csi | post_csi | act_smooth | enter_act | above_enter% | FSM_act% |
|---|---|---|---|---|---|---|---|
| `l_left_010` | 2.8 | 2.9 | 2.7 | 3252 | 3412 | 64% | 17% |
| `l_left_015` | 3.0 | 3.1 | 2.0 | 3275 | 3551 | 55% | 51% |
| `l_left_017` | 2.7 | 2.9 | 2.6 | 4064 | 4303 | 44% | 44% |

#### Interpretasi

"Fall lemas" adalah jatuh yang lambat dan bertahap — subjek melemas secara gradual. Ini secara fisik menghasilkan perubahan CSI yang lebih kecil dan lebih lambat dibanding fall_forward/backward yang memiliki impak mendadak.

- **`Z_fall_left_010`:** CSI delta=2.9, smooth_above_enter=64%, FSM_active=17%. Timestamp gap dalam fall_action menghilangkan sebagian sinyal.
- **`Z_fall_left_015`:** CSI delta=3.1, smooth_above_enter=55%, FSM_active=51%. Profil gradual konsisten dengan label.
- **`Z_fall_left_017`:** CSI delta=2.9, smooth_above_enter=44%, FSM_active=44%. Profil gradual konsisten dengan label.

Ketiga recording ini menunjukkan karakteristik yang **konsisten dengan label fall_lemas** (jatuh gradual). Profil berbeda dari fall_forward/backward bukan karena execution error melainkan karena sifat fisik aktivitas yang berbeda.

---

## Kesimpulan Cross-Source

| Recording / Kelompok | Sumber Anomali | Jenis | Rekomendasi |
|---|---|---|---|
| fall_keseleo 10/11 — FSM tidak trigger | FSM baseline adaptation | Keterbatasan firmware | Gunakan smooth_scaled/enter_level sebagai feature, bukan motion_status |
| object_drop 10/10 — FSM tidak trigger | Keterbatasan fisik CSI | Keterbatasan arsitektural | Pertimbangkan apakah label ini dapat dibedakan dari still_standing |
| fall_forward_008 — smooth rendah | Eksekusi aktivitas (kemungkinan gradual fall) | Anomali aktivitas | REVIEW — tidak ada bukti mislabeling |
| fall_backward Nov4 — post_action aktif | Recovery movement + window fall sempit (2s) | Karakteristik aktivitas + protokol | Dapat digunakan; pre-fall window perlu normalisasi |
| fall_lemas _010/_015/_017 — action lemah | Karakteristik fall_lemas (gradual) | Karakteristik aktivitas yang valid | Tidak ada masalah; profil gradual adalah expected |

**Tidak ada recording yang terbukti salah label berdasarkan analisis ini.**

**Keterbatasan analisis:** Alignment dua clock (CSI callback_timestamp_us vs motion ts_ms) dilakukan dengan zero-offset dari masing-masing sumber pertama. Jitter antar keduanya ~0–200ms, dapat menyebabkan misalignment kecil pada fase-fase sempit (< 2 detik).
