# Pipeline training berbasis fase

Pipeline ini adalah jalur eksperimen offline terpisah dari trainer berlabel
take dan firmware. Ia memakai reader CSI serta `extract_window_features` yang
sama dengan trainer kanonik: 24 frame per window, stride 12, 16 fitur.
Standardisasi dan fit dijalankan ulang pada data training di setiap fold lewat
`classifier_models.fit_classifier`; window dari grup test tidak ikut menghitung
parameter standardisasi.

## Aturan label

Policy contoh ada di `fall_detection/phase_label_policy.json`.

- Kelas keluaran biner berurutan `fall`, `non_fall`.
- Window aktivitas normal diberi `non_fall` hanya jika seluruh rentang
  timestamp frame yang dipakai berada di dalam fase timeline yang dipetakan.
- Pada policy terbaru, rekaman jatuh memakai window `non_fall` yang seluruhnya
  berada di fase `pre_action`; window `fall` dimulai pada offset rekaman 4 detik
  (clock anchor/timeline) dan berlanjut sampai window terakhir yang lengkap
  sebelum frame CSI valid terakhir. Anotasi `fall_start`/`fall_impact` tidak
  lagi membatasi target kelas ini. Window yang memotong batas 4 detik tetap
  tidak berlabel.
- Window yang melintasi batas fase, tidak punya label, atau tidak memenuhi
  aturan ekor rekaman dilewati. Jika sebuah window cocok dengan dua kelas
  berbeda, pipeline berhenti dengan error, bukan memilih label diam-diam.

Waktu fase terjadwal diturunkan dari `started_at_utc` dan `clock_anchor`, lalu
dibandingkan dengan `host_receive_monotonic_ns` frame yang dipertahankan oleh
reader kanonik. Window harus utuh di dalam interval; batas interval bersifat
setengah terbuka. Window CSI tetap overlap satu sama lain.

## Evaluasi dan penggunaan

Default adalah 5-fold OOF dengan penempatan grup deterministik: semua window
dari satu take ditahan bersama pada satu fold. Pilih `--group-by session` atau
`--group-by subject` untuk menguji generalisasi yang lebih ketat; metadata grup
yang hilang akan membuat take tersebut tercatat sebagai dilewati, dan fold
yang kehilangan kelas training akan dihentikan. Jumlah fold dapat diatur dengan
`--folds`; jumlahnya harus 2 sampai jumlah grup.

```sh
python3 fall_detection/train_phase_activity_model.py \
  --algorithm linear-svm \
  --group-by take \
  --folds 5 \
  --output /tmp/phase-svm-take-oof
```

Hasil berisi `summary.json` dengan jumlah window dan metrik pooled OOF
per-window, serta `predictions.csv` dengan label aktual/prediksi, grup, take,
fase, rentang frame, dan skor mentah. Script tidak mengekspor atau mengganti
artifact firmware.

## Run historis sebelum pengecualian dan evaluasi stabilisasi

Run Linear SVM lima-fold per-take menghasilkan 3.300 labeled windows dari
192 take (101 `fall`, 3.199 `non_fall`); satu take tidak complete dan dilewati.
Pooled OOF: accuracy 97,48%, macro-F1 0,793; kelas `fall` precision 0,585,
recall 0,614, F1 0,599; kelas `non_fall` precision 0,988, recall 0,986,
F1 0,987. Tingginya accuracy terutama harus dibaca bersama imbalance kelas:
fall hanya 101 dari 3.300 window. Recall jatuh yang terukur belum memadai untuk
menjadikan model sebagai alarm. Artefak run disimpan sementara di
`/tmp/phase-svm-take-oof/`; belum ada model final yang di-fit/export untuk
firmware.

Run grouped per `subject_id` memakai tiga grup yang tersedia (dua subject
numerik dan satu grup `TEST01`), 1.745 labeled windows dari 103 take; 89 take
tanpa `subject_id` dan satu incomplete dilewati. Pooled OOF: accuracy 67,74%,
macro-F1 0,520; `fall` precision 0,141, recall 0,901, F1 0,244; `non_fall`
recall 0,664. Recall tinggi di sini disertai banyak false positive. Ini hanya
dua subject aktual ditambah satu grup smoke test, sehingga bukan validasi
lintas-populasi.

## Run terdahulu dan kandidat firmware

Angka dan artifact di bawah dibuat sebelum policy diperluas menjadi
`fall` dari offset 4 detik hingga akhir rekaman. Karena cakupan label positif
telah berubah, metrik, OOF predictions, dan artifact tersebut adalah hasil
policy lama dan tidak mewakili policy terbaru; jalankan ulang eksperimen
sebelum menggunakan atau mengekspor model untuk policy baru.

Run 5-fold grouped OOF per take dengan policy lama mengecualikan 4 take
dari sesi `SMOKE01` dan subject `TEST01`. Hasilnya 3.261 labeled windows dari
189 take: 101 `fall` dan 3.160 `non_fall`; satu take incomplete tidak
digunakan. Model final kemudian di-fit ulang pada semua 3.261 labeled windows,
bukan diambil dari fold OOF. Artifact-nya:
[`final_model_phase_linear_svm.json`](./phase_aware_run_20261114_stabilized/final_model_phase_linear_svm.json).

Metrik pooled OOF mentah per-window: accuracy 97,55%, macro-F1 0,783;
`fall` precision 61,80%, recall 54,46%, F1 0,579. Kelas `non_fall` memiliki
precision 98,55%, recall 98,92%, F1 0,987.

Stabilisasi temporal yang sama dengan helper firmware menurunkan transisi
kelas pada run ini dari 61 menjadi 17. Trade-off-nya: accuracy 97,12%,
macro-F1 0,755; `fall` precision 53,61%, recall 51,49%, F1 0,525. Ini
mengurangi kedipan label dengan menahan sebagian prediksi FALL; bukan
peningkatan metrik klasifikasi. Simulasi OOF ini hanya memberi skor pada window
berlabel dan mereset state ketika ada gap antar-window berlabel, jadi jumlah
transisinya bukan ukuran lengkap seluruh aliran prediksi firmware.

Kontrak model yang diekspor:

- Input LLTF 51 pasangan I/Q signed-int8 (102 byte), urutan pasangan tidak
  diubah; magnitudo `sqrt(I*I + Q*Q)`.
- Window 24 frame, stride 12; 16 band menggunakan
  `band = floor(subcarrier_index * 16 / 51)`. Tiap fitur adalah
  `log1p(mean(abs(delta_amplitude)))` atas subcarrier dalam band dan 23
  transisi frame yang berdekatan.
- Standardisasi menggunakan 16 mean dan 16 scale hasil fit full-data di
  artifact. Skor mentah adalah margin hinge one-vs-rest:
  `dot(weights[class], standardized_features) + intercept[class]`.
  Keputusan memakai argmax dalam urutan `fall`, `non_fall`; seri memilih
  `fall`. Skor bukan probabilitas atau confidence dan tidak dikalibrasi.
- Helper temporal mempublikasikan FALL setelah minimal 2 prediksi FALL dari
  3 window terakhir; kembali ke NON_FALL setelah 3 prediksi NON_FALL
  berurutan. Ini hanya mengubah label classifier aktivitas, bukan Motion
  Graph/FSM, threshold, baseline, smoothing, sensitivity, atau debounce.

Build ESP-IDF v5.5.3 berhasil untuk source kandidat ini; tidak dilakukan flash.
Image `wifi_sensing_demo.bin` berukuran `0xf1a20` byte terhadap partisi app
terkecil `0x100000`, dengan `0xe5e0` byte (6%) tersisa. Linker map mencatat
parameter model `.rodata` 264 byte, state stabilizer `.bss` 20 byte, dan
buffer history amplitude `.bss` 4.896 byte. Pemakaian statis seluruh firmware
yang dilaporkan `idf.py size` adalah DRAM 48.104 byte (`.bss` 30.632,
`.data` 17.472) dan IRAM 87.075 byte. Waktu inferensi, stack puncak, dan
performa pada perangkat belum diukur karena perangkat tidak di-flash.

## Run policy ekor 4 detik

Run ini memakai policy baru: window pre-action utuh adalah `non_fall`, lalu
window utuh mulai offset 4 detik hingga akhir rekaman adalah `fall`. Evaluasi
5-fold grouped OOF per take menghasilkan 4.098 window dari 189 take: 938
`fall` dan 3.160 `non_fall`; empat take dari sesi `SMOKE01` dikecualikan oleh
policy. Metrik pooled OOF per-window: accuracy 80,55%, macro-F1 0,686;
`fall` precision 61,21%, recall 41,04%, F1 0,491. Setelah stabilisasi,
accuracy 80,94%, macro-F1 0,701, dan recall `fall` 45,31%. Transisi prediksi
turun dari 382 menjadi 141.

Ini tetap evaluasi offline pada window yang berlabel; bukan replay seluruh
recording, metrik event, atau hasil realtime. Run ini tidak membuat model
full-fit maupun mengubah artifact firmware. Artifact dan angka di bagian
policy lama tidak boleh dipakai untuk mewakili target label yang baru.

## Batasan interpretasi

Grouped K-fold per take mencegah window dari take yang sama masuk ke sisi
training dan test sekaligus, tetapi bukan validasi lintas-sesi/subjek.
Pengelompokan `take` tidak membuat take independen dari sesi, subjek, tanggal,
posisi, atau kondisi radio yang sama. Metrik per-window juga bukan metrik event,
dan overlap window menjadikan sampel berkorelasi. Hasil ini hanya diagnostik
pipeline; dalam snapshot ini 39 take fall dan 2 take non-fall berada di
`sess_20261107T100226Z_luxlof`, sedangkan session lain hanya berisi non-fall
(dan 89 take non-fall tidak memiliki metadata sesi). Karena hanya satu sesi
memiliki fall, session-held-out tidak dapat mempertahankan kelas fall di
training. Evaluasi yang mendukung generalisasi perlu beberapa sesi dan subjek
untuk setiap kelas, dengan holdout yang benar-benar menyisakan semua kelas pada
training.

Hasil ini tidak untuk alarm keselamatan dan tidak otomatis diterapkan ke ESP32.
Evaluasi fase yang lebih kuat harus memakai label onset/impact yang ditinjau,
menetapkan jendela positif (termasuk apakah pemulihan termasuk target), lalu
melakukan evaluasi lintas-sesi/subjek sebelum memilih model atau mengubah
firmware.
