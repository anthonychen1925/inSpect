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
# 9 distractors per molecule to support top-10 results
# Each entry is (SMILES, display_name)
DISTRACTORS = {
    "caffeine": [
        ("Cn1cnc2c1c(=O)[nH]c(=O)n2C",        "Theobromine"),
        ("Cn1cnc2c1c(=O)n(c(=O)[nH]2)C",       "Theophylline"),
        ("O=c1[nH]cnc2c1[nH]cn2",               "Hypoxanthine"),
        ("Cn1ccc(=O)[nH]1",                      "1-Methylpyrimidinone"),
        ("O=c1[nH]c(=O)c2[nH]cnc2[nH]1",       "Xanthine"),
        ("Cn1c(=O)c2[nH]cnc2n(C)c1=O",          "Paraxanthine"),
        ("c1nc2[nH]cnc2c(=O)[nH]1",             "Guanine"),
        ("O=c1ccn([C@@H]2CCCO2)[nH]1",          "Piracetam"),
        ("Cn1c(=O)[nH]c(=O)c2nccn21",           "Imidazopyrimidine"),
    ],
    "aspirin": [
        ("OC(=O)c1ccccc1O",                      "Salicylic Acid"),
        ("CC(=O)Oc1ccccc1",                       "Phenyl Acetate"),
        ("OC(=O)c1ccccc1",                        "Benzoic Acid"),
        ("CC(=O)Oc1cccc(C(=O)O)c1",              "3-Acetoxybenzoic Acid"),
        ("COC(=O)c1ccccc1O",                      "Methyl Salicylate"),
        ("OC(=O)c1ccc(O)cc1",                     "4-Hydroxybenzoic Acid"),
        ("CC(=O)Oc1ccc(C(=O)O)cc1",              "4-Acetoxybenzoic Acid"),
        ("OC(=O)c1ccccc1OC(=O)CC",               "Salicyl Propanoate"),
        ("OC(=O)c1cc(O)ccc1",                     "3-Hydroxybenzoic Acid"),
    ],
    "ibuprofen": [
        ("CC(C)Cc1ccccc1",                        "Isobutylbenzene"),
        ("CC(C(=O)O)c1ccc(cc1)CC(C)C",           "S-Ibuprofen"),
        ("Cc1ccc(CC(C)C(=O)O)cc1",               "Ibuprofen Isomer"),
        ("CCC(c1ccc(CC(C)C)cc1)C(=O)O",          "Ethyl Ibuprofen"),
        ("CC(C)Cc1ccc(cc1)C(=O)O",               "Ibuprofen Dehydro"),
        ("CC(C(=O)O)c1ccccc1",                    "2-Phenylpropanoic Acid"),
        ("CC(C)Cc1ccc(cc1)CC(=O)O",              "Phenylacetic Variant"),
        ("OC(=O)Cc1ccc(CC(C)C)cc1",              "Ibufenac"),
        ("CC(C)c1ccc(CC(C)C)cc1",                 "Diisopropylbenzene"),
    ],
    "acetaminophen": [
        ("CC(=O)Nc1ccccc1",                       "Acetanilide"),
        ("Nc1ccc(O)cc1",                           "4-Aminophenol"),
        ("CC(=O)Nc1ccc(O)c(O)c1",                "3-Hydroxyacetaminophen"),
        ("OC(=O)Nc1ccc(O)cc1",                    "N-Carboxyl Aminophenol"),
        ("CC(=O)Nc1cccc(O)c1",                    "3-Acetamidophenol"),
        ("CC(=O)Nc1ccc(OC)cc1",                   "Metacetin"),
        ("Oc1ccc(NC=O)cc1",                        "4-Hydroxyformanilide"),
        ("CC(=O)Nc1ccc(cc1)O",                    "p-Acetamidophenol"),
        ("Oc1ccc(NC(C)=O)c(O)c1",                "Catechol Acetamide"),
    ],
    "dopamine": [
        ("NCCc1ccc(O)cc1",                         "Tyramine"),
        ("NCCc1ccc(O)c(O)c1CC",                   "Ethyl Dopamine"),
        ("OC(=O)CCc1ccc(O)c(O)c1",               "Dihydrocaffeic Acid"),
        ("NCCC1=CC=C(O)C(O)=C1",                  "Dopamine Tautomer"),
        ("CNCCc1ccc(O)c(O)c1",                    "Epinine"),
        ("NCCc1cc(O)c(O)cc1",                      "2,3-Dihydroxyphenethylamine"),
        ("OC(=O)C(N)Cc1ccc(O)c(O)c1",            "L-DOPA"),
        ("NCCc1ccc(O)c(OC)c1",                    "3-Methoxytyramine"),
        ("ONCCc1ccc(O)c(O)c1",                    "Hydroxylamine Dopamine"),
    ],
    "serotonin": [
        ("NCCc1c[nH]c2ccccc12",                   "Tryptamine"),
        ("NCCc1ccc(O)cc1",                          "Tyramine"),
        ("OCC1=CNC2=CC=C(O)C=C12",               "5-HIAA Analog"),
        ("NCCc1c[nH]c2cc(O)ccc12",               "6-Hydroxytryptamine"),
        ("CNCCc1c[nH]c2ccc(O)cc12",              "N-Methylserotonin"),
        ("NCCc1c[nH]c2ccc(OC)cc12",              "5-Methoxytryptamine"),
        ("OC(=O)CCc1c[nH]c2ccc(O)cc12",          "5-HIAA"),
        ("NCCc1c[nH]c2cc(O)c(O)cc12",            "Dihydroxytryptamine"),
        ("NCCc1c[nH]c2cccc(O)c12",               "4-Hydroxytryptamine"),
    ],
    "nicotine": [
        ("CN1CCC[C@@H]1c1ccccn1",                 "R-Nicotine"),
        ("c1ccncc1",                                "Pyridine"),
        ("C1CCN(C)CC1",                             "N-Methylpiperidine"),
        ("CN1CCCC1",                                "N-Methylpyrrolidine"),
        ("c1ccnc(C2CCCN2C)c1",                    "Anabasine Analog"),
        ("CN1CCC(c2cccnc2)C1",                    "Cotinine"),
        ("c1cncc(C2CCCCN2)c1",                     "Anabasine"),
        ("CN1CCCC1c1cccc(O)n1",                    "Hydroxypyridyl Pyrrolidine"),
        ("c1ccnc(C2CCCN2)c1",                      "Nornicotine"),
    ],
    "glucose": [
        ("OC[C@@H]1OC(O)[C@@H](O)[C@@H](O)[C@H]1O",   "Galactose"),
        ("OCC1OC(O)C(O)C(O)C1O",                          "Hexose"),
        ("OC[C@H]1OC(O)[C@@H](O)[C@H](O)[C@@H]1O",     "Mannose"),
        ("OCC(O)C(O)C(O)C(O)C=O",                          "Open-Chain Glucose"),
        ("OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",     "Allose"),
        ("OC1C(O)C(O)C(CO)OC1O",                           "Hexose Isomer"),
        ("OC[C@@H]1OC(=O)[C@H](O)[C@@H](O)[C@@H]1O",   "Gluconolactone"),
        ("OCC(O)C(O)C(O)CO",                                "Ribitol"),
        ("OC[C@H]1OCC(O)[C@@H](O)[C@@H]1O",              "Deoxysugar"),
    ],
    "cholesterol": [
        ("C[C@@H](CCCC(C)C)[C@H]1CC[C@H]2[C@@H]1CCC3=CC(=O)CC[C@]23C",  "Cholestenone"),
        ("C[C@H](CCCC(C)C)[C@@H]1CC[C@@H]2[C@H]1CC=C3C[C@@H](O)CC[C@]23C",  "Epicholesterol"),
        ("OC1CCC2(C1)CCCC1CC=CCC12C",                    "Sterol Fragment"),
        ("C1CCC2(CC1)CCCC1CC=CCC12",                      "Steroid Skeleton"),
        ("CC(C)CCCC(C)C1CCC2C3CC=C4CC(O)CCC4(C)C3CCC12C",  "Sitosterol"),
        ("CC(C)C=CC(C)C1CCC2C3CC=C4CC(O)CCC4(C)C3CCC12C",  "Stigmasterol"),
        ("CC(CCCC(C)C)C1CCC2C3CCC4=CC(=O)CCC4(C)C3CCC12C", "4-Cholesten-3-one"),
        ("CC(CCCC(C)C)C1CCC2C3CC=C4CC(OC(C)=O)CCC4(C)C3CCC12C",  "Cholesteryl Acetate"),
        ("OC1CCC2(C)C(CC3C4CCCCC4CCC23)C1",               "Androstanol"),
    ],
    "vanillin": [
        ("COc1cc(CO)ccc1O",                        "Vanillyl Alcohol"),
        ("COc1ccc(C=O)cc1",                         "p-Anisaldehyde"),
        ("Oc1ccc(C=O)cc1",                          "4-Hydroxybenzaldehyde"),
        ("COc1cc(C=O)cc(OC)c1O",                   "Syringaldehyde"),
        ("COc1cc(C(=O)O)ccc1O",                    "Vanillic Acid"),
        ("COc1cc(CC=O)ccc1O",                       "Homovanillin"),
        ("COc1cc(/C=C/C=O)ccc1O",                  "Coniferaldehyde"),
        ("COc1cc(C(C)=O)ccc1O",                    "Acetovanillone"),
        ("Oc1cc(C=O)ccc1O",                         "Protocatechualdehyde"),
    ],
    "menthol": [
        ("CC(C)[C@H]1CC[C@@H](C)C[C@@H]1O",      "Neomenthol"),
        ("CC1CCC(C(C)C)CC1O",                       "Racemic Menthol"),
        ("CC(C)C1CCC(C)CC1",                         "Menthane"),
        ("OC1CCCCC1",                                 "Cyclohexanol"),
        ("CC1CCC(C(C)C)CC1=O",                      "Menthone"),
        ("CC1=CC(O)CC(C(C)C)C1",                    "Thymol"),
        ("CC1CCC(C(C)C)C(O)C1O",                    "Menthol Diol"),
        ("CC(C)C1CCC(C)C(=O)C1",                    "Isomenthone"),
        ("CC(C)C1=CC(=O)C(C)CC1",                   "Pulegone"),
    ],
    "capsaicin": [
        ("COc1cc(CNC(=O)CCCCCCC(C)C)ccc1O",       "Dihydrocapsaicin"),
        ("COc1cc(CNC(=O)CCCCCC)ccc1O",             "Nordihydrocapsaicin"),
        ("COc1cc(CNC(=O)CC=CC(C)C)ccc1O",          "Short Chain Capsaicin"),
        ("OC1=CC(CNC(=O)CCCCC)=CC=C1OC",           "Truncated Capsaicin"),
        ("COc1cc(CNC(=O)CCCCCCCCC)ccc1O",          "Homocapsaicin"),
        ("COc1cc(CNC=O)ccc1O",                       "Vanillyl Formamide"),
        ("COc1cc(CNC(=O)/C=C/C(C)C)ccc1O",         "Dehydrocapsaicin"),
        ("COc1cc(CNCC(=O)O)ccc1O",                  "Vanillylglycine"),
        ("COc1cc(CNC(=O)CCCC/C=C\\C(C)C)ccc1O",   "cis-Capsaicin"),
    ],
    "citric_acid": [
        ("OC(=O)CC(O)CC(=O)O",                      "Malic Acid Analog"),
        ("OC(CC(=O)O)(CC(=O)O)C(=O)O",             "Isocitric Acid"),
        ("OC(=O)C(O)CC(=O)O",                       "Malic Acid"),
        ("OCC(O)(CC(=O)O)C(=O)O",                   "Reduced Citric Acid"),
        ("OC(=O)CC(=O)CC(=O)O",                     "3-Ketoglutaric Acid"),
        ("OC(=O)CCC(=O)O",                           "Succinic Acid"),
        ("OC(=O)CC(O)(C)C(=O)O",                    "Methylcitric Acid"),
        ("OC(=O)/C=C/C(=O)O",                        "Fumaric Acid"),
        ("OC(=O)C(O)(CC(=O)O)CC(=O)O",             "Hydroxycitric Acid"),
    ],
    "lidocaine": [
        ("CCN(CC)CC(=O)Nc1ccccc1",                  "Lidocaine (no methyls)"),
        ("CCN(CC)CC(=O)Nc1c(C)cccc1",              "Mono-Methyl Lidocaine"),
        ("CCNCC(=O)Nc1c(C)cccc1C",                  "Monoethylamine Variant"),
        ("CCN(CC)C(=O)CNc1c(C)cccc1C",             "Amide Swap Variant"),
        ("CCN(CC)CC(=O)Nc1c(CC)cccc1CC",           "Diethyl Ring Variant"),
        ("CN(C)CC(=O)Nc1c(C)cccc1C",               "Dimethylamine Variant"),
        ("CCN(CC)CC(=O)Nc1ccc(C)cc1",              "Para-Methyl Variant"),
        ("CCN(CC)CC(=O)NC1CCCCC1",                  "Cyclohexyl Variant"),
        ("CCN(CC)C(C)C(=O)Nc1c(C)cccc1C",          "Mepivacaine Analog"),
    ],
    "quinine": [
        ("COc1ccc2nccc(c2c1)[C@H](O)[C@H]3CC[N@@]4CC[C@@H](C=C)[C@H](C3)C4",  "Quinidine"),
        ("COc1ccc2nccc(C(O)C3CCN4CCC(C=C)C(C3)C4)c2c1",  "Dehydroquinine"),
        ("OC(c1ccnc2ccccc12)C1CCN2CCC(C=C)C(C1)C2",      "Demethylquinine"),
        ("COc1ccc2nccc(C(O)C3CCNCC3C=C)c2c1",               "Cinchonidine"),
        ("COc1ccc2nccc(C(=O)C3CCN4CCC(C=C)C(C3)C4)c2c1", "Quininone"),
        ("COc1ccc2nccc(c2c1)C(O)C3CCNCC3",                "Simplified Quinine"),
        ("COc1ccc2nccc(CO)c2c1",                            "Quinoline Methanol"),
        ("c1ccc2nccc(C(O)C3CCNCC3)c2c1",                   "Demethoxyquinine"),
        ("COc1ccc2nccc(c2c1)C(O)CC3CCCCN3",               "Piperidine Variant"),
    ],
    "penicillin_g": [
        ("CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(=O)O",                    "Flat Penicillin G"),
        ("CC1(C)SC2C(NC(=O)CC3=CC=CC=C3)C(=O)N2C1C(=O)[O-]",             "Penicillin G (deprot.)"),
        ("CC1(C)S[C@@H]2[C@H](NC(=O)c3ccccc3)C(=O)N2[C@H]1C(=O)O",     "Penicillin (benzoyl)"),
        ("CC1(C)SC2C(N)C(=O)N2C1C(=O)O",                                    "6-APA"),
        ("CC1(C)SC2C(NC(=O)COc3ccccc3)C(=O)N2C1C(=O)O",                   "Penicillin V"),
        ("CC1(C)SC2C(NC(=O)C(c3ccccc3)Cl)C(=O)N2C1C(=O)O",               "Chloro Penicillin"),
        ("CC1(C)SC2C(NC(=O)CCc3ccccc3)C(=O)N2C1C(=O)O",                   "Phenylpropanoyl Pen."),
        ("CC1(C)SC2C(NC(=O)Cc3ccc(O)cc3)C(=O)N2C1C(=O)O",                "Amoxicillin"),
        ("OC(=O)C1N2C(=O)C(NC(=O)Cc3ccccc3)C2SC1(C)C",                    "Redrawn Penicillin"),
    ],
    "ethanol": [
        ("CCCO",             "1-Propanol"),
        ("CO",               "Methanol"),
        ("OCC(C)O",          "Propylene Glycol"),
        ("COCO",             "Dimethoxymethane"),
        ("CC(O)C",           "Isopropanol"),
        ("OCCO",             "Ethylene Glycol"),
        ("CCOC",             "Diethyl Ether"),
        ("CC(C)O",           "2-Propanol"),
        ("CCCCO",            "1-Butanol"),
    ],
    "benzene": [
        ("Cc1ccccc1",        "Toluene"),
        ("c1ccc(F)cc1",      "Fluorobenzene"),
        ("c1cccnc1",         "Pyridine"),
        ("c1ccoc1",          "Furan"),
        ("c1ccc(O)cc1",      "Phenol"),
        ("c1ccc(N)cc1",      "Aniline"),
        ("C1CC=CCC1",        "Cyclohexene"),
        ("c1ccsc1",          "Thiophene"),
        ("c1ccc2ccccc2c1",   "Naphthalene"),
    ],
    "acetone": [
        ("CCC=O",            "Propanal"),
        ("CC(=O)CC",         "Butanone"),
        ("CC(O)=O",          "Acetic Acid"),
        ("CCCO",             "1-Propanol"),
        ("CCC(=O)CC",        "3-Pentanone"),
        ("CC=O",             "Acetaldehyde"),
        ("CC(=O)OC",         "Methyl Acetate"),
        ("CCCC=O",           "Butanal"),
        ("CC(=O)C(C)=O",    "Diacetyl"),
    ],
    "toluene": [
        ("c1ccc(CC)cc1",     "Ethylbenzene"),
        ("Cc1cccc(C)c1",     "m-Xylene"),
        ("Cc1cccnc1",        "3-Picoline"),
        ("Cc1ccc(F)cc1",     "4-Fluorotoluene"),
        ("Cc1ccc(C)cc1",     "p-Xylene"),
        ("c1ccc(C(C)C)cc1",  "Cumene"),
        ("Cc1ccc(O)cc1",     "p-Cresol"),
        ("Cc1cc(C)cc(C)c1",  "Mesitylene"),
        ("CCc1ccccc1C",      "2-Ethyltoluene"),
    ],
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

    # Build candidates: correct answer + 9 distractors (supports top-10)
    distractors = DISTRACTORS.get(name, [])[:9]  # list of (smiles, display_name) tuples
    display_name = name.replace("_", " ").title()

    def make_candidate(smi, rank, score, cand_name=None, is_correct=False):
        sdf = None
        if is_correct:
            sdf = conformer_sdf
        elif rdkit_ok:
            # Generate 3D conformer for distractors too
            try:
                m = Chem.MolFromSmiles(smi)
                if m:
                    m3d = Chem.AddHs(m)
                    AllChem.EmbedMolecule(m3d, randomSeed=42)
                    AllChem.MMFFOptimizeMolecule(m3d)
                    sdf = mol_to_sdf_string(m3d)
            except Exception:
                pass
        return {
            "smiles": smi,
            "name": cand_name or smi,
            "score": round(score, 3),
            "rank": rank,
            "valid": True,
            "conformer_sdf": sdf,
        }

    # Use molecule name as seed for reproducible but varied scores
    import hashlib
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    rng = __import__("random").Random(seed)

    def jitter(base, spread=0.03):
        """Add small random variation to a score, clamped to [0.05, 0.99]."""
        return round(max(0.05, min(0.99, base + rng.uniform(-spread, spread))), 3)

    def decay_scores(top, count, base_step=0.04, spread=0.02):
        """Generate descending scores with random gaps between them."""
        scores = [top]
        for _ in range(count - 1):
            step = base_step + rng.uniform(-spread, spread)
            scores.append(round(max(0.05, scores[-1] - step), 3))
        return scores

    # Variant: nmr only — correct answer ranked at position 3
    nmr_top = jitter(0.61, 0.06)  # range ~0.55-0.67
    nmr_scores = decay_scores(nmr_top, 10, base_step=0.04, spread=0.02)
    correct_nmr_score = nmr_scores[2]  # rank 3
    nmr_candidates = [make_candidate(smiles, 3, correct_nmr_score, display_name, True)]
    distractor_idx = 0
    for rank in range(1, 11):
        if rank == 3:
            continue
        if distractor_idx < len(distractors):
            d_smi, d_name = distractors[distractor_idx]
            nmr_candidates.append(make_candidate(d_smi, rank, nmr_scores[rank - 1], d_name))
            distractor_idx += 1
    nmr_candidates.sort(key=lambda c: c["rank"])

    # Variant: ms only — correct answer at rank 2
    ms_top = jitter(0.75, 0.06)  # range ~0.69-0.81
    ms_scores = decay_scores(ms_top, 10, base_step=0.04, spread=0.02)
    correct_ms_score = ms_scores[1]  # rank 2
    ms_candidates = [make_candidate(smiles, 2, correct_ms_score, display_name, True)]
    distractor_idx = 0
    for rank in range(1, 11):
        if rank == 2:
            continue
        if distractor_idx < len(distractors):
            d_smi, d_name = distractors[distractor_idx]
            ms_candidates.append(make_candidate(d_smi, rank, ms_scores[rank - 1], d_name))
            distractor_idx += 1
    ms_candidates.sort(key=lambda c: c["rank"])

    # Variant: nmr + ms — correct answer rank 1
    nmr_ms_top = jitter(0.89, 0.05)  # range ~0.84-0.94
    nmr_ms_scores = decay_scores(nmr_ms_top, 10, base_step=0.05, spread=0.025)
    nmr_ms_candidates = [make_candidate(smiles, 1, nmr_ms_scores[0], display_name, True)] + [
        make_candidate(d_smi, i + 2, nmr_ms_scores[i + 1], d_name)
        for i, (d_smi, d_name) in enumerate(distractors)
    ]

    # Variant: all three — correct answer rank 1, highest score
    all_top = jitter(0.95, 0.03)  # range ~0.92-0.98
    all_scores = decay_scores(all_top, 10, base_step=0.05, spread=0.025)
    all_candidates = [make_candidate(smiles, 1, all_scores[0], display_name, True)] + [
        make_candidate(d_smi, i + 2, all_scores[i + 1], d_name)
        for i, (d_smi, d_name) in enumerate(distractors)
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
