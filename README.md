# AutoCAD Evaluator

A Windows-based Python tool for assessing AutoCAD DWG submissions against configurable JSON criteria. It includes a Streamlit editor and batch evaluation interface, plus a command-line runner.

## Requirements

- Windows with a working installation of AutoCAD and access to its COM automation interface.
- Python 3.10+ recommended; install the packages in `requirements.txt`.
- A local folder of DWG submissions. Each DWG's parent folder name is used as the student name.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Workflow

1. In **Criteria**, import a JSON configuration or create/edit criteria in the rule builder. The JSON structure contains `version`, `name`, `description`, and `criteria`.
2. Download the JSON configuration to save your changes. The Streamlit editor does not automatically persist criteria to disk.
3. In **Evaluatie**, enter the local root folder of DWG files, search for drawings, and start evaluation.
4. Review the **Resultaten** overview (one row per student) and **Detailresultaten per criterium** (one row per criterion per student).
5. Download the overview or detail CSV, or the Excel workbook with **Resultaten** and **Details** sheets.

**Criterion labels:** Summary column headings use the criterion's `name` rather than its `id`. The detail view uses `results_to_detail_dataframe()` from `batch.py`; the internal `criterion_id` remains in detail exports for traceability but is hidden in the Streamlit detail display. Give criteria unique names to prevent similarly named summary columns from overwriting one another.

## Command line

```powershell
python run_from_json.py "D:\Examens" "evaluation_criteria_example.json" --output "evaluation_results.xlsx"
```

Add `--hidden` to request a hidden AutoCAD window. The CLI produces an Excel workbook containing summary and detail worksheets.

## Project structure

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit UI, session state, batch controls and downloads |
| `rule_builder.py` | Interactive criteria editor |
| `config.py` | JSON schema defaults, normalization, validation and I/O |
| `criteria_generator.py` | Helpers for checking and normalizing generated criteria; **not wired into the current Streamlit UI** |
| `autocad_inspector.py` | AutoCAD COM inspection of ModelSpace, layouts and associated files |
| `evaluator.py` | Rule evaluation and scoring |
| `batch.py` | DWG discovery, per-file evaluation, DataFrames and Excel export |
| `run_from_json.py` | Command-line batch runner |
| `evaluation_criteria_example.json` | Example criteria configuration |

## Evaluation outputs

- `results_to_dataframe(results)` creates a wide summary table with human-readable criterion names.
- `results_to_detail_dataframe(results)` creates a long-form detail table, preserving `criterion_id` alongside the human-readable `criterion` field.
- `evaluate_one_dwg()` and `rows_to_dataframes()` remain for backward compatibility with the CLI.
