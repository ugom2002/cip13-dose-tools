from cipdose.normalize import parse_label, build_human_dose

def test_parse_solid():
    p = parse_label("ESOMEPRAZOLE 20 MG CPR GASTRORESISTANT 14")
    assert p["dose_par_unite_mg"] == 20.0
    assert p["combo_a_mg"] is None and p["combo_b_mg"] is None

def test_parse_liquid_with_volume():
    p = parse_label("AVONEX 30 MCG/0,5 ML SOL INJ STYLO 4/0,5 ML")
    # 30 mcg = 0.03 mg ; 0.5 mL → 0.015 mg / unité
    assert abs(p["dose_par_unite_mg"] - 0.015) < 1e-6

def test_parse_combo():
    p = parse_label("VALSARTAN/HYDROCHLOROTHIAZIDE 80 MG/12,5 MG CPR 30")
    assert p["combo_a_mg"] == 80.0 and p["combo_b_mg"] == 12.5
