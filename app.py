from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from config import empty_config
from rule_builder import render_rule_builder
from config import config_from_json
from batch import (find_dwg_files, evaluate_single_dwg, results_to_dataframe, results_to_detail_dataframe)


# ============================================================
# Streamlit configuration
# ============================================================

st.set_page_config(page_title="AutoCAD Evaluator", page_icon="📐", layout="wide")

st.title("AutoCAD Evaluator")

st.caption(
    "Genereer evaluatiecriteria met AI, pas ze handmatig aan "
    "en evalueer vervolgens AutoCAD DWG-bestanden."
)


# ============================================================
# Session state
# ============================================================

if "config" not in st.session_state:
    st.session_state.config = empty_config()

if "batch_running" not in st.session_state:
    st.session_state.batch_running = False

if "batch_stop_requested" not in st.session_state:
    st.session_state.batch_stop_requested = False

if "batch_files" not in st.session_state:
    st.session_state.batch_files = []

if "batch_index" not in st.session_state:
    st.session_state.batch_index = 0

if "batch_results" not in st.session_state:
    st.session_state.batch_results = []


# ============================================================
# Helpers
# ============================================================

def config_to_json(config: dict) -> str:
    return json.dumps(
        config,
        indent=2,
        ensure_ascii=False,
    )


def reset_batch():
    st.session_state.batch_running = False
    st.session_state.batch_stop_requested = False
    st.session_state.batch_files = []
    st.session_state.batch_index = 0
    st.session_state.batch_results = []


# ============================================================
# Tabs
# ============================================================

tab_criteria, tab_evaluation = st.tabs(["Criteria", "Evaluatie"])


# ============================================================
# Criteria
# ============================================================

with tab_criteria:
    st.header("Evaluatiecriteria")

    # --------------------------------------------------------
    # Import JSON
    # --------------------------------------------------------

    col_import, col_download = st.columns(2)

    with col_import:
        uploaded_json = st.file_uploader(
            "Importeer criteria uit JSON",
            type=["json"],
            key="criteria_json_upload",
        )

        if uploaded_json is not None:
            if st.button("JSON laden", width='stretch'):
                try:
                    imported_config = config_from_json(uploaded_json.getvalue().decode("utf-8"))
                    st.session_state.config = imported_config
                    st.session_state["config_name"] = (imported_config.get("name", ""))
                    st.session_state["config_description"] = (imported_config.get("description", ""))
                    st.success("Configuratie geladen.")
                    st.rerun()
                except (ValueError, TypeError, UnicodeDecodeError) as exc:
                    st.error(f"JSON kon niet worden geladen: {exc}")

    with col_download:
        st.download_button(
            "Download criteria als JSON",
            data=config_to_json(
                st.session_state.config
            ),
            file_name="evaluation_criteria.json",
            mime="application/json",
            width='stretch',
        )
    st.divider()

    # --------------------------------------------------------
    # General config
    # --------------------------------------------------------

    st.subheader("Algemeen")

    st.session_state.config["name"] = st.text_input(
        "Naam configuratie",
        value=st.session_state.config.get(
            "name",
            "",
        ),
        key="config_name",
    )

    st.session_state.config["description"] = (
        st.text_area(
            "Beschrijving",
            value=st.session_state.config.get(
                "description",
                "",
            ),
            height=100,
            key="config_description",
        )
    )

    st.session_state.config["version"] = (
        st.session_state.config.get("version", 2)
    )

    st.divider()

    # --------------------------------------------------------
    # Rule builder
    # --------------------------------------------------------

    st.subheader("Criteria")
    updated_config = render_rule_builder(st.session_state.config)
    if updated_config is not None:
        st.session_state.config = updated_config

    # --------------------------------------------------------
    # JSON preview
    # --------------------------------------------------------

    with st.expander(
        "Volledige JSON-configuratie",
        expanded=False,
    ):

        st.code(
            config_to_json(
                st.session_state.config
            ), language="json")


# ============================================================
# Evaluation
# ============================================================

with tab_evaluation:
    st.header("DWG-evaluatie")
    st.write(
        "Selecteer een hoofdmap met DWG-bestanden. "
        "De evaluator verwerkt één bestand per Streamlit-run, "
        "zodat de evaluatie veilig kan worden gestopt."
    )

    evaluation_root = st.text_input("Map met studentenbestanden", placeholder=r"D:\Projecten\Evaluations\submissions")

    visible_autocad = st.checkbox("AutoCAD zichtbaar", value=True)

    readonly = st.checkbox("DWG read-only openen", value=True)

    # --------------------------------------------------------
    # Find files
    # --------------------------------------------------------
    if st.button("Zoek DWG-bestanden", width='stretch'):
        if not evaluation_root.strip():
            st.error("Geef eerst een map op.")

        else:
            try:
                files = find_dwg_files(evaluation_root.strip())

                st.session_state.batch_files = [str(path) for path in files]

                st.session_state.batch_index = 0
                st.session_state.batch_results = []
                st.session_state.batch_running = False
                st.session_state.batch_stop_requested = False

                st.success(f"{len(files)} DWG-bestanden gevonden.")

            except Exception as exc:
                st.error(f"Zoeken naar DWG-bestanden mislukt: {exc}")

    # --------------------------------------------------------
    # File overview
    # --------------------------------------------------------
    if st.session_state.batch_files:
        st.info(f"{len(st.session_state.batch_files)} DWG-bestanden klaar voor evaluatie.")

        with st.expander("Gevonden bestanden", expanded=False):
            for filename in (st.session_state.batch_files):
                st.write(filename)

    # --------------------------------------------------------
    # Start / stop
    # --------------------------------------------------------
    col_start, col_stop, col_reset = st.columns(3)

    with col_start:
        if st.button("Start evaluatie", type="primary", disabled=(st.session_state.batch_running or not st.session_state.batch_files), width='stretch'):
            st.session_state.batch_running = True
            st.session_state.batch_stop_requested = False

            if (st.session_state.batch_index >= len(st.session_state.batch_files)):
                st.session_state.batch_index = 0
                st.session_state.batch_results = []

            st.rerun()

    with col_stop:
        if st.button("Stop evaluatie", disabled=not st.session_state.batch_running, width='stretch'):
            st.session_state.batch_stop_requested = True

    with col_reset:
        if st.button("Reset", width='stretch'):
            reset_batch()
            st.rerun()

    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------
    total_files = len(st.session_state.batch_files)
    current_index = (st.session_state.batch_index)

    if total_files:
        progress = min(current_index / total_files, 1.0)
        st.progress(progress, text=(f"{current_index} / {total_files} bestanden verwerkt"))

    # --------------------------------------------------------
    # Process ONE DWG
    # --------------------------------------------------------
    if st.session_state.batch_running:
        if st.session_state.batch_stop_requested:
            st.session_state.batch_running = False
            st.session_state.batch_stop_requested = False
            st.warning("Evaluatie gestopt.")
        elif (st.session_state.batch_index >= len(st.session_state.batch_files)):
            st.session_state.batch_running = False
            st.success("Evaluatie voltooid.")
        else:
            dwg_path = (
                st.session_state.batch_files[
                    st.session_state.batch_index
                ]
            )

            st.info(f"Evalueren: {dwg_path}")

            try:
                result = evaluate_single_dwg(
                    dwg_path=dwg_path,
                    config=st.session_state.config,
                    visible=visible_autocad,
                    readonly=readonly,
                )
                st.session_state.batch_results.append(result)

            except Exception as exc:

                st.session_state.batch_results.append(
                    {
                        "file": dwg_path,
                        "success": False,
                        "error": str(exc),
                    }
                )

            finally:
                st.session_state.batch_index += 1

            st.rerun()

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------
    if st.session_state.batch_results:
        st.divider()
        st.subheader("Resultaten")

        try:
            results_df = results_to_dataframe(st.session_state.batch_results)
            detail_df = results_to_detail_dataframe(st.session_state.batch_results)

        except Exception:
            results_df = pd.DataFrame(st.session_state.batch_results)
            detail_df = pd.DataFrame()

        st.dataframe(results_df, width='stretch', hide_index=True)
        st.subheader("Detailresultaten per criterium")
        st.dataframe(detail_df.drop(columns=["criterion_id"], errors="ignore"), width="stretch", hide_index=True)

        # CSV
        csv_data = results_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "Download resultaten als CSV",
            data=csv_data,
            file_name="evaluation_results.csv",
            mime="text/csv",
            width='stretch',
        )

        st.download_button(
            "Download detailresultaten als CSV",
            data=detail_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="evaluation_details.csv",
            mime="text/csv",
            width="stretch",
        )

        # Excel
        try:
            from io import BytesIO
            excel_buffer = BytesIO()

            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                results_df.to_excel(writer, index=False, sheet_name="Resultaten")
                detail_df.to_excel(writer, index=False, sheet_name="Details")

            st.download_button(
                "Download resultaten als Excel",
                data=excel_buffer.getvalue(),
                file_name="evaluation_results.xlsx",
                mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                width='stretch',
            )

        except Exception as exc:
            st.caption(f"Excel-export niet beschikbaar: {exc}")
