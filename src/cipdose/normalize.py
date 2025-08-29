import math, re
from pathlib import Path
from typing import Tuple
import numpy as np
import pandas as pd

from .io_utils import read_cip_ucd, write_outputs

FORM_TOKENS = {
    "CPR": "comprimé",
    "SEC": "comprimé sécable",
    "GEL": "gélule",
    "CAPSULE": "capsule",
    "COLLYRE": "collyre",
    "SOL": "solution",
    "INJ": "injection",
    "PATCH": "patch",
    "FL": "flacon",
    "STYLO": "stylo",
    "SUSP": "suspension",
    "SIROP": "sirop",
    "SACHET": "sachet",
}

def _to_float(s: str) -> float:
    return float(str(s).replace(",", ".").strip())

def _to_mg(value: float, unit: str) -> float:
    u = unit.upper()
    if u == "MG": return value
    if u == "G":  return value * 1000.0
    if u in ("MCG", "µG"): return value / 1000.0
    return float("nan")

def normalize_ids(df: pd.DataFrame) -> pd.DataFrame:
    for col, width in [("CIP13", 13), ("CIP7", 7), ("UCD13", 13), ("UCD7", 7)]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.replace(r"\D", "", regex=True)
                .str.zfill(width)
            )
    if "QTE" in df.columns:
        df["QTE"] = pd.to_numeric(df["QTE"], errors="coerce")
    return df

def parse_label(label: str) -> dict:
    S = str(label).upper()
    out = {}

    # Forme
    out["forme"] = next((lbl for tok, lbl in FORM_TOKENS.items()
                         if re.search(rf"\b{tok}\b", S)), None)

    # Nb d’unités en fallback (dernier entier)
    m_units = re.search(r"(\d+)\s*$", S)
    out["units_from_label"] = int(m_units.group(1)) if m_units else None

    # Tokens
    tokens = re.findall(r"(\d+(?:[.,]\d+)?)\s*(MCG|µG|MG|G|ML)", S)

    # Concentration X MG/ML + volume unitaire “… / Y ML”
    conc = re.search(r"(\d+(?:[.,]\d+)?)\s*(MCG|µG|MG|G)\s*/\s*ML", S)
    vol_last = re.search(r"/\s*([\d,\.]+)\s*ML\s*$", S)
    out["conc_mg_per_ml"] = None
    out["unit_volume_ml"] = None

    per_unit_mg = None
    if conc:
        conc_mg = _to_mg(_to_float(conc.group(1)), conc.group(2))
        out["conc_mg_per_ml"] = conc_mg if not math.isnan(conc_mg) else None
        if vol_last:
            vol_ml = _to_float(vol_last.group(1))
            out["unit_volume_ml"] = vol_ml
            if out["forme"] in ("collyre", "solution", "injection", "flacon") and out["conc_mg_per_ml"] is not None:
                per_unit_mg = conc_mg * vol_ml

    if per_unit_mg is None:
        mg_vals = [_to_mg(_to_float(v), u) for v, u in tokens if u.upper() in ("MG", "G", "MCG", "µG")]
        per_unit_mg = mg_vals[0] if mg_vals else None

    out["dose_par_unite_mg"] = None if per_unit_mg is None or math.isnan(per_unit_mg) else per_unit_mg

    # Combinaisons “A mg / B mg”
    combo = re.search(r"(\d+(?:[.,]\d+)?)\s*(MG|G|MCG|µG)\s*/\s*(\d+(?:[.,]\d+)?)\s*(MG|G|MCG|µG)", S)
    if combo:
        out["combo_a_mg"] = _to_mg(_to_float(combo.group(1)), combo.group(2))
        out["combo_b_mg"] = _to_mg(_to_float(combo.group(3)), combo.group(4))
    else:
        out["combo_a_mg"] = None
        out["combo_b_mg"] = None

    return out

def build_human_dose(row) -> str | None:
    if pd.notna(row.get("combo_a_mg")) and pd.notna(row.get("combo_b_mg")):
        base = f"{row['combo_a_mg']:.2f} mg + {row['combo_b_mg']:.2f} mg"
        if pd.notna(row.get("nb_unites_par_boite")):
            base += f" × {int(row['nb_unites_par_boite'])}"
        return base
    if pd.isna(row.get("dose_par_unite_mg")) and pd.notna(row.get("conc_mg_per_ml")):
        base = f"{row['conc_mg_per_ml']:.3f} mg/mL"
        if pd.notna(row.get("unit_volume_ml")):
            base += f", {row['unit_volume_ml']} mL/unité"
        if pd.notna(row.get("nb_unites_par_boite")):
            base += f" × {int(row['nb_unites_par_boite'])}"
        return base
    if pd.notna(row.get("dose_par_unite_mg")):
        base = f"{row['dose_par_unite_mg']:.2f} mg"
        if pd.notna(row.get("nb_unites_par_boite")):
            base += f" × {int(row['nb_unites_par_boite'])}"
        return base
    return None

def explode_components(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        a, b = r.get("combo_a_mg"), r.get("combo_b_mg")
        if pd.notna(a) and pd.notna(b):
            for idx, val in enumerate([a, b], start=1):
                rr = r.copy()
                rr["component_index"] = idx
                rr["dose_par_unite_mg_component"] = val
                rr["dose_totale_boite_mg_component"] = (
                    val * r["nb_unites_par_boite"] if pd.notna(r.get("nb_unites_par_boite")) else np.nan
                )
                rows.append(rr)
        else:
            rr = r.copy()
            rr["component_index"] = 1
            rr["dose_par_unite_mg_component"] = r.get("dose_par_unite_mg")
            rr["dose_totale_boite_mg_component"] = r.get("dose_totale_boite_mg")
            rows.append(rr)

    cols_keep = [
        "CIP13","CIP7","UCD13","UCD7","LIB_UCD","LIB_CIP","LABO","EPHMRA",
        "forme","nb_unites_par_boite","conc_mg_per_ml","unit_volume_ml",
        "component_index","dose_par_unite_mg_component","dose_totale_boite_mg_component"
    ]
    out = pd.DataFrame(rows)
    for c in cols_keep:
        if c not in out.columns:
            out[c] = np.nan
    return out[cols_keep]

def homogenize_cip13(cip_ucd_path: str | Path, outdir: str | Path = "out") -> tuple[pd.DataFrame, pd.DataFrame]:
    df = read_cip_ucd(cip_ucd_path)
    df = normalize_ids(df)

    label_col = "LIB_UCD" if "LIB_UCD" in df.columns else ("LIB_CIP" if "LIB_CIP" in df.columns else df.columns[-1])
    parsed = df[label_col].apply(parse_label).apply(pd.Series)
    base = pd.concat([df, parsed], axis=1)

    base["nb_unites_par_boite"] = base["QTE"].fillna(base["units_from_label"])
    base.drop(columns=["units_from_label"], inplace=True, errors="ignore")

    base["dose_totale_boite_mg"] = np.where(
        (base["combo_a_mg"].notna() & base["combo_b_mg"].notna()),
        np.nan,
        base["nb_unites_par_boite"] * base["dose_par_unite_mg"]
    )

    base["DOSE"] = base.apply(build_human_dose, axis=1)

    cols_norm = [
        "CIP13","CIP7","UCD13","UCD7","LABO","EPHMRA", label_col,
        "forme","nb_unites_par_boite","dose_par_unite_mg","dose_totale_boite_mg",
        "conc_mg_per_ml","unit_volume_ml","combo_a_mg","combo_b_mg","DOSE"
    ]
    cols_norm = [c for c in cols_norm if c in base.columns]
    norm = base[cols_norm].copy()

    comp = explode_components(base)
    write_outputs(norm, comp, outdir)
    return norm, comp
