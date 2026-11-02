"""DeepChecks sobre las mismas variables y particiones que el entrenamiento de P2."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

# DeepChecks 0.19.1 todavía utiliza estos nombres de NumPy.
for _name, _value in {"Inf": np.inf, "NaN": np.nan, "bool": np.bool_}.items():
    if _name not in np.__dict__:
        setattr(np, _name, _value)

from deepchecks.tabular import Dataset
from deepchecks.tabular.suites import data_integrity, train_test_validation

from src.features.p2_features import get_train_test_data


def load_dataset_samples(
    parquet_path: Path, sample_size: int = 15000, random_state: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Muestrea después de aplicar el filtro y el corte temporal de producción.

    Se excluyen el calentamiento, target=-1 y las dos últimas horas de Train.
    Las variables futuras delta_net y ratio nunca se consideran predictoras.
    """
    if sample_size < 2:
        raise ValueError("sample_size debe ser al menos 2 (una fila por partición).")
    x_train, _, x_test, _, features, clean = get_train_test_data(
        features_parquet=parquet_path
    )
    columns = ["station_id", "timestamp", *features, "target"]
    train = clean.loc[x_train.index, columns]
    test = clean.loc[x_test.index, columns]
    if train.empty or test.empty:
        raise ValueError("Se necesitan filas válidas de Train (2025) y Test (2026).")
    for name, frame in [("Train", train), ("Test", test)]:
        if not frame["target"].isin([0, 1, 2]).all():
            raise ValueError(f"{name} contiene etiquetas distintas de 0, 1 y 2.")
    train_size = min(sample_size // 2, len(train))
    test_size = min(sample_size - sample_size // 2, len(test))
    return (
        train.sample(n=train_size, random_state=random_state).sort_values("timestamp"),
        test.sample(n=test_size, random_state=random_state).sort_values("timestamp"),
        features,
    )


def make_dataset(frame: pd.DataFrame, feature_cols: list[str], name: str) -> Dataset:
    """Conserva fecha y clave estación/hora como metadatos para detectar fugas."""
    data = frame[["timestamp", *feature_cols, "target"]].copy()
    data["row_id"] = (
        frame["station_id"].astype(str) + "|" + frame["timestamp"].astype(str)
    )
    return Dataset(
        data,
        label="target",
        features=feature_cols,
        cat_features=[],
        datetime_name="timestamp",
        index_name="row_id",
        label_type="multiclass",
        dataset_name=name,
    )


def summarize_suite(result, suite_name: str, output_html: Path | None = None) -> dict:
    """Registra condiciones incumplidas y errores; generar un HTML no implica aprobar."""
    if output_html is not None:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        with output_html.open("w", encoding="utf-8") as stream:
            result.save_as_html(stream)
    passed = [check.check.name() for check in result.get_passed_checks()]
    failed = [check.check.name() for check in result.get_not_passed_checks()]
    not_run = [
        {"check": check.check.name(), "reason": str(check.exception)}
        for check in result.get_not_ran_checks()
    ]
    conditions = []
    for check in result.results:
        for condition in getattr(check, "conditions_results", []):
            conditions.append(
                {
                    "check": check.check.name(),
                    "condition": condition.name,
                    "status": condition.category.name,
                    "details": condition.details,
                }
            )
    return {
        "suite_name": suite_name,
        "total_checks": len(result.results),
        "passed_checks_count": len(passed),
        "passed_checks": passed,
        "not_passed_checks": failed,
        "not_run_checks": not_run,
        "conditions": conditions,
        "all_passed": bool(result.passed(fail_if_check_not_run=True)),
        "report_path": output_html.name if output_html else None,
    }


def run_data_integrity_suite(
    df: pd.DataFrame, feature_cols: list[str], output_html: Path | None = None
) -> dict:
    """Audita integridad con los umbrales estándar de DeepChecks, sin omitir avisos."""
    result = data_integrity(random_state=42).run(
        make_dataset(df, feature_cols, "P2 integridad")
    )
    return summarize_suite(result, "data_integrity", output_html)


def run_train_test_drift_suite(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: list[str],
    output_html: Path | None = None,
) -> dict:
    """Compara 2025/2026, incluidas las comprobaciones de fuga por fecha e índice."""
    result = train_test_validation(random_state=42).run(
        train_dataset=make_dataset(df_train, feature_cols, "P2 Train 2025"),
        test_dataset=make_dataset(df_test, feature_cols, "P2 Test 2026"),
    )
    return summarize_suite(result, "train_test_validation", output_html)


def file_sha256(path: Path) -> str:
    """Identifica el dataset realmente auditado sin publicarlo en Git."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
