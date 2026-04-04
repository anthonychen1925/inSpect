from typing import Optional
import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors
    from rdkit.Chem import rdMolDescriptors
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

FUNCTIONAL_GROUP_SMARTS = [
    ("carbonyl",        "[CX3]=[OX1]"),
    ("carboxylic_acid", "[CX3](=O)[OX2H1]"),
    ("ester",           "[CX3](=O)[OX2][CX4]"),
    ("amide",           "[CX3](=O)[NX3]"),
    ("amine_primary",   "[NX3;H2]"),
    ("amine_secondary", "[NX3;H1]"),
    ("amine_tertiary",  "[NX3;H0]"),
    ("hydroxyl",        "[OX2H]"),
    ("nitro",           "[NX3](=O)=O"),
    ("nitrile",         "[NX1]#[CX2]"),
    ("aromatic",        "c1ccccc1"),
    ("halogen_F",       "[F]"),
    ("halogen_Cl",      "[Cl]"),
    ("halogen_Br",      "[Br]"),
    ("halogen_I",       "[I]"),
    ("ether",           "[OD2]([#6])[#6]"),
    ("aldehyde",        "[CX3H1](=O)"),
    ("ketone",          "[CX3](=O)[#6]"),
    ("thiol",           "[SX2H]"),
    ("sulfide",         "[SX2]([#6])[#6]"),
]
N_FG = len(FUNCTIONAL_GROUP_SMARTS)

def smiles_to_mol(smiles: str) -> Optional["Chem.Mol"]:
    if not RDKIT_AVAILABLE:
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        return mol
    except Exception:
        return None

def generate_conformers(mol, n_conformers: int = 10, ff: str = "MMFF94",
                        prune_rms_thresh: float = 0.5, random_seed: int = 42):
    if not RDKIT_AVAILABLE or mol is None:
        return None
    try:
        mol = Chem.AddHs(mol)
        cids = AllChem.EmbedMultipleConfs(
            mol,
            numConfs=n_conformers,
            randomSeed=random_seed,
            pruneRmsThresh=prune_rms_thresh,
        )
        if not cids:
            return None
        if ff == "MMFF94":
            AllChem.MMFFOptimizeMoleculeConfs(mol)
        else:
            AllChem.UFFOptimizeMoleculeConfs(mol)
        return mol
    except Exception:
        return None

def mol_to_sdf_string(mol) -> Optional[str]:
    if not RDKIT_AVAILABLE or mol is None:
        return None
    try:
        import io
        buf = io.StringIO()
        w = Chem.SDWriter(buf)
        w.write(mol)
        w.close()
        return buf.getvalue()
    except Exception:
        return None

def get_morgan_fingerprint(mol, radius: int = 2, n_bits: int = 2048) -> np.ndarray:
    if not RDKIT_AVAILABLE or mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    return np.array(fp, dtype=np.float32)

def get_functional_groups(mol) -> np.ndarray:
    vec = np.zeros(N_FG, dtype=np.float32)
    if not RDKIT_AVAILABLE or mol is None:
        return vec
    for i, (_, smarts) in enumerate(FUNCTIONAL_GROUP_SMARTS):
        patt = Chem.MolFromSmarts(smarts)
        if patt and mol.HasSubstructMatch(patt):
            vec[i] = 1.0
    return vec

def tanimoto_similarity(fp1: np.ndarray, fp2: np.ndarray) -> float:
    intersection = np.dot(fp1, fp2)
    union = np.sum(fp1) + np.sum(fp2) - intersection
    return float(intersection / union) if union > 0 else 0.0
