from __future__ import annotations

import argparse
from pathlib import Path

from batch import evaluate_one_dwg, export_excel, find_dwg_files, rows_to_dataframes
from config import config_from_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_folder")
    parser.add_argument("config_json")
    parser.add_argument("--output", default="evaluation_results.xlsx")
    parser.add_argument("--hidden", action="store_true")
    args = parser.parse_args()

    config = config_from_json(Path(args.config_json).read_text(encoding="utf-8"))
    summary_rows, detail_rows = [], []
    for dwg in find_dwg_files(args.root_folder):
        summary, details = evaluate_one_dwg(dwg, config, visible=not args.hidden)
        summary_rows.append(summary)
        detail_rows.extend(details)
    summary_df, detail_df = rows_to_dataframes(summary_rows, detail_rows)
    export_excel(summary_df, detail_df, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
