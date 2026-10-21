# Preflight dokumentasi (wajib untuk semua AI agent)

Dokumen ini adalah gerbang sebelum menyentuh perilaku runtime. Membacanya
bukan formalitas: agent harus mengutip isinya.

## Kapan wajib

Sebelum edit atau commit pertama pada:

- `examples/esp-radar/wifi_sensing_demo/main/**` (firmware C)
- `examples/esp-radar/wifi_sensing_demo/tools/**` (UI web serial)
- `examples/esp-radar/wifi_sensing_demo/sdkconfig*`
- `examples/esp-radar/wifi_sensing_demo/managed_components/**`
- driver Wi-Fi/BT, konfigurasi radio, parameter keamanan, atau protokol apa pun

## Sumber wajib, sesuai versi terpasang

| Komponen | Versi | Sumber |
| --- | --- | --- |
| `esp_wifi_sensing` | 0.1.1 (revisi registry `0.1.1~3`) | `managed_components/espressif__esp_wifi_sensing/README.md` dan <https://components.espressif.com/components/espressif/esp_wifi_sensing/versions/0.1.1~3/readme> |
| `esp-radar` | 0.3.4 | `managed_components/espressif__esp-radar/README.md`, `include/esp_radar.h`, `src/esp_radar.c` |
| ESP-IDF | v5.5.3 | `espressif-docs_search_espressif_sources`, atau `/home/azri/.espressif/v5.5.3/esp-idf` |

Salinan lokal adalah sumber utama karena versinya persis yang di-build. URL
registry dipakai untuk memastikan README lokal tidak dimodifikasi.

## Jangan pakai

MCP `esp-idf` di `~/.config/opencode/opencode.jsonc` menunjuk ke **v6.0**.
Jangan pakai untuk proyek ini. Kalau hanya itu yang tersedia, sebutkan
ketidakcocokan versinya secara eksplisit sebelum menjawab.

## Urutan kerja

1. Baca sumber di atas untuk topik yang akan diubah (fungsi, konstanta,
   perilaku driver). Bukan untuk membenarkan tebakan yang sudah dibuat.
2. Tuliskan bukti sebelum edit pertama:

   ```text
   Dokumen: <nama komponen> <versi> <path/URL>
   Kutipan: <satu API/konstanta/perilaku persis dari dokumen>
   ```

3. Sebutkan sumber di jawaban akhir dan di trailer commit:

   ```text
   Docs: esp_wifi_sensing 0.1.1 managed_components/espressif__esp_wifi_sensing/README.md
   ```

## Log perubahan wajib

Setiap perubahan kode wajib dicatat di `docs/agent-changes.md` sebelum commit.
Entri baru ditambahkan di paling bawah dengan format yang ada di bagian atas
file itu: file, perubahan, alasan, dokumen, dan verifikasi. Ini bukan ringkasan
diff; tujuannya menyimpan keputusan dan buktinya.

## Kalau dokumentasi tidak ditemukan

Tulis "tidak ditemukan" secara eksplisit. Jangan menggantinya dengan penalaran
lalu menyebutnya fakta. Untuk kondisi ini, trailer commit memakai:

```text
Docs: none (tidak ditemukan; alasan: ...)
```

## Kalau dokumentasi bertentangan dengan pengamatan

Pengamatan perangkat menang. Catat bagian mana yang tidak cocok dan sebutkan
di pesan commit. Dokumentasi yang menyesatkan adalah bug yang perlu
dilaporkan ke Espressif.

## Penegakan

- Gate commit: `.githooks/commit-msg` menolak commit yang mengubah kode tanpa
  entri di `docs/agent-changes.md`, dan menolak commit yang menyentuh path di
  atas tanpa trailer `Docs:`. Aktifkan sekali per clone dengan
  `git config core.hooksPath .githooks`. Bypass darurat:
  `git commit --no-verify`.
- Adapter per tool: `AGENTS.md` (opencode, Codex, Cursor, Zed), `CLAUDE.md`
  (Claude Code), `.github/copilot-instructions.md` (Copilot),
  `.cursor/rules/espressif-docs.mdc` (Cursor).
