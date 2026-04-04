import numpy as np

def bin_spectrum(
    axis: np.ndarray,
    intensity: np.ndarray,
    axis_min: float,
    axis_max: float,
    n_bins: int,
    normalize: bool = True,
    log_transform: bool = False,
) -> np.ndarray:
    """Bin a spectrum into a fixed-length float32 vector."""
    result = np.zeros(n_bins, dtype=np.float32)
    if len(axis) == 0:
        return result

    if log_transform:
        intensity = np.log1p(intensity.astype(np.float64)).astype(np.float32)

    for x, y in zip(axis, intensity):
        if axis_min <= x < axis_max:
            idx = int((x - axis_min) / (axis_max - axis_min) * n_bins)
            idx = min(idx, n_bins - 1)
            result[idx] = max(result[idx], y)

    if normalize and result.max() > 0:
        result = result / result.max()

    return result.astype(np.float32)
