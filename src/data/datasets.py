import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path

class SpectroscopyDataset(Dataset):
    def __init__(self, data_dir: str):
        self.files = sorted(Path(data_dir).glob("*.npz"))

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        d = np.load(self.files[idx], allow_pickle=True)
        nmr = torch.FloatTensor(d.get("nmr_binned", np.zeros(1024))).unsqueeze(0)
        ms  = torch.FloatTensor(d.get("ms_binned",  np.zeros(2048))).unsqueeze(0)
        ir  = torch.FloatTensor(d.get("ir_binned",  np.zeros(2048))).unsqueeze(0)
        nmr_mask = bool(d.get("has_nmr", False))
        ms_mask  = bool(d.get("has_ms",  False))
        ir_mask  = bool(d.get("has_ir",  False))
        return {
            "nmr": nmr, "ms": ms, "ir": ir,
            "nmr_mask": nmr_mask, "ms_mask": ms_mask, "ir_mask": ir_mask,
            "fingerprint": torch.FloatTensor(d.get("fingerprint", np.zeros(2048))),
            "smiles": str(d.get("smiles", "")),
        }
