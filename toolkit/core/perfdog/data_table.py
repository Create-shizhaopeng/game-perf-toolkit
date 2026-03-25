"""DataFrame → 报告用全量表格（字符串单元格，便于 Markdown / GUI 展示）。"""

from __future__ import annotations

import pandas as pd


def dataframe_to_report_cells(df: pd.DataFrame) -> tuple[list[str], list[list[str]]]:
    """列名为 str，行值为 str；缺失值为空串。"""
    cols = [str(c) for c in df.columns]
    if df.empty:
        return cols, []
    mat = df.to_numpy(copy=False)
    rows: list[list[str]] = []
    for i in range(len(df)):
        line: list[str] = []
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                line.append("")
            else:
                line.append(str(v))
        rows.append(line)
    return cols, rows
