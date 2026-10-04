URL PROYEK: isu-pengangguran.vercel.app 

URL REPOSITORI: github.com/222313242/visdat_uas_222313242

# Isu Pengangguran yang Masih Berhamburan

Visualisasi interaktif mengenai dinamika pengangguran dan ketimpangan pembangunan sosio-ekonomi di 514 kabupaten/kota Indonesia.

## Tentang Proyek

Proyek ini dibuat untuk Proyek UAS Visualisasi Data dan Informasi

Visualisasi dikembangkan dalam bentuk data storytelling untuk melihat pengangguran melalui pola spasial dan struktur pembangunan sosio-ekonomi daerah.

Proyek menggunakan tiga pendekatan utama:

- Visualisasi geospasial
- Visualisasi multivariat
- Visualisasi hierarki

Analisis dan visualisasi yang digunakan meliputi:

- Tingkat Pengangguran Terbuka (TPT)
- Choropleth map
- Proportional symbol map
- Moran's I dan LISA
- Principal Component Analysis (PCA)
- Parallel coordinates
- Scatterplot matrix
- Correlation heatmap
- Treemap
- Sunburst

Visualisasi dilengkapi dengan tooltip, zoom dan pan, highlight, brushing dan linking, serta drill-down dengan breadcrumb.

## Data

Data utama berasal dari Badan Pusat Statistik (BPS). Data pendukung berupa batas wilayah kabupaten/kota digunakan untuk visualisasi geospasial.

### Sumber Data

1. Badan Pusat Statistik, *Keadaan Angkatan Kerja di Indonesia Agustus 2025*, Volume 47, Nomor 2, 2025. Tabel 27, untuk data pendidikan dan jenis kegiatan pada laki-laki.

2. Badan Pusat Statistik, *Keadaan Angkatan Kerja di Indonesia Agustus 2025*, Volume 47, Nomor 2, 2025. Tabel 28, untuk data pendidikan dan jenis kegiatan pada perempuan.

3. Badan Pusat Statistik, *Keadaan Angkatan Kerja di Indonesia Agustus 2025*, Volume 47, Nomor 2, 2025. Tabel 131, untuk data pengangguran dan kategori pekerja tidak penuh pada laki-laki.

4. Badan Pusat Statistik, *Keadaan Angkatan Kerja di Indonesia Agustus 2025*, Volume 47, Nomor 2, 2025. Tabel 132, untuk data pengangguran dan kategori pekerja tidak penuh pada perempuan.

5. Badan Pusat Statistik, *Indeks Pembangunan Teknologi Informasi & Komunikasi 2024*, Volume 7, 2025.

6. Badan Pusat Statistik, Tabel Statistik Kependudukan dan Migrasi, *Persentase Penduduk Daerah Perkotaan menurut Provinsi, 2010-2035*, 2025.

7. Badan Pusat Statistik, Tabel Statistik Kependudukan dan Migrasi, *Penduduk, Laju Pertumbuhan Penduduk, Distribusi Persentase Penduduk, Kepadatan Penduduk, Rasio Jenis Kelamin Penduduk Menurut Provinsi, 2025*, 2025.

8. Badan Pusat Statistik, Tabel Dinamis, *Angka Partisipasi Murni (APM) Menurut Provinsi dan Jenjang Pendidikan*, 2025.

9. Badan Pusat Statistik, *Statistik Pendidikan 2025*, 2025.

10. Badan Pusat Statistik, Tabel Dinamis, *[Seri 2010] PDRB Triwulanan Atas Dasar Harga Konstan Menurut Lapangan Usaha di Provinsi Seluruh Indonesia (Milyar Rupiah)*, 2025.

11. Badan Pusat Statistik, *Survei Angkatan Kerja Nasional (Sakernas)*, *Rata-Rata Upah/Gaji Bersih Sebulan Buruh/Karyawan/Pegawai menurut Provinsi dan Lapangan Usaha di 17 Sektor*, 2025.

12. Badan Pusat Statistik, Tabel Dinamis, *Persentase Penduduk Miskin (P0) Menurut Provinsi dan Daerah (Persen)*, 2025.

13. Badan Pusat Statistik, *Survei Penduduk Antar Sensus (SUPAS)*, *Rasio Ketergantungan Menurut Provinsi*, 2025.

14. Badan Pusat Statistik, Tabel Dinamis, *Penduduk Berumur 15 Tahun Keatas yang Bekerja Selama Seminggu Terakhir Menurut Kabupaten/Kota dan Lapangan Usaha (Orang)*, 2025.

15. Badan Pusat Statistik, Tabel Dinamis, *Tingkat Pengangguran Terbuka menurut Jenis Kelamin dan Kabupaten/Kota*, 2025.

16. LapakGIS, *Batas wilayah kabupaten/kota Indonesia 2024*, berkas shapefile, 2024. Accessed: Oct. 2, 2026. Available: https://www.lapakgis.com/

## Struktur Repository
Project dapat dijalankan menggunakan server lokal melalui index.html

```text
visdat_uas_222313242/
├── data/
│   ├── Input Data Tabulasi.xlsx
│   └── kabkota.geojson
├── output/
│   ├── data.json
│   ├── merged_kabkota.geojson
│   └── summary_for_report.txt
├── css/
│   └── style.css
├── js/
│   └── script.js
├── analisis.py
└── index.html
```

## Tools:

- HTML
- CSS
- JavaScript
- D3.js
- Leaflet
- Turf.js

##
Muhammad Haris Syah Putra / 222313242 / Politeknik Statistika STIS
