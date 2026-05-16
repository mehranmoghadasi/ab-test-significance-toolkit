"""Load GA4-style export CSVs into the toolkit's variant-summary format.

The expected GA4 export is one row per session with at minimum these columns:
- experiment_variant (control / treatment / or arbitrary variant name)
- session_id (string)
- converted (0 or 1)
- revenue (float; 0 if not converted)

Optional:
- aov_currency
- ga_session_number
- traffic_source

This loader is permissive about column names — pass a column_map dict to
remap to your own export schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .frequentist import VariantSummary


DEFAULT_COLUMN_MAP = {
    "variant": "experiment_variant",
    "session_id": "session_id",
    "converted": "converted",
    "revenue": "revenue",
}


@dataclass
class LoadedExperiment:
    variant_summaries: Dict[str, VariantSummary]
    revenue_by_variant: Dict[str, np.ndarray]
    raw_df: pd.DataFrame
    column_map: Dict[str, str]


def load_ga4_csv(
    path: str | Path,
    column_map: Optional[Dict[str, str]] = None,
    control_variant: str = "control",
) -> LoadedExperiment:
    """Load a GA4 export CSV into experiment-ready structures.

    Args:
        path: Path to the CSV.
        column_map: Optional remap of {variant, session_id, converted, revenue}.
        control_variant: Which variant value to label as the control summary.

    Returns:
        LoadedExperiment with per-variant counts and revenue arrays.
    """
    cmap = {**DEFAULT_COLUMN_MAP, **(column_map or {})}
    df = pd.read_csv(path)

    missing = [c for c in cmap.values() if c not in df.columns]
    if missing:
        raise KeyError(
            f"Missing required columns in GA4 export: {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    if df.duplicated(subset=[cmap["session_id"]]).any():
        n_dup = int(df.duplicated(subset=[cmap["session_id"]]).sum())
        df = df.drop_duplicates(subset=[cmap["session_id"]], keep="first")
        # In a real pipeline we'd log this; here we attach a metadata flag.
        df.attrs["dedup_dropped"] = n_dup

    variant_col = cmap["variant"]
    converted_col = cmap["converted"]
    revenue_col = cmap["revenue"]

    df[converted_col] = pd.to_numeric(df[converted_col], errors="coerce").fillna(0).astype(int)
    df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0.0)

    summaries: Dict[str, VariantSummary] = {}
    revenues: Dict[str, np.ndarray] = {}

    for variant_name, sub in df.groupby(variant_col):
        summaries[str(variant_name)] = VariantSummary(
            name=str(variant_name),
            visitors=int(len(sub)),
            conversions=int(sub[converted_col].sum()),
        )
        revenues[str(variant_name)] = sub[revenue_col].to_numpy()

    if control_variant not in summaries:
        raise KeyError(
            f"control_variant '{control_variant}' not found among variants: "
            f"{list(summaries.keys())}"
        )

    return LoadedExperiment(
        variant_summaries=summaries,
        revenue_by_variant=revenues,
        raw_df=df,
        column_map=cmap,
    )


def select_pair(
    experiment: LoadedExperiment,
    control_name: str,
    treatment_name: str,
):
    """Pull a (control, treatment) summary + revenue arrays out of a multi-variant export."""
    if control_name not in experiment.variant_summaries:
        raise KeyError(f"control '{control_name}' not in variants.")
    if treatment_name not in experiment.variant_summaries:
        raise KeyError(f"treatment '{treatment_name}' not in variants.")
    return (
        experiment.variant_summaries[control_name],
        experiment.variant_summaries[treatment_name],
        experiment.revenue_by_variant[control_name],
        experiment.revenue_by_variant[treatment_name],
    )
