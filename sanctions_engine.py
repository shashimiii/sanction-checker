from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

OFAC_SDN_CSV = "https://www.treasury.gov/ofac/downloads/sdn.csv"
UN_CONSOLIDATED_XML = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
EU_FSFD_CSV = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content?token=dG9rZW4tMjAxNw"


@dataclass
class SanctionEntry:
    source: str
    name: str


def ensure_dirs() -> None:
    for p in [DATA_DIR, OUTPUT_DIR, OUTPUT_DIR / "excel", OUTPUT_DIR / "archives", OUTPUT_DIR / "uploads", SCREENSHOT_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def _download(url: str, path: Path) -> None:
    res = requests.get(url, timeout=60)
    res.raise_for_status()
    path.write_bytes(res.content)


def refresh_data(data_dir: Path = DATA_DIR) -> None:
    ensure_dirs()
    _download(OFAC_SDN_CSV, data_dir / "ofac_sdn.csv")
    _download(UN_CONSOLIDATED_XML, data_dir / "un_consolidated.xml")
    _download(EU_FSFD_CSV, data_dir / "eu_fsf.csv")


def _normalize(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9\u4e00-\u9fff]", "", text)
    return text


def _load_ofac(path: Path) -> list[SanctionEntry]:
    out: list[SanctionEntry] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            name = row[1].strip() if len(row) > 1 else ""
            if name:
                out.append(SanctionEntry(source="OFAC SDN", name=name))
    return out


def _load_un_xml(path: Path) -> list[SanctionEntry]:
    import xml.etree.ElementTree as ET

    out: list[SanctionEntry] = []
    root = ET.fromstring(path.read_bytes())
    for node in root.findall(".//INDIVIDUAL") + root.findall(".//ENTITY"):
        pieces = []
        for tag in ["FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME", "NAME_ORIGINAL_SCRIPT"]:
            t = node.findtext(tag, default="").strip()
            if t:
                pieces.append(t)
        if not pieces:
            whole = node.findtext("ENTITY_NAME", default="").strip() or node.findtext("FIRST_NAME", default="").strip()
            if whole:
                pieces = [whole]
        if pieces:
            out.append(SanctionEntry(source="UN Consolidated", name=" ".join(pieces)))
    return out


def _load_eu(path: Path) -> list[SanctionEntry]:
    out: list[SanctionEntry] = []
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    for col in ["nameAlias", "name"]:
        if col in df.columns:
            vals = df[col].dropna().astype(str)
            for v in vals:
                clean = v.strip()
                if clean:
                    out.append(SanctionEntry(source="EU Sanctions Map", name=clean))
    return out


def _load_ppatk_manual(path: Path) -> list[SanctionEntry]:
    if not path.exists():
        return []
    df = pd.read_excel(path)
    names = df.iloc[:, 0].dropna().astype(str).tolist()
    return [SanctionEntry(source="PPATK(Manual)", name=n) for n in names if n.strip()]


def load_sanctions_index(data_dir: Path = DATA_DIR) -> list[SanctionEntry]:
    required = [data_dir / "ofac_sdn.csv", data_dir / "un_consolidated.xml", data_dir / "eu_fsf.csv"]
    if not all(p.exists() for p in required):
        refresh_data(data_dir)

    entries: list[SanctionEntry] = []
    entries.extend(_load_ofac(data_dir / "ofac_sdn.csv"))
    entries.extend(_load_un_xml(data_dir / "un_consolidated.xml"))
    entries.extend(_load_eu(data_dir / "eu_fsf.csv"))
    entries.extend(_load_ppatk_manual(data_dir / "ppatk_manual.xlsx"))

    dedup = {}
    for e in entries:
        key = (e.source, _normalize(e.name))
        if key[1]:
            dedup[key] = e
    return list(dedup.values())


def _best_match(name: str, entries: Iterable[SanctionEntry]) -> tuple[SanctionEntry | None, float]:
    normalized_query = _normalize(name)
    best_score = 0.0
    best_entry = None
    for e in entries:
        score = float(fuzz.WRatio(normalized_query, _normalize(e.name)))
        if score > best_score:
            best_score = score
            best_entry = e
    return best_entry, best_score


def _to_status(score: float) -> str:
    if score >= 92:
        return "是"
    if score >= 80:
        return "待复核"
    return "否"


def _make_result_image(path: Path, query: str, status: str, score: float, source: str, matched_name: str) -> None:
    img = Image.new("RGB", (1200, 700), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    lines = [
        "Sanctions Screening Snapshot",
        f"Query: {query}",
        f"Status: {status}",
        f"Score: {score:.1f}",
        f"Source: {source}",
        f"Matched Name: {matched_name[:120]}",
    ]
    y = 60
    for line in lines:
        draw.text((60, y), line, fill="black", font=font)
        y += 80

    img.save(path)


def build_report(company_names: list[str], sanctions_index: list[SanctionEntry], run_id: str) -> dict:
    rows = []
    run_shot_dir = SCREENSHOT_DIR / run_id
    run_shot_dir.mkdir(parents=True, exist_ok=True)

    hit = nohit = uncertain = 0
    for i, name in enumerate(company_names, start=1):
        best, score = _best_match(name, sanctions_index)
        status = _to_status(score)
        if status == "是":
            hit += 1
        elif status == "否":
            nohit += 1
        else:
            uncertain += 1

        source = best.source if best else ""
        matched_name = best.name if best else ""
        safe = re.sub(r'[^0-9A-Za-z一-龥_-]+', '_', name)[:40]
        screenshot_file = f"{i:04d}_{safe}.png"
        screenshot_path = run_shot_dir / screenshot_file
        _make_result_image(screenshot_path, name, status, score, source, matched_name)

        rows.append(
            {
                "公司名称": name,
                "是否命中": status,
                "匹配分数": round(score, 2),
                "风险来源": source,
                "匹配名称": matched_name,
                "截图文件": str(screenshot_path.relative_to(OUTPUT_DIR)),
            }
        )

    result_df = pd.DataFrame(rows)
    excel_name = f"result_{run_id}.xlsx"
    excel_path = OUTPUT_DIR / "excel" / excel_name
    result_df.to_excel(excel_path, index=False)

    zip_name = f"screenshots_{run_id}.zip"
    zip_path = OUTPUT_DIR / "archives" / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for shot in sorted(run_shot_dir.glob("*.png")):
            zf.write(shot, arcname=shot.name)

    return {
        "summary": {"total": len(rows), "hit": hit, "nohit": nohit, "uncertain": uncertain},
        "excel_filename": excel_name,
        "zip_filename": zip_name,
    }
