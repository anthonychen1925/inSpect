"""
Extract peak data from spectrum images (JPG/PNG).
Converts a photo/screenshot of an NMR or MS spectrum into (x, y) peak lists.
"""
import io
import base64
import numpy as np
from PIL import Image
from scipy.signal import find_peaks


def image_bytes_to_peaks(
    img_bytes: bytes,
    spectrum_type: str = "nmr",
) -> list[tuple[float, float]]:
    """
    Extract peaks from a spectrum image.

    Args:
        img_bytes: Raw image bytes (JPG/PNG).
        spectrum_type: "nmr" or "ms" — determines x-axis scaling.

    Returns:
        List of (x_value, intensity) tuples.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")  # grayscale
    arr = np.array(img, dtype=np.float64)

    # Invert: dark lines on white bg → high values = signal
    # Also handle white lines on dark bg by checking which is dominant
    mean_val = arr.mean()
    if mean_val > 128:
        # White background — invert so peaks are high
        arr = 255.0 - arr
    # else: dark background, peaks already bright

    # Collapse vertically: for each x column, take the max intensity
    # This captures the spectrum trace regardless of where it sits vertically
    profile = arr.max(axis=0)

    # Smooth with a simple moving average to reduce noise
    kernel_size = max(3, len(profile) // 100)
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(profile, kernel, mode="same")

    # Normalize to 0-200 range
    p_min, p_max = smoothed.min(), smoothed.max()
    if p_max - p_min < 1:
        return []
    normalized = (smoothed - p_min) / (p_max - p_min) * 200.0

    # Find peaks
    height_threshold = 20.0  # minimum intensity to count
    distance = max(5, len(normalized) // 50)  # minimum distance between peaks
    peak_indices, properties = find_peaks(
        normalized,
        height=height_threshold,
        distance=distance,
        prominence=10.0,
    )

    if len(peak_indices) == 0:
        return []

    # Map pixel x-positions to spectrum x-values
    width = len(normalized)
    if spectrum_type == "nmr":
        # NMR: typically 0-14 ppm, displayed right-to-left
        x_min, x_max = 0.0, 14.0
        x_values = x_max - (peak_indices / width) * (x_max - x_min)
    else:
        # MS: typically 0-500 m/z, displayed left-to-right
        x_min, x_max = 0.0, 500.0
        x_values = (peak_indices / width) * (x_max - x_min)

    peaks = []
    for x_val, idx in zip(x_values, peak_indices):
        intensity = float(normalized[idx])
        peaks.append((round(float(x_val), 2), round(intensity, 1)))

    # Sort by x value
    peaks.sort(key=lambda p: p[0])
    return peaks


def base64_image_to_peaks(
    b64_data: str,
    spectrum_type: str = "nmr",
) -> list[tuple[float, float]]:
    """Decode base64 image and extract peaks."""
    img_bytes = base64.b64decode(b64_data)
    return image_bytes_to_peaks(img_bytes, spectrum_type)
