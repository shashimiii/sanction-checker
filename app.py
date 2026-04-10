from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, send_from_directory, url_for

from sanctions_engine import (
    DATA_DIR,
    OUTPUT_DIR,
    SCREENSHOT_DIR,
    build_report,
    ensure_dirs,
    load_sanctions_index,
)

app = Flask(__name__)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/run")
def run_check() -> str:
    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("index.html", error="请先上传 Excel 文件（首列为供应商/股东名称）。")

    ensure_dirs()
    upload_id = uuid.uuid4().hex
    upload_path = OUTPUT_DIR / "uploads" / f"input_{upload_id}.xlsx"
    file.save(upload_path)

    try:
        df = pd.read_excel(upload_path)
    except Exception as exc:
        return render_template("index.html", error=f"读取 Excel 失败: {exc}")

    if df.empty:
        return render_template("index.html", error="Excel 内容为空。")

    names = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
    if not names:
        return render_template("index.html", error="首列没有可查询的名称。")

    sanctions_index = load_sanctions_index(DATA_DIR)
    result = build_report(names, sanctions_index, run_id=upload_id)

    return render_template(
        "result.html",
        run_id=upload_id,
        total=result["summary"]["total"],
        hit=result["summary"]["hit"],
        nohit=result["summary"]["nohit"],
        uncertain=result["summary"]["uncertain"],
        excel_url=url_for("download", folder="excel", filename=result["excel_filename"]),
        screenshot_url=url_for("download", folder="screenshots", filename=result["zip_filename"]),
    )


@app.get("/download/<folder>/<path:filename>")
def download(folder: str, filename: str):
    if folder == "excel":
        base = OUTPUT_DIR / "excel"
    elif folder == "screenshots":
        base = OUTPUT_DIR / "archives"
    else:
        return "invalid folder", 400
    return send_from_directory(base, filename, as_attachment=True)


if __name__ == "__main__":
    ensure_dirs()
    Path("templates").mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
