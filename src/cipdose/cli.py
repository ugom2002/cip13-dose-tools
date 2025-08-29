import argparse
from .normalize import homogenize_cip13

def main():
    ap = argparse.ArgumentParser(description="Normalize CIP13 presentations from CIP_UCD.csv")
    ap.add_argument("--cipucd", required=True, help="Chemin vers CIP_UCD.csv (ANSM)")
    ap.add_argument("--outdir", default="out", help="Dossier de sortie (parquet-first)")
    args = ap.parse_args()
    homogenize_cip13(args.cipucd, args.outdir)
