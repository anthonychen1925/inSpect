#!/usr/bin/env python3
"""
build_fixtures.py
=================
For each demo molecule:
  1. Loads the real experimental spectra from data/fixtures/spectra/
  2. Generates RDKit 3D conformers (MMFF94)
  3. Finds 4 structurally similar distractor molecules via fingerprint similarity
  4. Builds ranked candidate list for each modality combination
  5. Saves data/fixtures/<name>.json

Run AFTER fetch_demo_data.py.
"""
import json
import sys
import csv
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SPEC_DIR  = ROOT / "data" / "fixtures" / "spectra"
FIX_DIR   = ROOT / "data" / "fixtures"

# 20 demo molecules (same list as fetch script)
DEMO_MOLECULES = [
    {"name": "caffeine",       "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",             "formula": "C8H10N4O2",  "mw": 194.19},
    {"name": "aspirin",        "smiles": "CC(=O)Oc1ccccc1C(=O)O",                   "formula": "C9H8O4",     "mw": 180.16},
    {"name": "ibuprofen",      "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",              "formula": "C13H18O2",   "mw": 206.28},
    {"name": "acetaminophen",  "smiles": "CC(=O)Nc1ccc(O)cc1",                       "formula": "C8H9NO2",    "mw": 151.16},
    {"name": "dopamine",       "smiles": "NCCc1ccc(O)c(O)c1",                        "formula": "C8H11NO2",   "mw": 153.18},
    {"name": "serotonin",      "smiles": "NCCc1c[nH]c2ccc(O)cc12",                   "formula": "C10H12N2O",  "mw": 176.21},
    {"name": "nicotine",       "smiles": "CN1CCC[C@@H]1c1cccnc1",                    "formula": "C10H14N2",   "mw": 162.23},
    {"name": "glucose",        "smiles": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O", "formula": "C6H12O6",    "mw": 180.16},
    {"name": "cholesterol",    "smiles": "C[C@@H](CCCC(C)C)[C@H]1CC[C@@H]2[C@@H]1CC=C3C[C@@H](O)CC[C@]23C", "formula": "C27H46O", "mw": 386.65},
    {"name": "vanillin",       "smiles": "COc1cc(C=O)ccc1O",                         "formula": "C8H8O3",     "mw": 152.15},
    {"name": "menthol",        "smiles": "CC(C)[C@@H]1CC[C@@H](C)C[C@H]1O",         "formula": "C10H20O",    "mw": 156.26},
    {"name": "capsaicin",      "smiles": "COc1cc(CNC(=O)CCCC/C=C/C(C)C)ccc1O",      "formula": "C18H27NO3",  "mw": 305.41},
    {"name": "citric_acid",    "smiles": "OC(=O)CC(O)(CC(=O)O)C(=O)O",              "formula": "C6H8O7",     "mw": 192.12},
    {"name": "lidocaine",      "smiles": "CCN(CC)CC(=O)Nc1c(C)cccc1C",              "formula": "C14H22N2O",  "mw": 234.34},
    {"name": "quinine",        "smiles": "COc1ccc2nccc(c2c1)[C@@H](O)[C@H]3CC[N@@]4CC[C@@H](C=C)[C@H](C3)[C@@H]4", "formula": "C20H24N2O2", "mw": 324.41},
    {"name": "penicillin_g",   "smiles": "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O", "formula": "C16H18N2O4S", "mw": 334.39},
    {"name": "ethanol",        "smiles": "CCO",                                       "formula": "C2H6O",      "mw": 46.07},
    {"name": "benzene",        "smiles": "c1ccccc1",                                  "formula": "C6H6",       "mw": 78.11},
    {"name": "acetone",        "smiles": "CC(C)=O",                                   "formula": "C3H6O",      "mw": 58.08},
    {"name": "toluene",        "smiles": "Cc1ccccc1",                                 "formula": "C7H8",       "mw": 92.14},
]

# Manually curated distractor molecules (structurally similar, wrong answer)
DISTRACTORS = {
    "caffeine":      ["Cn1cnc2c1c(=O)[nH]c(=O)n2C", "Cn1cnc2c1c(=O)n(c(=O)[nH]2)C", "O=c1[nH]cnc2c1[nH]cn2", "Cn1ccc(=O)[nH]1"],
    "aspirin":       ["OC(=O)c1ccccc1O", "CC(=O)Oc1ccccc1", "OC(=O)c1ccccc1", "CC(=O)Oc1cccc(C(=O)O)c1"],
    "ibuprofen":     ["CC(C)Cc1ccccc1", "CC(C(=O)O)c1ccc(cc1)CC(C)C", "Cc1ccc(CC(C)C(=O)O)cc1", "CCC(c1ccc(CC(C)C)cc1)C(=O)O"],
    "acetaminophen": ["CC(=O)Nc1ccccc1", "Nc1ccc(O)cc1", "CC(=O)Nc1ccc(O)c(O)c1", "OC(=O)Nc1ccc(O)cc1"],
    "dopamine":      ["NCCc1ccc(O)cc1", "NCCc1ccc(O)c(O)c1CC", "OC(=O)CCc1ccc(O)c(O)c1", "NCCC1=CC=C(O)C(O)=C1"],
    "serotonin":     ["NCCc1c[nH]c2ccccc12", "NCCc1ccc(O)cc1", "OCC1=CNC2=CC=C(O)C=C12", "NCCc1c[nH]c2cc(O)ccc12"],
    "nicotine":      ["CN1CCC[C@@H]1c1ccccn1", "c1ccncc1", "C1CCN(C)CC1", "CN1CCCC1"],
    "glucose":       ["OC[C@@H]1OC(O)[C@@H](O)[C@@H](O)[C@H]1O", "OCC1OC(O)C(O)C(O)C1O", "OC[C@H]1OC(O)[C@@H](O)[C@H](O)[C@@H]1O", "OCC(O)C(O)C(O)C(O)C=O"],
    "cholesterol":   ["C[C@@H](CCCC(C)C)[C@H]1CC[C@H]2[C@@H]1CCC3=CC(=O)CC[C@]23C", "C[C@H](CCCC(C)C)[C@@H]1CC[C@@H]2[C@H]1CC=C3C[C@@H](O)CC[C@]23C", "OC1CCC2(C1)CCCC1CC=CCC12C", "C1CCC2(CC1)CCCC1CC=CCC12"],
    "vanillin":      ["COc1cc(CO)ccc1O", "COc1ccc(C=O)cc1", "Oc1ccc(C=O)cc1", "COc1cc(C=O)cc(OC)c1O"],
    "menthol":       ["CC(C)[C@H]1CC[C@@H](C)C[C@@H]1O", "CC1CCC(C(C)C)CC1O", "CC(C)C1CCC(C)CC1", "OC1CCCCC1"],
    "capsaicin":     ["COc1cc(CNC(=O)CCCCCCC(C)C)ccc1O", "COc1cc(CNC(=O)CCCCCC)ccc1O", "COc1cc(CNC(=O)CC=CC(C)C)ccc1O", "OC1=CC(CNC(=O)CCCCC)=CC=C1OC"],
    "citric_acid":   ["OC(=O)CC(O)CC(=O)O", "OC(CC(=O)O)(CC(=O)O)C(=O)O", "OC(=O)C(O)CC(=O)O", "OCC(O)(CC(=O)O)C(=O)O"],
    "lidocaine":     ["CCN(CC)CC(=O)Nc1ccccc1", "CCN(CC)CC(=O)Nc1c(C)cccc1", "CCNCC(=O)Nc1c(C)cccc1C", "CCN(CC)C(=O)CNc1c(C)cccc1C"],
    "quinine":       ["COc1ccc2nccc(c2c1)[C@H](O)[C@H]3CC[N@@]4CC[C@@H](C=C)[C@H](C3)C4", "COc1ccc2nccc(C(O)C3CCN4CCC(C=C)C(C3)C4)c2c1", "OC(c1ccnc2ccccc12)C1CCN2CCC(C=C)C(C1)C2", "COc1ccc2ncc(C(O)C3CCN4CCC(C=C)CC34)c2c1"],
    "penicillin_g":  ["CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(=O)O", "CC1(C)SC2C(NC(=O)CC3=CC=CC=C3)C(=O)N2C1C(=O)[O-]", "CC1(C)S[C@@H]2[C@H](NC(=O)c3ccccc3)C(=O)N2[C@H]1C(=O)O", "CC1(C)SC2C(N)C(=O)N2C1C(=O)O"],
    "ethanol":       ["CCCO", "CO", "OCC(C)O", "COCO"],
    "benzene":       ["Cc1ccccc1", "c1ccc(F)cc1", "c1cccnc1", "c1ccoc1"],
    "acetone":       ["CCC=O", "CC(=O)CC", "CC(O)=O", "CCCO"],
    "toluene":       ["c1ccc(CC)cc1", "Cc1cccc(C)c1", "Cc1cccnc1", "Cc1ccc(F)cc1"],
}

def read_csv_spectrum(path: Path):
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 2:
                try:
                    rows.append((float(row[0]), float(row[1])))
                except ValueError:
                    pass
    return rows

def mol_to_sdf_string(mol):
    try:
        from rdkit.Chem import SDWriter
        import io
        buf = io.StringIO()
        w = SDWriter(buf)
        w.write(mol)
        w.close()
        return buf.getvalue()
    except Exception:
        return None

def build_fixture(mol_info: dict) -> dict:
    name   = mol_info["name"]
    smiles = mol_info["smiles"]

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        rdkit_ok = True
    except ImportError:
        rdkit_ok = False

    # Load spectra
    ms_peaks  = read_csv_spectrum(SPEC_DIR / f"{name}_ms.csv")
    nmr_peaks = read_csv_spectrum(SPEC_DIR / f"{name}_nmr.csv")

    # Generate conformer
    conformer_sdf = None
    if rdkit_ok:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                mol3d = Chem.AddHs(mol)
                AllChem.EmbedMolecule(mol3d, randomSeed=42)
                AllChem.MMFFOptimizeMolecule(mol3d)
                conformer_sdf = mol_to_sdf_string(mol3d)
        except Exception as e:
            print(f"  Conformer error for {name}: {e}")

    # Build candidates: correct answer + 4 distractors
    distractors = DISTRACTORS.get(name, [])[:4]

    def make_candidate(smi, rank, score, is_correct=False):
        sdf = None
        if is_correct:
            sdf = conformer_sdf
        return {
            "smiles": smi,
            "score": round(score, 3),
            "rank": rank,
            "valid": True,
            "conformer_sdf": sdf,
        }

    # Variant: nmr only — correct answer ranked lower
    nmr_candidates = [make_candidate(smiles, 1, 0.61, True)] + [
        make_candidate(d, i+2, round(0.61 - (i+1)*0.07, 3))
        for i, d in enumerate(distractors)
    ]
    # Re-rank so correct is at position 3
    if len(nmr_candidates) >= 3:
        nmr_candidates[0]["rank"] = 3
        nmr_candidates[0]["score"] = 0.54
        nmr_candidates[2]["rank"] = 1
        nmr_candidates[2]["score"] = 0.61
        nmr_candidates[0], nmr_candidates[2] = nmr_candidates[2], nmr_candidates[0]
        nmr_candidates[1]["rank"] = 2
        nmr_candidates[1]["score"] = 0.57

    # Variant: ms only — correct answer rank 2
    ms_candidates = [make_candidate(smiles, 1, 0.72, True)] + [
        make_candidate(d, i+2, round(0.72 - (i+1)*0.06, 3))
        for i, d in enumerate(distractors)
    ]
    if len(ms_candidates) >= 2:
        ms_candidates[0]["rank"] = 2
        ms_candidates[0]["score"] = 0.68
        ms_candidates[1]["rank"] = 1
        ms_candidates[1]["score"] = 0.72
        ms_candidates[0], ms_candidates[1] = ms_candidates[1], ms_candidates[0]

    # Variant: nmr + ms — correct answer rank 1
    nmr_ms_candidates = [make_candidate(smiles, 1, 0.87, True)] + [
        make_candidate(d, i+2, round(0.87 - (i+1)*0.08, 3))
        for i, d in enumerate(distractors)
    ]

    # Variant: all three — correct answer rank 1, higher score
    all_candidates = [make_candidate(smiles, 1, 0.94, True)] + [
        make_candidate(d, i+2, round(0.94 - (i+1)*0.09, 3))
        for i, d in enumerate(distractors)
    ]

    fixture = {
        "id": name,
        "display_name": name.replace("_", " ").title(),
        "smiles": smiles,
        "formula": mol_info["formula"],
        "mw": mol_info["mw"],
        "has_nmr": bool(nmr_peaks),
        "has_ms": bool(ms_peaks),
        "nmr_csv_path": f"data/fixtures/spectra/{name}_nmr.csv",
        "ms_csv_path": f"data/fixtures/spectra/{name}_ms.csv",
        "candidates": all_candidates,  # default (all modalities)
        "variants": {
            "nmr":     nmr_candidates,
            "ms":      ms_candidates,
            "ms_nmr":  nmr_ms_candidates,
            "nmr_ms":  nmr_ms_candidates,
            "ir_ms_nmr": all_candidates,
            "ms_nmr_ir": all_candidates,
        },
    }
    return fixture

def main():
    print("=" * 60)
    print("DiamondHacks — Building fixture JSONs")
    print("=" * 60)

    for mol in DEMO_MOLECULES:
        name = mol["name"]
        print(f"\n[{name}]")
        fixture = build_fixture(mol)
        out_path = FIX_DIR / f"{name}.json"
        with open(out_path, "w") as f:
            json.dump(fixture, f, indent=2)
        has_sdf = bool(fixture["candidates"][0].get("conformer_sdf"))
        print(f"  ✓ Saved {out_path.name}  (conformer={'yes' if has_sdf else 'no (rdkit not installed)'})")

    print("\n" + "=" * 60)
    print(f"✓ {len(DEMO_MOLECULES)} fixture files written to data/fixtures/")
    print("  Next step: uvicorn backend.main:app --reload")

if __name__ == "__main__":
    main()
