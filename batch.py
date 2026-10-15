from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from autocad_inspector import inspect_dwg
from evaluator import evaluate_context


# ============================================================
# Find DWG files
# ============================================================

def find_dwg_files(root_folder: str) -> list[str]:
    """
    Zoek recursief alle DWG-bestanden in een map.

    Parameters
    ----------
    root_folder:
        Hoofdmap waarin gezocht moet worden.

    Returns
    -------
    list[str]
        Gesorteerde lijst met volledige paden naar DWG-bestanden.
    """

    root = Path(root_folder)
    if not root.exists():
        raise FileNotFoundError(f"De opgegeven map bestaat niet: {root}")
    if not root.is_dir():
        raise ValueError(f"Het opgegeven pad is geen map: {root}")
    return sorted(str(path) for path in root.rglob("*") if (path.is_file() and path.suffix.lower() == ".dwg"))


# ============================================================
# Student name
# ============================================================

def get_student_name(dwg_path: str) -> str:
    """
    Haal de studentnaam uit de bovenliggende map.

    Voorbeeld:

        D:\\Examens\\Student A\\drawing.dwg

    geeft:

        Student A
    """
    path = Path(dwg_path)
    return path.parent.name


# ============================================================
# Evaluate one DWG
# ============================================================

def evaluate_single_dwg(dwg_path: str, config: dict[str, Any], visible: bool = True, readonly: bool = True) -> dict[str, Any]:
    """
    Evalueer één DWG-bestand.

    Deze functie:
    - leest het DWG-bestand met autocad_inspector;
    - evalueert de DrawingContext;
    - zet het resultaat om naar één uniforme dictionary.

    Deze vorm is geschikt voor opslag in Streamlit session_state.
    """
    student = get_student_name(dwg_path)

    try:
        context = inspect_dwg(dwg_path=dwg_path, visible=visible, readonly=readonly)
        result = evaluate_context(context=context, config=config)

        return {
            "success": True,
            "student": student,
            "file": dwg_path,
            "score": result.get("score", 0.0),
            "max_score": result.get("max_score", 0.0),
            "percentage": result.get("percentage", 0.0),
            "criteria": result.get("results", []),
            "error": "",
        }

    except Exception as exc:
        return {
            "success": False,
            "student": student,
            "file": dwg_path,
            "score": 0.0,
            "max_score": 0.0,
            "percentage": 0.0,
            "criteria": [],
            "error": str(exc),
        }


# ============================================================
# Backwards-compatible alias
# ============================================================

def evaluate_one_dwg(dwg_path: str, config: dict[str, Any], visible: bool = True, readonly: bool = True):
    """
    Compatibiliteitsfunctie voor oudere code.

    Retourneert:
        summary, details
    """

    result = evaluate_single_dwg(dwg_path=dwg_path, config=config, visible=visible, readonly=readonly)
    summary = {
        "student": result["student"],
        "dwg": result["file"],
        "score": result["score"],
        "max_score": result["max_score"],
        "percentage": result["percentage"],
        "error": result["error"],
    }

    details = []

    for item in result.get("criteria", []):
        criterion_id = item.get("id", "")

        # Add criterion score to wide summary table
        if criterion_id:
            summary[item.get("name") or criterion_id] = item.get("points", 0.0)

        details.append(
            {
                "student": result["student"],
                "dwg": result["file"],
                "criterion_id": criterion_id,
                "criterion": item.get("name", ""),
                "passed": item.get("passed", False),
                "points": item.get("points", 0.0),
                "max_points": item.get("max_points", 0.0),
                "actual": str(item.get("actual", "")),
                "details": item.get("details", ""),
            }
        )
    return (summary, details)


# ============================================================
# Convert results to DataFrame
# ============================================================

def results_to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Maak een compacte overzichtstabel uit batchresultaten.

    Iedere student vormt één rij.
    Daarnaast wordt per criterium een kolom toegevoegd.
    """

    rows = []
    for result in results:
        row = {
            "student": result.get("student", ""),
            "dwg": result.get("file", ""),
            "success": result.get("success", False),
            "score": result.get("score", 0.0),
            "max_score": result.get("max_score", 0.0),
            "percentage": result.get("percentage", 0.0),
            "error": result.get("error", ""),
        }
        for criterion in result.get("criteria", []):
            criterion_id = (criterion.get("id"))
            if not criterion_id:
                continue
            row[criterion.get("name") or criterion_id] = criterion.get("points", 0.0)
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# Detail DataFrame
# ============================================================

def results_to_detail_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Maak een detailtabel met één rij per criterium per student.
    """

    rows = []
    for result in results:
        student = result.get("student", "")
        dwg = result.get("file", "")
        if not result.get("success", False):
            rows.append(
                {
                    "student": student,
                    "dwg": dwg,
                    "criterion_id": "",
                    "criterion": "",
                    "passed": False,
                    "points": 0.0,
                    "max_points": 0.0,
                    "actual": "",
                    "details": "",
                    "error": result.get("error", ""),
                }
            )

            continue

        for item in result.get("criteria", []):
            rows.append(
                {
                    "student": student,
                    "dwg": dwg,
                    "criterion_id": item.get("id", ""),
                    "criterion": item.get("name", ""),
                    "passed": item.get("passed", False),
                    "points": item.get("points", 0.0),
                    "max_points": item.get("max_points", 0.0),
                    "actual": str(item.get("actual", "")),
                    "details": item.get("details", ""),
                    "error": "",
                }
            )
    return pd.DataFrame(rows)


# ============================================================
# Legacy DataFrame converter
# ============================================================

def rows_to_dataframes(summary_rows, detail_rows):
    """
    Compatibiliteit met oudere batchcode.
    """
    return (pd.DataFrame(summary_rows), pd.DataFrame(detail_rows))


# ============================================================
# Excel export
# ============================================================

def export_excel(summary_df: pd.DataFrame, detail_df: pd.DataFrame, output_path: str) -> str:
    """
    Exporteer samenvatting en detailresultaten naar Excel.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        detail_df.to_excel(writer, sheet_name="Details", index=False)

    return str(output)
