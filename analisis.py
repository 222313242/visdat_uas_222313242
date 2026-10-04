
#!/usr/bin/env python3
"""
Analysis pipeline for the latest Visdat UAS dataset.

Inputs
------
data/Input Data Tabulasi.xlsx
data/kabkota.geojson

Output
------
output/data.json

The output combines:
- source inventory / validation
- multivariate data + PCA + correlation
- spatial attributes + merged GeoJSON + Moran's I / LISA
- hierarchical data in D3 hierarchy form
- story-ready factual summaries
"""

import json
import math
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
XLSX = DATA_DIR / "Input Data Tabulasi.xlsx"
GEOJSON = DATA_DIR / "kabkota.geojson"
OUTPUT = OUTPUT_DIR / "data.json"
MERGED_GEOJSON_OUTPUT = OUTPUT_DIR / "merged_kabkota.geojson"
SUMMARY_OUTPUT = OUTPUT_DIR / "hasil analisis.txt"

SEED = 20261004
PERMUTATIONS = 499


PCA_FIELDS = [
    "APM SMA",
    "RLS",
    "Kontribusi PDRB Non Agrikultur (Persen)",
    "Persentase Penduduk Daerah Kota",
    "Indeks TIK",
    "Rerata Upah (Rupiah)",
    "Persentase Penduduk Miskin",
    "PMTB Per Kapita (Juta Rupiah)",
    "Rasio Ketergantungan",
]

PCA_KEYS = [
    "apm_sma",
    "rls",
    "pdrb_non_agri",
    "pct_urban",
    "ip_tik",
    "upah_rerata",
    "pct_miskin",
    "pmtb_per_kapita",
    "rasio_ketergantungan",
]

PCA_LABELS = {
    "apm_sma": "APM SMA",
    "rls": "RLS",
    "pdrb_non_agri": "PDRB non-agri",
    "pct_urban": "Perkotaan",
    "ip_tik": "IP-TIK",
    "upah_rerata": "Upah",
    "pct_miskin": "Kemiskinan",
    "pmtb_per_kapita": "PMTB/kapita",
    "rasio_ketergantungan": "Ketergantungan",
}

HIERARCHY_STATUS = [
    ("full", "Pekerja Penuh", "Aman", "#2f6f54"),
    ("part", "Pekerja Paruh Waktu", "Sukarela", "#d08a3c"),
    ("underemployed", "Setengah Penganggur", "Rentan", "#8b8060"),
    ("unemployed", "Pengangguran Terbuka", "Gagal", "#a53d30"),
]

REQUIRED_SHEETS = [
    "Data Hierarki",
    "Data Multivariate",
    "Data Spasial",
    "Base Kode WIlayah",
]


def json_number(v):
    if v is None:
        return None
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def json_clean(obj):
    """Convert pandas/numpy objects to plain JSON-safe objects."""
    if isinstance(obj, dict):
        return {str(k): json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return json_number(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if pd.isna(obj) if not isinstance(obj, (dict, list, tuple)) else False:
        return None
    return obj


def norm_code(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (int, np.integer)):
        return f"{int(v):02d}"
    if isinstance(v, (float, np.floating)):
        if abs(v - round(v)) < 1e-9:
            return f"{int(round(v)):02d}"
        return f"{v:.2f}"
    s = str(v).strip()
    try:
        f = float(s)
        if abs(f - round(f)) < 1e-9:
            return f"{int(round(f)):02d}"
        return f"{f:.2f}"
    except ValueError:
        return s


def read_excel():
    sheets = pd.read_excel(XLSX, sheet_name=None)
    missing = [s for s in REQUIRED_SHEETS if s not in sheets]
    if missing:
        raise ValueError(f"Sheet wajib tidak ditemukan: {missing}")
    return sheets


def inventory(sheets):
    roles = {
        "Data Hierarki": "Tabel kontingensi 8 kombinasi pendidikan × gender dengan 4 status pekerjaan.",
        "Data Multivariate": "Dataset analisis 38 provinsi dan 9 variabel struktural.",
        "Data Spasial": "Data ketenagakerjaan 514 kabupaten/kota: TPT, penganggur, angkatan kerja, dan bekerja.",
        "Base Kode WIlayah": "Bridge table untuk menghubungkan kode BPS dengan kode pada GeoJSON.",
        "Base Jumlah Penduduk": "Basis jumlah penduduk provinsi.",
        "APM": "Sumber indikator APM SMA.",
        "RLS": "Sumber rata-rata lama sekolah.",
        "PDRB Non Agri": "Sumber kontribusi PDRB non-agrikultur.",
        "IP TIK": "Sumber IP-TIK 2024 beserta status/provenance.",
        "Rerata Upah": "Sumber rata-rata upah/gaji bersih bulanan.",
        "Persentase Miskin": "Sumber persentase penduduk miskin.",
        "Rasio Ketergantungan": "Sumber rasio ketergantungan.",
        "Persentase Perkotaan": "Sumber persentase penduduk daerah perkotaan.",
        "PMTB Per Kapita": "Sumber PMTB per kapita.",
    }
    out = []
    for name, df in sheets.items():
        out.append({
            "sheet": name,
            "rows_total": int(df.shape[0]),
            "columns_total": int(df.shape[1]),
            "purpose": roles.get(name, ""),
        })
    return out


def prepare_multivariate(sheets):
    df = sheets["Data Multivariate"].copy()
    df = df[df["Provinsi"].notna()].copy()
    if df["Provinsi"].nunique() != 38:
        raise ValueError(f"Data Multivariate: expected 38 provinces, got {df['Provinsi'].nunique()}")

    for col in PCA_FIELDS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().any():
            bad = df.loc[df[col].isna(), "Provinsi"].tolist()
            raise ValueError(f"Data Multivariate: nilai hilang pada {col}: {bad}")

    # Province TPT is derived from district-level unemployed / labor totals.
    # Use the numeric province code instead of province names so text variants
    # such as "Kep. Bangka Belitung" vs "Kepulauan Bangka Belitung"
    # cannot create false missing values. It remains external to PCA.
    spatial = prepare_spatial_table(sheets)
    grouped = spatial.dropna(subset=["unemployed", "labor"]).groupby("province_code", as_index=True).agg(
        unemployed=("unemployed", "sum"),
        labor=("labor", "sum"),
        districts_used=("province_code", "size"),
    )
    grouped["tpt_prov"] = 100 * grouped["unemployed"] / grouped["labor"]
    expected_counts = spatial.groupby("province_code").size().to_dict()

    records = []
    for _, r in df.iterrows():
        province_code = int(r["Kode"])
        rec = {
            "code": province_code,
            "province_code": province_code,
            "province": str(r["Provinsi"]),
        }
        for src, key in zip(PCA_FIELDS, PCA_KEYS):
            rec[key] = json_number(r[src])
        if province_code in grouped.index:
            rec["tpt_prov"] = json_number(grouped.loc[province_code, "tpt_prov"])
            rec["districts_used_for_tpt"] = int(grouped.loc[province_code, "districts_used"])
        else:
            rec["tpt_prov"] = None
            rec["districts_used_for_tpt"] = 0
        rec["districts_expected_for_tpt"] = int(expected_counts.get(province_code, 0))
        rec["tpt_prov_is_partial"] = rec["districts_used_for_tpt"] < rec["districts_expected_for_tpt"]
        records.append(rec)
    return records



def jenks_breaks(values, k=5):
    vals = sorted(float(v) for v in values if v is not None and np.isfinite(float(v)))
    if not vals:
        return []
    uniq = sorted(set(vals))
    if len(uniq) <= k:
        return uniq

    n = len(vals)
    lower = np.zeros((n + 1, k + 1), dtype=int)
    variance = np.full((n + 1, k + 1), np.inf, dtype=float)

    for j in range(1, k + 1):
        lower[0, j] = 1
        variance[0, j] = 0

    for l in range(2, n + 1):
        s1 = s2 = w = 0.0
        for m in range(1, l):
            idx = l - m
            val = vals[idx - 1]
            w += 1
            s1 += val
            s2 += val * val
            v = s2 - (s1 * s1) / w
            for j in range(2, k + 1):
                if variance[l, j] >= v + variance[idx - 1, j - 1]:
                    lower[l, j] = idx
                    variance[l, j] = v + variance[idx - 1, j - 1]
        lower[l, 1] = 1
        variance[l, 1] = s2 - (s1 * s1) / w

    breaks = [0.0] * (k + 1)
    breaks[k] = vals[-1]
    c = n
    for j in range(k, 1, -1):
        idx = lower[c, j]
        breaks[j - 1] = vals[idx - 1]
        c = idx - 1
    breaks[0] = vals[0]
    return breaks


def classify_breaks(value, breaks):
    if value is None or not np.isfinite(float(value)) or len(breaks) < 2:
        return None
    for i in range(len(breaks) - 1):
        if value <= breaks[i + 1]:
            return i
    return len(breaks) - 2


def prepare_spatial_table(sheets):
    df = sheets["Data Spasial"].copy()
    df = df[df["kode_bps"].notna()].copy()
    if len(df) != 514:
        raise ValueError(f"Data Spasial: expected 514 districts, got {len(df)}")

    numeric_cols = {
        "Jumlah Bekerja": "employed",
        "TPT": "tpt",
        "Jumlah Penganggur": "unemployed",
        "Total Angkatan Kerja": "labor",
        "kode_bps": "bps_code",
    }
    for src, alias in numeric_cols.items():
        df[alias] = pd.to_numeric(df[src], errors="coerce")

    df["bps_code"] = pd.to_numeric(df["kode_bps"], errors="coerce")

    base = sheets["Base Kode WIlayah"].copy()
    if len(base) != 514:
        raise ValueError(f"Base Kode WIlayah: expected 514 rows, got {len(base)}")
    base["bps_code"] = pd.to_numeric(base["kode_bps"], errors="coerce")
    base["geo_code"] = base["kode_geojson"].map(norm_code)

    merged = df.merge(
        base[["bps_code", "geo_code", "nama_geojson", "Wilayah", "Provinsi"]],
        on="bps_code",
        how="left",
        suffixes=("", "_base"),
    )
    if merged["geo_code"].isna().any():
        raise ValueError("Ada data spasial yang tidak menemukan kode GeoJSON pada Base Kode WIlayah.")

    records = []
    for _, r in merged.iterrows():
        records.append({
            "no": int(r["No"]),
            "kode": str(r["Kode"]),
            "bps_code": int(r["bps_code"]),
            "province_code": int(int(r["bps_code"]) // 100),
            "geo_code": str(r["geo_code"]),
            "province": str(r["Provinsi"]),
            "name": str(r["Wilayah"]),
            "name_geojson": str(r["nama_geojson"]),
            "employed": json_number(r["employed"]),
            "tpt": json_number(r["tpt"]),
            "unemployed": json_number(r["unemployed"]),
            "labor": json_number(r["labor"]),
        })
    return pd.DataFrame(records)


def standardize_matrix(X):
    means = X.mean(axis=0)
    stds = X.std(axis=0, ddof=0)
    if np.any(stds == 0):
        raise ValueError("PCA memiliki variabel dengan standar deviasi nol.")
    return (X - means) / stds, means, stds


def orient_eigenvectors(evecs, loadings, labels):
    """Choose deterministic sign orientation for readable loadings."""
    # PC1: poverty loading positive.
    poverty_idx = labels.index("pct_miskin")
    if loadings[poverty_idx, 0] < 0:
        evecs[:, 0] *= -1
        loadings[:, 0] *= -1
    # PC2: wage loading negative, matching the story orientation.
    wage_idx = labels.index("upah_rerata")
    if loadings[wage_idx, 1] > 0:
        evecs[:, 1] *= -1
        loadings[:, 1] *= -1
    return evecs, loadings


def run_pca(multivariate):
    X = np.array([[r[k] for k in PCA_KEYS] for r in multivariate], dtype=float)
    Z, means, stds = standardize_matrix(X)
    corr_matrix = np.corrcoef(Z, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    loadings = eigenvectors * np.sqrt(np.maximum(eigenvalues, 0))
    eigenvectors, loadings = orient_eigenvectors(eigenvectors, loadings, PCA_KEYS)

    scores = Z @ eigenvectors
    explained = eigenvalues / eigenvalues.sum()

    pca_rows = []
    for i, r in enumerate(multivariate):
        pca_rows.append({
            "province": r["province"],
            "pc1": json_number(scores[i, 0]),
            "pc2": json_number(scores[i, 1]),
            "tpt_prov": r["tpt_prov"],
            "tpt_prov_is_partial": r["tpt_prov_is_partial"],
        })

    load_rows = []
    for j, key in enumerate(PCA_KEYS):
        load_rows.append({
            "key": key,
            "label": PCA_LABELS[key],
            "pc1": json_number(loadings[j, 0]),
            "pc2": json_number(loadings[j, 1]),
        })

    pairs = []
    for i in range(len(PCA_KEYS)):
        for j in range(i + 1, len(PCA_KEYS)):
            pairs.append({
                "a": PCA_KEYS[i],
                "b": PCA_KEYS[j],
                "a_label": PCA_LABELS[PCA_KEYS[i]],
                "b_label": PCA_LABELS[PCA_KEYS[j]],
                "r": json_number(corr_matrix[i, j]),
                "abs_r": json_number(abs(corr_matrix[i, j])),
            })
    pairs = sorted(pairs, key=lambda x: x["abs_r"], reverse=True)

    distances = np.sqrt((Z ** 2).sum(axis=1))
    atypical = [
        {"province": multivariate[i]["province"], "distance_z": json_number(distances[i])}
        for i in np.argsort(distances)[::-1][:8]
    ]

    parallel_scores = []
    for i, r in enumerate(multivariate):
        parallel_scores.append({
            "province": r["province"],
            **{key: json_number(Z[i, j]) for j, key in enumerate(PCA_KEYS)}
        })

    return {
        "variables": [
            {"key": k, "label": PCA_LABELS[k], "source_column": src}
            for k, src in zip(PCA_KEYS, PCA_FIELDS)
        ],
        "observations": len(multivariate),
        "standardization": "Z-score",
        "explained_variance": [json_number(x) for x in explained],
        "pc1_percent": json_number(explained[0] * 100),
        "pc2_percent": json_number(explained[1] * 100),
        "pc12_percent": json_number((explained[0] + explained[1]) * 100),
        "loadings": load_rows,
        "scores": pca_rows,
        "parallel_scores": parallel_scores,
        "correlation_matrix": [
            [json_number(v) for v in row] for row in corr_matrix
        ],
        "strongest_correlations": pairs[:8],
        "atypical_profiles": atypical,
    }


def geo_merge(geojson, spatial_records):
    by_key = {}
    for r in spatial_records:
        by_key[(str(r["geo_code"]), r["province"], r["name_geojson"])] = r

    features = []
    used = set()
    for feature in geojson["features"]:
        props = dict(feature.get("properties", {}))
        key = (
            norm_code(props.get("kode")),
            str(props.get("prov", "")),
            str(props.get("nama", "")),
        )
        rec = by_key.get(key)
        if rec is None:
            # Secondary validation: same geo code + province + name,
            # in case of text variation between workbook and GeoJSON.
            candidates = [
                (k, v)
                for k, v in by_key.items()
                if k[0] == norm_code(props.get("kode"))
                and k[1].strip().lower() == str(props.get("prov", "")).strip().lower()
                and k[2].strip().lower() == str(props.get("nama", "")).strip().lower()
            ]
            if candidates:
                rec = candidates[0][1]

        if rec is not None:
            used.add(rec["bps_code"])
            props.update({
                "matched": True,
                "bps_code": rec["bps_code"],
                "kode_bps": rec["bps_code"],
                "data_name": rec["name"],
                "data_province": rec["province"],
                "TPT": rec["tpt"],
                "Jumlah_Penganggur": rec["unemployed"],
                "Total_Angkatan_Kerja": rec["labor"],
                "Jumlah_Bekerja": rec["employed"],
            })
        else:
            props["matched"] = False
        feature_out = dict(feature)
        feature_out["properties"] = props
        features.append(feature_out)

    merged_geo = {
        "type": "FeatureCollection",
        "features": features,
    }

    unmatched_data = sorted(
        [r["bps_code"] for r in spatial_records if r["bps_code"] not in used]
    )
    unmatched_geo = sum(1 for f in features if not f["properties"].get("matched"))
    return merged_geo, {
        "primary_key": "kode_bps",
        "bridge_sheet": "Base Kode WIlayah",
        "geojson_key": "properties.kode",
        "validation_fields": ["Wilayah", "Provinsi", "nama_geojson"],
        "matched_data_rows": len(used),
        "total_data_rows": len(spatial_records),
        "unmatched_data_rows": unmatched_data,
        "unmatched_geojson_features": unmatched_geo,
        "ambiguous_geojson_code": ["92.01"],
        "note": "Kode BPS menjadi kunci utama; nama wilayah dan provinsi dipakai untuk validasi/disambiguasi.",
    }


def build_adjacency(features, valid_codes):
    geoms = [shape(f["geometry"]) if f.get("geometry") else None for f in features]
    valid_idx = [i for i, f in enumerate(features) if f.get("properties", {}).get("matched") and
                 f.get("properties", {}).get("kode_bps") in valid_codes and
                 json_number(f.get("properties", {}).get("TPT")) is not None]

    adjacency = {i: set() for i in valid_idx}
    # Bounding boxes first to avoid unnecessary geometry checks.
    bboxes = {}
    for i in valid_idx:
        g = geoms[i]
        if g is not None:
            bboxes[i] = g.bounds

    for pos, i in enumerate(valid_idx):
        gi = geoms[i]
        if gi is None:
            continue
        minx, miny, maxx, maxy = bboxes[i]
        for j in valid_idx[pos + 1:]:
            gj = geoms[j]
            if gj is None:
                continue
            jminx, jminy, jmaxx, jmaxy = bboxes[j]
            if maxx < jminx or jmaxx < minx or maxy < jminy or jmaxy < miny:
                continue
            try:
                # Queen contiguity: share an edge or a point.
                if gi.touches(gj):
                    adjacency[i].add(j)
                    adjacency[j].add(i)
            except Exception:
                continue
    return valid_idx, adjacency


def moran_and_lisa(merged_geo, spatial_records):
    features = merged_geo["features"]
    valid_codes = {r["bps_code"] for r in spatial_records if r["tpt"] is not None}

    valid_idx, adjacency = build_adjacency(features, valid_codes)
    n = len(valid_idx)
    vals = np.array(
        [float(features[i]["properties"]["TPT"]) for i in valid_idx],
        dtype=float
    )
    mean_val = float(vals.mean())
    z = vals - mean_val
    denom = float((z * z).sum())

    pos = {idx: p for p, idx in enumerate(valid_idx)}
    neighbors = []
    for idx in valid_idx:
        ns = sorted(adjacency.get(idx, set()))
        neighbors.append([pos[j] for j in ns])

    def moran_I(zv):
        num = 0.0
        s0 = 0.0
        for i, ns in enumerate(neighbors):
            if not ns:
                continue
            w = 1.0 / len(ns)
            for j in ns:
                num += w * zv[i] * zv[j]
                s0 += w
        return (n / s0) * (num / float((zv * zv).sum())) if s0 and np.any(zv) else np.nan

    I = moran_I(z)
    expected = -1 / (n - 1)
    rng = np.random.default_rng(SEED)
    permuted = []
    for _ in range(PERMUTATIONS):
        zp = rng.permutation(z)
        permuted.append(moran_I(zp))
    permuted = np.asarray(permuted, dtype=float)
    perm_mean = float(permuted.mean())
    perm_sd = float(permuted.std(ddof=1))
    z_score = (I - perm_mean) / perm_sd if perm_sd > 0 else np.nan
    p_global = (1 + int(np.sum(np.abs(permuted - perm_mean) >= abs(I - perm_mean)))) / (PERMUTATIONS + 1)

    lisa = []
    lisa_stats = []
    for ii, idx in enumerate(valid_idx):
        ns = neighbors[ii]
        lag = float(np.mean([z[j] for j in ns])) if ns else 0.0
        local_i = float(z[ii] * lag)
        if not ns:
            p = 1.0
        else:
            exceed = 0
            base_abs = abs(local_i)
            for _ in range(PERMUTATIONS):
                zp = rng.permutation(z)
                lagp = float(np.mean([zp[j] for j in ns]))
                if abs(z[ii] * lagp) >= base_abs:
                    exceed += 1
            p = (1 + exceed) / (PERMUTATIONS + 1)

        if p >= 0.05 or not ns:
            cluster = "NS"
        elif z[ii] >= 0 and lag >= 0:
            cluster = "HH"
        elif z[ii] < 0 and lag < 0:
            cluster = "LL"
        elif z[ii] >= 0 and lag < 0:
            cluster = "HL"
        else:
            cluster = "LH"

        props = features[idx]["properties"]
        lisa.append({
            "bps_code": int(props["kode_bps"]),
            "province": props.get("data_province", props.get("prov")),
            "name": props.get("data_name", props.get("nama")),
            "tpt": json_number(props.get("TPT")),
            "z": json_number(z[ii]),
            "spatial_lag": json_number(lag),
            "local_i": json_number(local_i),
            "p_value": json_number(p),
            "cluster": cluster,
            "neighbors": len(ns),
        })

    counts = {k: sum(1 for x in lisa if x["cluster"] == k) for k in ["HH", "LL", "HL", "LH", "NS"]}
    return {
        "n_valid": n,
        "mean_tpt": json_number(mean_val),
        "moran_i": json_number(I),
        "expected_i": json_number(expected),
        "permutation_mean": json_number(perm_mean),
        "permutation_sd": json_number(perm_sd),
        "z_score": json_number(z_score),
        "p_value": json_number(p_global),
        "permutations": PERMUTATIONS,
        "weighting": "row-standardized queen contiguity",
        "clusters": counts,
        "local": lisa,
    }


def build_hierarchy(sheets):
    df = sheets["Data Hierarki"].copy()
    if len(df) != 8:
        raise ValueError(f"Data Hierarki: expected 8 rows, got {len(df)}")
    edu_order = ["SD ke Bawah", "SMP", "SMA / SMK", "Perguruan Tinggi (Dip/PT)"]

    children = []
    for key, label, risk, color in HIERARCHY_STATUS:
        status_children = []
        source_col = {
            "full": "Pekerja Penuh",
            "part": "Pekerja Paruh Waktu",
            "underemployed": "Setengah Penganggur",
            "unemployed": "Pengangguran Terbuka",
        }[key]
        for edu in edu_order:
            subset = df[df["Tingkat Pendidikan"] == edu].copy()
            gender_children = []
            for _, row in subset.iterrows():
                gender_children.append({
                    "name": str(row["Jenis Kelamin"]),
                    "type": "gender",
                    "gender": str(row["Jenis Kelamin"]),
                    "status": key,
                    "education": edu,
                    "value": int(pd.to_numeric(row[source_col], errors="coerce")),
                    "color": color,
                })
            status_children.append({
                "name": edu,
                "type": "education",
                "education": edu,
                "color": color,
                "children": gender_children,
            })
        children.append({
            "name": label,
            "type": "status",
            "status": key,
            "risk_label": risk,
            "color": color,
            "children": status_children,
        })

    root_value = sum(
        g["value"]
        for s in children for e in s["children"] for g in e["children"]
    )

    # Story-ready summaries.
    long_rows = []
    for _, row in df.iterrows():
        for key, label, risk, color in HIERARCHY_STATUS:
            long_rows.append({
                "education": str(row["Tingkat Pendidikan"]),
                "gender": str(row["Jenis Kelamin"]),
                "status": label,
                "status_key": key,
                "value": int(pd.to_numeric(row[{
                    "full": "Pekerja Penuh",
                    "part": "Pekerja Paruh Waktu",
                    "underemployed": "Setengah Penganggur",
                    "unemployed": "Pengangguran Terbuka",
                }[key]], errors="coerce")),
            })
    long_df = pd.DataFrame(long_rows)

    status_summary = long_df.groupby(["status_key", "status"], as_index=False)["value"].sum()
    status_summary["share_root"] = 100 * status_summary["value"] / root_value

    gender_summary = long_df.groupby("gender", as_index=False)["value"].sum()
    gender_open = (
        long_df[long_df["status_key"] == "unemployed"]
        .groupby("gender", as_index=False)["value"]
        .sum()
        .rename(columns={"value": "unemployed_open"})
    )
    gender_summary = gender_summary.merge(gender_open, on="gender")
    gender_summary["open_rate"] = 100 * gender_summary["unemployed_open"] / gender_summary["value"]

    education_summary = long_df.groupby("education", as_index=False)["value"].sum()
    education_open = (
        long_df[long_df["status_key"] == "unemployed"]
        .groupby("education", as_index=False)["value"]
        .sum()
        .rename(columns={"value": "unemployed_open"})
    )
    education_summary = education_summary.merge(education_open, on="education")
    education_summary["open_rate"] = 100 * education_summary["unemployed_open"] / education_summary["value"]

    status_education = long_df.groupby(
        ["status_key", "status", "education"], as_index=False
    )["value"].sum()

    return {
        "root": {
            "name": "Angkatan Kerja",
            "type": "root",
            "value": root_value,
            "children": children,
        },
        "story": {
            "status": status_summary.to_dict(orient="records"),
            "gender": gender_summary.to_dict(orient="records"),
            "education": education_summary.to_dict(orient="records"),
            "status_by_education": status_education.to_dict(orient="records"),
        },
    }


def build_report_summary(multivariate, spatial_records, pca, moran, hierarchy, merge_info, breaks, sheets):
    s = pd.DataFrame(spatial_records)

    max_row = s.loc[s["tpt"].idxmax()]
    min_row = s.loc[s["tpt"].idxmin()]

    status_sorted = sorted(hierarchy["story"]["status"], key=lambda x: x["value"], reverse=True)
    gender_sorted = sorted(hierarchy["story"]["gender"], key=lambda x: x["value"], reverse=True)
    education_by_rate = sorted(hierarchy["story"]["education"], key=lambda x: x["open_rate"], reverse=True)
    education_by_count = sorted(hierarchy["story"]["education"], key=lambda x: x["unemployed_open"], reverse=True)

    pc1_top = sorted(pca["loadings"], key=lambda x: abs(x["pc1"]), reverse=True)[:4]
    pc2_top = sorted(pca["loadings"], key=lambda x: abs(x["pc2"]), reverse=True)[:4]

    summary = {
        "data_scope": {
            "sheet_count": len(sheets),
            "multivariate_observations": len(multivariate),
            "multivariate_variables": len(PCA_KEYS),
            "spatial_units": len(spatial_records),
            "geojson_features": merge_info["total_data_rows"] + merge_info["unmatched_geojson_features"],
            "hierarchy_leaf_groups": 4 * 4 * 2,
            "hierarchy_root_people": hierarchy["root"]["value"],
        },
        "spatial": {
            "mean_tpt_percent": json_number(s["tpt"].mean()),
            "min_tpt": {"name": str(min_row["name"]), "province": str(min_row["province"]), "tpt_percent": json_number(min_row["tpt"])},
            "max_tpt": {"name": str(max_row["name"]), "province": str(max_row["province"]), "tpt_percent": json_number(max_row["tpt"])},
            "count_tpt_ge_5_percent": int((s["tpt"] >= 5).sum()),
            "total_unemployed": int(s["unemployed"].sum()),
            "jenks_breaks": [json_number(x) for x in breaks],
        },
        "moran_lisa": {
            "valid_units": moran["n_valid"],
            "moran_i": moran["moran_i"],
            "expected_i": moran["expected_i"],
            "z_score": moran["z_score"],
            "p_value": moran["p_value"],
            "permutations": moran["permutations"],
            "clusters": moran["clusters"],
        },
        "pca": {
            "observations": pca["observations"],
            "variables": len(pca["variables"]),
            "pc1_percent": pca["pc1_percent"],
            "pc2_percent": pca["pc2_percent"],
            "pc12_percent": pca["pc12_percent"],
            "pc1_dominant_loadings": pc1_top,
            "pc2_dominant_loadings": pc2_top,
            "strongest_correlations": pca["strongest_correlations"][:5],
            "most_atypical_profiles": pca["atypical_profiles"][:5],
        },
        "hierarchy": {
            "root_people": hierarchy["root"]["value"],
            "status_largest_by_count": status_sorted[0] if status_sorted else None,
            "status_all": status_sorted,
            "gender_largest_by_count": gender_sorted[0] if gender_sorted else None,
            "gender_all": gender_sorted,
            "education_highest_open_rate": education_by_rate[0] if education_by_rate else None,
            "education_highest_open_count": education_by_count[0] if education_by_count else None,
            "education_all": education_by_rate,
        },
        "join_quality": {
            "matched_data_rows": merge_info["matched_data_rows"],
            "total_data_rows": merge_info["total_data_rows"],
            "unmatched_data_rows": merge_info["unmatched_data_rows"],
            "unmatched_geojson_features": merge_info["unmatched_geojson_features"],
            "ambiguous_geojson_code": merge_info["ambiguous_geojson_code"],
        },
    }
    return summary


def format_report_summary(summary):
    spatial = summary["spatial"]
    moran = summary["moran_lisa"]
    pca = summary["pca"]
    hierarchy = summary["hierarchy"]
    join = summary["join_quality"]
    largest_status = hierarchy["status_largest_by_count"]
    largest_gender = hierarchy["gender_largest_by_count"]
    hardest_education = hierarchy["education_highest_open_rate"]

    lines = [
        "RINGKASAN HASIL ANALISIS",
        "",
        "1. CAKUPAN DATA",
        f"- Multivariat: {summary['data_scope']['multivariate_observations']} provinsi × {summary['data_scope']['multivariate_variables']} variabel.",
        f"- Spasial: {summary['data_scope']['spatial_units']} kabupaten/kota.",
        f"- Hierarki: {summary['data_scope']['hierarchy_leaf_groups']} kelompok daun; total root {summary['data_scope']['hierarchy_root_people']:,} orang.",
        "",
        "2. GEOSPASIAL",
        f"- Rata-rata TPT kabupaten/kota: {spatial['mean_tpt_percent']:.2f}%.",
        f"- TPT tertinggi: {spatial['max_tpt']['name']} ({spatial['max_tpt']['province']}), {spatial['max_tpt']['tpt_percent']:.2f}%.",
        f"- TPT terendah: {spatial['min_tpt']['name']} ({spatial['min_tpt']['province']}), {spatial['min_tpt']['tpt_percent']:.2f}%.",
        f"- Kab/kota dengan TPT ≥ 5%: {spatial['count_tpt_ge_5_percent']} dari {summary['data_scope']['spatial_units']}.",
        f"- Total penganggur dari tabel spasial: {spatial['total_unemployed']:,} orang.",
        f"- Klasifikasi choropleth: Jenks natural breaks, 5 kelas; break {', '.join(f'{x:.2f}' for x in spatial['jenks_breaks'])}.",
        "",
        "3. AUTOKORELASI SPASIAL",
        f"- Moran's I: {moran['moran_i']:.4f}.",
        f"- Expected I: {moran['expected_i']:.4f}.",
        f"- z-score: {moran['z_score']:.3f}.",
        f"- p-value permutasi: {moran['p_value']:.4f}; {moran['permutations']} permutasi.",
        f"- LISA: HH={moran['clusters']['HH']}, LL={moran['clusters']['LL']}, HL={moran['clusters']['HL']}, LH={moran['clusters']['LH']}, NS={moran['clusters']['NS']}.",
        "",
        "4. PCA / MULTIVARIAT",
        f"- PC1 menjelaskan {pca['pc1_percent']:.2f}% variasi.",
        f"- PC2 menjelaskan {pca['pc2_percent']:.2f}% variasi.",
        f"- Dua komponen pertama menjelaskan {pca['pc12_percent']:.2f}% variasi.",
        f"- Loading absolut terbesar PC1: {', '.join(x['label'] for x in pca['pc1_dominant_loadings'])}.",
        f"- Loading absolut terbesar PC2: {', '.join(x['label'] for x in pca['pc2_dominant_loadings'])}.",
        "- TPT tidak digunakan sebagai input PCA; TPT digunakan sebagai variabel eksternal untuk interpretasi/pewarnaan.",
        "",
        "5. HIERARKI",
        f"- Status terbesar secara absolut: {largest_status['status']} ({largest_status['value']:,}; {largest_status['share_root']:.2f}% dari root).",
        f"- Kelompok gender terbesar: {largest_gender['gender']} ({largest_gender['value']:,}).",
        f"- Pendidikan dengan proporsi Pengangguran Terbuka tertinggi: {hardest_education['education']} ({hardest_education['open_rate']:.2f}%).",
        f"- Jumlah Pengangguran Terbuka pada pendidikan tersebut: {hardest_education['unemployed_open']:,} dari {hardest_education['value']:,}.",
        "",
        "6. KUALITAS JOIN SPASIAL",
        f"- Data BPS matched: {join['matched_data_rows']} / {join['total_data_rows']}.",
        f"- Data BPS unmatched: {join['unmatched_data_rows']}.",
        f"- Feature GeoJSON unmatched: {join['unmatched_geojson_features']}.",
        f"- Kode GeoJSON ambiguous: {', '.join(join['ambiguous_geojson_code'])}.",
        "",
    ]
    return "\n".join(lines) + "\n"


def story_facts(multivariate, spatial_records, pca, moran, hierarchy):
    s = pd.DataFrame(spatial_records)
    max_row = s.loc[s["tpt"].idxmax()]
    min_row = s.loc[s["tpt"].idxmin()]
    top_tpt = s.sort_values("tpt", ascending=False).head(10)[["name", "province", "tpt", "unemployed"]].to_dict(orient="records")

    status = sorted(hierarchy["story"]["status"], key=lambda x: x["value"], reverse=True)
    edu = sorted(hierarchy["story"]["education"], key=lambda x: x["open_rate"], reverse=True)
    gender = hierarchy["story"]["gender"]

    pc1 = sorted(pca["loadings"], key=lambda x: abs(x["pc1"]), reverse=True)
    pc2 = sorted(pca["loadings"], key=lambda x: abs(x["pc2"]), reverse=True)
    correlations = pca["strongest_correlations"]

    return {
        "spatial": {
            "mean_tpt": json_number(s["tpt"].mean()),
            "max_tpt": {
                "name": max_row["name"], "province": max_row["province"], "tpt": json_number(max_row["tpt"])
            },
            "min_tpt": {
                "name": min_row["name"], "province": min_row["province"], "tpt": json_number(min_row["tpt"])
            },
            "count_ge_5": int((s["tpt"] >= 5).sum()),
            "total_unemployed": int(s["unemployed"].sum()),
            "top_tpt": top_tpt,
            "selected_regions": {
                x["name"]: {
                    "province": x["province"],
                    "tpt": json_number(x["tpt"]),
                    "unemployed": json_number(x["unemployed"]),
                }
                for x in top_tpt + s[s["name"].isin(["Lebak", "Sukabumi", "Pandeglang"])].to_dict(orient="records")
            },
        },
        "moran": {
            "moran_i": moran["moran_i"],
            "z_score": moran["z_score"],
            "p_value": moran["p_value"],
            "clusters": moran["clusters"],
        },
        "pca": {
            "pc1_percent": pca["pc1_percent"],
            "pc2_percent": pca["pc2_percent"],
            "pc12_percent": pca["pc12_percent"],
            "pc1_dominant": pc1[:4],
            "pc2_dominant": pc2[:4],
            "strongest_correlations": correlations[:5],
            "atypical_profiles": pca["atypical_profiles"][:5],
        },
        "hierarchy": {
            "status": status,
            "gender": gender,
            "education_by_open_rate": edu,
        },
    }


def main():
    if not XLSX.exists():
        raise FileNotFoundError(XLSX)
    if not GEOJSON.exists():
        raise FileNotFoundError(GEOJSON)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sheets = read_excel()

    with open(GEOJSON, "r", encoding="utf-8") as f:
        raw_geojson = json.load(f)

    spatial_df = prepare_spatial_table(sheets)
    breaks = jenks_breaks(spatial_df["tpt"].tolist(), 5)
    spatial_df["tpt_class"] = spatial_df["tpt"].apply(lambda v: classify_breaks(v, breaks))
    spatial_records = spatial_df.to_dict(orient="records")
    multivariate = prepare_multivariate(sheets)
    pca = run_pca(multivariate)
    merged_geo, merge_info = geo_merge(raw_geojson, spatial_records)
    moran = moran_and_lisa(merged_geo, spatial_records)
    hierarchy = build_hierarchy(sheets)

    story = story_facts(multivariate, spatial_records, pca, moran, hierarchy)
    summary = build_report_summary(
        multivariate, spatial_records, pca, moran, hierarchy, merge_info, breaks, sheets
    )

    result = {
        "meta": {
            "project": "Dinamika Pengangguran dan Ketimpangan Pembangunan Sosio-Ekonomi di 514 Kabupaten/Kota Indonesia",
            "title": "Isu Pengangguran yang Masih Memprihatinkan",
            "generated_from": {
                "workbook": str(XLSX.name),
                "geojson": str(GEOJSON.name),
                "workbook_sha256": hashlib.sha256(XLSX.read_bytes()).hexdigest(),
                "geojson_sha256": hashlib.sha256(GEOJSON.read_bytes()).hexdigest(),
            },
            "data_inventory": inventory(sheets),
            "spatial_join": merge_info,
            "spatial_classification": {
                "method": "Jenks natural breaks",
                "classes": 5,
                "breaks": [json_number(x) for x in breaks],
                "variable": "TPT"
            },
            "hierarchy_levels": ["Status Pekerjaan", "Tingkat Pendidikan", "Jenis Kelamin"],
            "hierarchy_shape": "4 → 4 → 2",
            "pca_note": "TPT is external for interpretation/coloring and is not an input variable of PCA.",
        },
        "multivariate": multivariate,
        "pca": pca,
        "spatial": spatial_records,
        "moran": moran,
        "hierarchy": hierarchy,
        "story": story,
        "summary": summary,
    }

    MERGED_GEOJSON_OUTPUT.write_text(
        json.dumps(json_clean(merged_geo), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    OUTPUT.write_text(
        json.dumps(json_clean(result), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    SUMMARY_OUTPUT.write_text(format_report_summary(summary), encoding="utf-8")

    print(f"Generated {OUTPUT}")
    print(f"Generated {SUMMARY_OUTPUT}")
    print(f"Generated {MERGED_GEOJSON_OUTPUT}")
    print(f"Multivariat: {len(multivariate)} provinsi × {len(PCA_KEYS)} variabel")
    print(f"Spasial: {len(spatial_records)} wilayah")
    print(f"GeoJSON: {len(merged_geo['features'])} features")
    print(f"PCA: PC1={pca['pc1_percent']:.2f}% PC2={pca['pc2_percent']:.2f}%")
    print(f"Moran I={moran['moran_i']:.4f}, z={moran['z_score']:.3f}, p={moran['p_value']:.4f}")
    print(f"Hierarchy root={hierarchy['root']['value']:,}")
    print(f"Spatial join unmatched data rows={merge_info['unmatched_data_rows']}, unmatched GeoJSON={merge_info['unmatched_geojson_features']}")
    print(f"rerata TPT={summary['spatial']['mean_tpt_percent']:.2f}%, total pengangguran={summary['spatial']['total_unemployed']:,}")
    print(f"TPT tertinggi={summary['spatial']['max_tpt']['name']} {summary['spatial']['max_tpt']['tpt_percent']:.2f}%")
    print(f"TPT tertinggi berdasar pendidikan={summary['hierarchy']['education_highest_open_rate']['education']} {summary['hierarchy']['education_highest_open_rate']['open_rate']:.2f}%")


if __name__ == "__main__":
    main()
