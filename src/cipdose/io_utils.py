from pathlib import Path
import pandas as pd

def detect_header_row(path: Path, enc: str = "utf-16", probe: int = 200) -> int:
    with open(path, "r", encoding=enc, errors="ignore") as f:
        for i, line in enumerate(f):
            if i > probe:
                break
            if "CodeCIP13" in line and ";" in line:
                return i
    return 0

def read_cip_ucd(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    header_idx = detect_header_row(path)
    df = pd.read_csv(path, sep=";", encoding="utf-16", header=header_idx, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    # Normalize column names
    colmap = {
        "CodeCIP13": "CIP13",
        "CodeCIP": "CIP7",
        "CodeUCD13": "UCD13",
        "CodeUCD": "UCD7",
        "LibelleUCD": "LIB_UCD",
        "LibelleCIP": "LIB_CIP",
        "Laboratoire": "LABO",
        "Qte": "QTE",
        "EphMRA": "EPHMRA",
    }
    for k, v in colmap.items():
        if k in df.columns:
            df.rename(columns={k: v}, inplace=True)
    return df

def write_outputs(norm_df: pd.DataFrame, comp_df: pd.DataFrame, outdir: str | Path) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        norm_df.to_parquet(outdir / "cip13_norm.parquet", index=False)
        comp_df.to_parquet(outdir / "cip13_components.parquet", index=False)
    except Exception as e:
        # Fallback CSV si pyarrow non dispo
        print(f"[WARN] Parquet indisponible ({e}). Fallback CSV.")
        norm_df.to_csv(outdir / "cip13_norm.csv", index=False, encoding="utf-8")
        comp_df.to_csv(outdir / "cip13_components.csv", index=False, encoding="utf-8")
