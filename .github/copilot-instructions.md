# Instruksi untuk agen

Wajib membaca `docs/agent-preflight.md` sebelum mengubah perilaku runtime:
firmware `examples/esp-radar/wifi_sensing_demo/main/**`, UI `tools/**`,
`sdkconfig*`, atau apa pun yang menyentuh driver Wi-Fi/BT, radio, keamanan,
dan protokol.

Tuliskan `Dokumen: <komponen> <versi> <path/URL>` dan satu baris `Kutipan:`
sebelum edit pertama, lalu sertakan trailer `Docs:` pada pesan commit.

Setiap perubahan kode juga wajib dicatat di `docs/agent-changes.md` (entri baru
di paling bawah): file, perubahan, alasan, dokumen, dan verifikasi. Commit yang
mengubah kode tanpa entri itu ditolak oleh `.githooks/commit-msg`.

Proyek ini di-build dengan ESP-IDF v5.5.3. Jangan memakai MCP `esp-idf` v6.0
untuk pertanyaan tentang proyek ini.
