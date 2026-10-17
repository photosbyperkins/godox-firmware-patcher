#!/usr/bin/env python3
"""
Core detection and patching engine for the Godox Custom Firmware Patcher.

Wraps the per-model `patch.py` scripts and `tools/fwversion.py` so both the
GUI drag-and-drop application and CLI mode share a single source of truth
for SHA-256 verification, model metadata, and binary generation.
"""

from dataclasses import dataclass
import hashlib
import importlib.util
import os
import sys
from typing import Dict, List, Optional, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import fwversion  # noqa: E402


MODELS_DIRNAME = "models"


def get_bundle_root() -> str:
    """Return the repo root (or PyInstaller _MEIPASS), which contains models/<model_id>/patch.py."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.abspath(os.path.join(TOOLS_DIR, ".."))


@dataclass(frozen=True)
class TierOption:
    tier_key: str          # e.g. "S", "R", "X", "R+", "X+"
    tier_code: int         # e.g. 1..5
    name: str              # e.g. "Studio", "Recovery", "Super"
    version_str: str       # e.g. "1.08.02"
    display_version: str   # e.g. "1.08.02" or "V1.05.02" (as shown on strobe LCD)
    output_filename: str   # e.g. "AD600PROII_v1.08.02_recovery.bin"
    expected_sha256: str   # Verified target SHA-256 of the patched image
    summary: str           # Concise 1-line modification summary
    details: str           # Short protection tag


@dataclass(frozen=True)
class ModelSpec:
    model_id: str          # Directory under models/, e.g. "AD600ProII"
    display_name: str      # e.g. "Godox AD600Pro II"
    category: str          # e.g. "600Ws Studio Strobe"
    oem_filename: str      # e.g. "AD600PROII_v1.08.bin"
    v_prefix: str          # "v" or "V" used in output filename
    godox_version: Tuple[int, int]
    expected_size: int
    expected_sha256: str
    hardware_notes: str
    tiers: Tuple[TierOption, ...]

    @property
    def base_version_display(self) -> str:
        return f"{self.v_prefix}{fwversion.godox_version(*self.godox_version)}"


# Verified model & tier specifications. Hashes must match the output of
# models/<model_id>/patch.py and the tables in models/<model_id>/README.md.
MODEL_SPECS: Tuple[ModelSpec, ...] = (
    ModelSpec(
        model_id="AD600ProII",
        display_name="Godox AD600Pro II",
        category="600Ws Flagship Strobe",
        oem_filename="AD600PROII_v1.08.bin",
        v_prefix="v",
        godox_version=(1, 8),
        expected_size=407384,
        expected_sha256="33e327457bef0023af5254153a990a572c6a3afeb792fdb84e5bf137613bf910",
        hardware_notes="Active internal fan · Physical NTC overheat sensors active",
        tiers=(
            TierOption(
                tier_key="S",
                tier_code=1,
                name="Studio",
                version_str="1.08.01",
                display_version="1.08.01",
                output_filename="AD600PROII_v1.08.01_studio.bin",
                expected_sha256="d85d22f05b84e5d259250da3c618f776e340f75d4f98dce922cc91f6c56c62ab",
                summary="Continuous high-speed fan · Factory burst & cooldown limits",
                details="Stock limits",
            ),
            TierOption(
                tier_key="R",
                tier_code=2,
                name="Recovery",
                version_str="1.08.02",
                display_version="1.08.02",
                output_filename="AD600PROII_v1.08.02_recovery.bin",
                expected_sha256="d51033cc1dd911764b9995ef81dee7e449ab8db6ef3c2886c7c414c386ee63de",
                summary="Continuous high-speed fan · 2× faster cooldown between bursts",
                details="2× pause recovery",
            ),
            TierOption(
                tier_key="X",
                tier_code=3,
                name="Super",
                version_str="1.08.03",
                display_version="1.08.03",
                output_filename="AD600PROII_v1.08.03_super.bin",
                expected_sha256="a9b4b0f5fc18a44d1e0af5a1e03db9da199fabfdcc4737c6a7f8f734cd780d27",
                summary="Continuous fan · 2× faster cooldown · +25% more HSS burst shots (64 → 80)",
                details="+25% HSS burst",
            ),
            TierOption(
                tier_key="R+",
                tier_code=4,
                name="Recovery+",
                version_str="1.08.04",
                display_version="1.08.04",
                output_filename="AD600PROII_v1.08.04_recovery_plus.bin",
                expected_sha256="69b27c2789c9604db6aa6bab507e02303f3fb3f07c308076b1c17eb11a849114",
                summary="Continuous fan · 2× faster recovery on both primary & pre-throttle counters",
                details="2× dual recovery",
            ),
            TierOption(
                tier_key="X+",
                tier_code=5,
                name="Super+",
                version_str="1.08.05",
                display_version="1.08.05",
                output_filename="AD600PROII_v1.08.05_super_plus.bin",
                expected_sha256="c62e16a60bee7cf534469e19dfc6acf21f821b7c3ecc570063099c58e2e0109e",
                summary="Continuous fan · 2× recovery · +25% HSS shots · 38-shot mid-burst delay removed",
                details="Max performance",
            ),
        ),
    ),
    ModelSpec(
        model_id="AD200ProII",
        display_name="Godox AD200Pro II",
        category="200Ws Modular Pocket Strobe",
        oem_filename="AD200ProII_V1.05.bin",
        v_prefix="V",
        godox_version=(1, 5),
        expected_size=387248,
        expected_sha256="30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b",
        hardware_notes="Drives H200 II fresnel head fan continuously · Physical NTC overheat sensors active",
        tiers=(
            TierOption(
                tier_key="S",
                tier_code=1,
                name="Studio",
                version_str="1.05.01",
                display_version="V1.05.01",
                output_filename="AD200ProII_V1.05.01_studio.bin",
                expected_sha256="c26d91f59f85217474ab1e1b828e17f5370646c48621036a937aaea1394e9292",
                summary="Continuous H200 II head fan · Factory burst & cooldown limits",
                details="Stock limits",
            ),
            TierOption(
                tier_key="R",
                tier_code=2,
                name="Recovery",
                version_str="1.05.02",
                display_version="V1.05.02",
                output_filename="AD200ProII_V1.05.02_recovery.bin",
                expected_sha256="716b0048a784891858047c433d83c191b0442f00421ff034a222cdddb2b80c86",
                summary="Continuous H200 II fan · 2× faster cooldown between bursts (all heads)",
                details="2× pause recovery",
            ),
            TierOption(
                tier_key="X",
                tier_code=3,
                name="Super",
                version_str="1.05.03",
                display_version="V1.05.03",
                output_filename="AD200ProII_V1.05.03_super.bin",
                expected_sha256="f4aacd86f89d2de6ba4128b883f3e85b0c85aab3b1986e5378fc2722be86f1b3",
                summary="Continuous H200 II fan · 2× faster cooldown · +25% more HSS burst shots",
                details="+25% HSS burst",
            ),
        ),
    ),
    ModelSpec(
        model_id="AD100ProII",
        display_name="Godox AD100Pro II",
        category="100Ws Pocket Round-Head Strobe",
        oem_filename="AD100ProII_RF433V1_07.bin",
        v_prefix="V",
        godox_version=(1, 7),
        expected_size=357004,
        expected_sha256="5dd2dd434e0ca531a57fd5ad397a9de1cf4e8acf2374aa6bfc5d7fed17c135dc",
        hardware_notes="Active internal cooling fan · Physical NTC overheat sensor active",
        tiers=(
            TierOption(
                tier_key="S",
                tier_code=1,
                name="Studio",
                version_str="1.07.01",
                display_version="1.07.01",
                output_filename="AD100ProII_V1.07.01_studio.bin",
                expected_sha256="8995f2b85fe0380282913d4d0697b7d3709d457b68257f6df2d57aec6eb55cc2",
                summary="Continuous cooling fan · Factory burst & cooldown limits",
                details="Stock limits",
            ),
            TierOption(
                tier_key="R",
                tier_code=2,
                name="Recovery",
                version_str="1.07.02",
                display_version="1.07.02",
                output_filename="AD100ProII_V1.07.02_recovery.bin",
                expected_sha256="86386df6319f9e4ba3719e514525f565968d7a456c424008d26ba7eb892006bc",
                summary="Continuous fan · 2× faster cooldown between bursts",
                details="2× pause recovery",
            ),
            TierOption(
                tier_key="X",
                tier_code=3,
                name="Super",
                version_str="1.07.03",
                display_version="1.07.03",
                output_filename="AD100ProII_V1.07.03_super.bin",
                expected_sha256="71ad25e7f833f655fa129a6e37f048ed0baba09e1ce34e21f325834765d6b381",
                summary="Continuous fan · 2× faster cooldown · +25% more HSS burst shots (60 → 75)",
                details="+25% HSS burst",
            ),
        ),
    ),
    ModelSpec(
        model_id="V100N",
        display_name="Godox V100N (Nikon)",
        category="100Ws Round-Head Speedlite",
        oem_filename="V100N_V1.04.bin",
        v_prefix="V",
        godox_version=(1, 4),
        expected_size=1001676,
        expected_sha256="18e3581c601cc7c15e81bbbe951b8b336e133de822f99450f57f116ffab37ee6",
        hardware_notes="Fanless speedlite body · Monitor head temperature during rapid bursts",
        tiers=(
            TierOption(
                tier_key="R",
                tier_code=2,
                name="Recovery",
                version_str="1.04.02",
                display_version="V1.04.02",
                output_filename="V100N_V1.04.02_recovery.bin",
                expected_sha256="f3855ac2132eade59df334b4d1d406c38689d72ab4d91be9ba6c8cbb8ebba80d",
                summary="2× faster cooldown between bursts · Factory single-burst limit",
                details="2× pause recovery",
            ),
            TierOption(
                tier_key="X",
                tier_code=3,
                name="Super",
                version_str="1.04.03",
                display_version="V1.04.03",
                output_filename="V100N_V1.04.03_super.bin",
                expected_sha256="af32bb854c4a7551029874151a930210ef0cb1cb3a9ecc3acd4df72bdbba383c",
                summary="2× faster cooldown · +25% more HSS burst shots (60 → 75 at 1/1)",
                details="+25% HSS burst",
            ),
        ),
    ),
    ModelSpec(
        model_id="iT30ProN",
        display_name="Godox iT30ProN (Nikon)",
        category="Ultra-Compact Mini Speedlite",
        oem_filename="iT30ProN_V1.02.bin",
        v_prefix="V",
        godox_version=(1, 2),
        expected_size=688172,
        expected_sha256="a6920833d267834e7ff41f537ce8b897bab47234013731ae79b4affcbf41847e",
        hardware_notes="Fanless mini speedlite · Auto-updates trailing MD5 checksum footer",
        tiers=(
            TierOption(
                tier_key="R",
                tier_code=2,
                name="Recovery",
                version_str="1.02.02",
                display_version="V1.02.02",
                output_filename="iT30ProN_V1.02.02_recovery.bin",
                expected_sha256="13357697a6aa2c56afd15727f9f32148f5c11e6954e205337fa7031b0d317c27",
                summary="2× faster cooldown between bursts · Factory single-burst limit",
                details="2× pause recovery",
            ),
            TierOption(
                tier_key="X",
                tier_code=3,
                name="Super",
                version_str="1.02.03",
                display_version="V1.02.03",
                output_filename="iT30ProN_V1.02.03_super.bin",
                expected_sha256="eebbc0210a912dff953cff3a89a0cbba722ef847bc1b2400480676bb6f9afaac",
                summary="2× faster cooldown · +25% more multi-pulse HSS burst shots (40 → 50)",
                details="+25% HSS burst",
            ),
        ),
    ),
)

# Reference-only unpatchable OEM images (for helpful user diagnostics)
REFERENCE_ONLY_HASHES: Dict[str, Tuple[str, str]] = {
    "8a8cebd364987dd53ad128f9fc4943f9379a134fc5daa4a56b62a16d3f4e2a8a": (
        "Godox AD600BM II (v1.02)",
        "Manual-only strobe (disassembly reference only; custom patches are not supported for this model).",
    ),
}

MODEL_BY_SHA256: Dict[str, ModelSpec] = {m.expected_sha256: m for m in MODEL_SPECS}
MODEL_BY_ID: Dict[str, ModelSpec] = {m.model_id: m for m in MODEL_SPECS}
PATCHED_BY_SHA256: Dict[str, Tuple[ModelSpec, TierOption]] = {
    tier.expected_sha256: (model, tier)
    for model in MODEL_SPECS
    for tier in model.tiers
}


@dataclass(frozen=True)
class DetectionResult:
    status: str  # "oem_match", "already_patched", "reference_only", "size_match_hash_mismatch", "unknown"
    file_path: str
    file_size: int
    file_sha256: str
    model: Optional[ModelSpec] = None
    existing_tier: Optional[TierOption] = None
    message: str = ""


def identify_firmware(file_path: str) -> DetectionResult:
    """Read a firmware file and identify whether it is a supported OEM image, an already-patched tier, or unknown."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        data = f.read()

    file_size = len(data)
    file_sha256 = hashlib.sha256(data).hexdigest()

    # 1. Exact OEM base firmware match
    if file_sha256 in MODEL_BY_SHA256:
        model = MODEL_BY_SHA256[file_sha256]
        return DetectionResult(
            status="oem_match",
            file_path=file_path,
            file_size=file_size,
            file_sha256=file_sha256,
            model=model,
            message=f"Verified OEM firmware: {model.display_name} ({model.base_version_display})",
        )

    # 2. Already-patched custom firmware match
    if file_sha256 in PATCHED_BY_SHA256:
        model, tier = PATCHED_BY_SHA256[file_sha256]
        return DetectionResult(
            status="already_patched",
            file_path=file_path,
            file_size=file_size,
            file_sha256=file_sha256,
            model=model,
            existing_tier=tier,
            message=(
                f"This file is already patched to Tier {tier.tier_key}: {tier.name} ({tier.version_str}). "
                f"Drop the original OEM '{model.oem_filename}' ({model.base_version_display}) to build other versions."
            ),
        )

    # 3. Known reference-only firmware
    if file_sha256 in REFERENCE_ONLY_HASHES:
        ref_name, ref_msg = REFERENCE_ONLY_HASHES[file_sha256]
        return DetectionResult(
            status="reference_only",
            file_path=file_path,
            file_size=file_size,
            file_sha256=file_sha256,
            message=f"{ref_name}: {ref_msg}",
        )

    # 4. File size matches one of our models, but SHA-256 differs
    for model in MODEL_SPECS:
        if file_size == model.expected_size:
            return DetectionResult(
                status="size_match_hash_mismatch",
                file_path=file_path,
                file_size=file_size,
                file_sha256=file_sha256,
                model=model,
                message=(
                    f"Size matches {model.display_name}, but checksum does not match official {model.base_version_display} "
                    f"(got {file_sha256[:12]}...)."
                ),
            )

    # 5. Unknown file
    supported_list = ", ".join(f"{m.display_name} ({m.base_version_display})" for m in MODEL_SPECS)
    return DetectionResult(
        status="unknown",
        file_path=file_path,
        file_size=file_size,
        file_sha256=file_sha256,
        message=f"Unrecognized file ({file_size:,} B). Supported OEM bases: {supported_list}.",
    )


def _load_model_patcher(model_id: str):
    """Dynamically load models/<model_id>/patch.py from source tree or PyInstaller bundle."""
    bundle_root = get_bundle_root()
    patch_script = os.path.join(bundle_root, MODELS_DIRNAME, model_id, "patch.py")
    if not os.path.isfile(patch_script):
        raise FileNotFoundError(f"Model patcher script not found: {patch_script}")

    spec = importlib.util.spec_from_file_location(f"godox_patch_{model_id}", patch_script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not create module spec for {patch_script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class BuiltOutput:
    tier: TierOption
    output_path: str
    sha256: str
    verified: bool


def build_selected_tiers(
    source_file_path: str,
    model: ModelSpec,
    tier_keys: List[str],
    output_dir: Optional[str] = None,
) -> List[BuiltOutput]:
    """
    Build one or more custom firmware tiers from a verified OEM base image.
    Writes output `.bin` files to `output_dir` (defaults to the directory of `source_file_path`)
    and verifies the resulting SHA-256 against `TierOption.expected_sha256`.
    """
    with open(source_file_path, "rb") as f:
        base_data = bytearray(f.read())

    if len(base_data) != model.expected_size:
        raise ValueError(
            f"Size mismatch for {model.display_name}: expected {model.expected_size} bytes, got {len(base_data)}"
        )

    actual_sha = hashlib.sha256(base_data).hexdigest()
    if actual_sha != model.expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {model.display_name}: expected {model.expected_sha256}, got {actual_sha}"
        )

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(source_file_path))

    os.makedirs(output_dir, exist_ok=True)
    patcher_mod = _load_model_patcher(model.model_id)

    tier_map = {t.tier_key: t for t in model.tiers}
    results: List[BuiltOutput] = []

    for key in tier_keys:
        if key not in tier_map:
            raise ValueError(f"Tier '{key}' is not supported on {model.display_name}")
        tier_opt = tier_map[key]
        out_hash = patcher_mod.build_profile(base_data, key, output_dir)
        out_path = os.path.join(output_dir, tier_opt.output_filename)
        verified = (out_hash == tier_opt.expected_sha256)
        if not verified:
            raise RuntimeError(
                f"Output SHA-256 verification failed for {tier_opt.output_filename}: "
                f"expected {tier_opt.expected_sha256}, got {out_hash}"
            )
        results.append(
            BuiltOutput(
                tier=tier_opt,
                output_path=out_path,
                sha256=out_hash,
                verified=verified,
            )
        )

    return results
