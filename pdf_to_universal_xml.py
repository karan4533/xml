#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF → Universal XML (streaming, large-file friendly)

- Streams pages; constant memory
- Text: PyMuPDF per page
- OCR fallback (pytesseract) for low-text pages
- Images: embedded image extraction (per page)
- Tables: Camelot → Tabula fallback, page-by-page
- Outputs:
  - combined.xml (single XML with all page text + references)
  - tables/page_{n}_table_{k}.xml (per-table XML)
  - assets/images/... (extracted images)
  - manifest.json (run summary)

CLI and callable function: process_pdf(...)
"""

import os
import io
import sys
import json
import math
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import fitz  # PyMuPDF
from lxml import etree

# OCR (optional)
OCR_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    import numpy as np
    import cv2
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# Tables (optional)
CAMELOT_AVAILABLE = False
TABULA_AVAILABLE = False
try:
    import camelot
    CAMELOT_AVAILABLE = True
except Exception:
    pass
try:
    import tabula
    TABULA_AVAILABLE = True
except Exception:
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _safe_write_text(path: Path, data: str, encoding="utf-8"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding, errors="ignore") as f:
        f.write(data)


def _page_to_image(page, dpi: int = 300) -> "Image.Image":
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    from PIL import Image  # local import
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def _ocr_image(pil_img: "Image.Image", lang: str = "eng", psm: str = "3", oem: str = "3", timeout: int = 120) -> str:
    if not OCR_AVAILABLE:
        return ""
    config = f"--psm {psm} --oem {oem}"
    import numpy as np  # local import
    import cv2
    img = np.array(pil_img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    from PIL import Image
    pil_proc = Image.fromarray(th)
    try:
        return pytesseract.image_to_string(pil_proc, lang=lang, config=config, timeout=timeout)
    except Exception:
        try:
            return pytesseract.image_to_string(pil_img, lang=lang, config=config, timeout=timeout)
        except Exception:
            return ""


def _extract_embedded_images(doc, page, page_index: int, outdir: Path) -> List[Dict[str, Any]]:
    results = []
    for img_idx, info in enumerate(page.get_images(full=True)):
        xref = info[0]
        try:
            pix = fitz.Pixmap(doc, xref)
            if pix.n >= 5:  # has alpha or CMYK
                pix = fitz.Pixmap(fitz.csRGB, pix)
            img_bytes = pix.tobytes("png")
            img_path = outdir / f"page_{page_index+1:06d}_img_{img_idx+1:03d}.png"
            _safe_write_bytes(img_path, img_bytes)
            results.append({
                "index": img_idx + 1,
                "path": str(img_path),
                "width": pix.width,
                "height": pix.height,
            })
        except Exception:
            continue
    return results


def _extract_tables_page(pdf_path: str, page_number_1based: int, table_order: List[str], tables_dir: Path) -> List[Dict[str, Any]]:
    found_tables = []
    global_table_index = 1  # Global counter for consistent table numbering

    def export_tables_camelot(flavor: str) -> List[Dict[str, Any]]:
        nonlocal global_table_index
        out = []
        try:
            tables = camelot.read_pdf(pdf_path, pages=str(page_number_1based), flavor=flavor, suppress_stdout=True)
            for i, t in enumerate(tables):
                xml_path = tables_dir / f"page_{page_number_1based:06d}_table_{global_table_index:03d}.xml"
                t.to_xml(str(xml_path))
                out.append({
                    "engine": f"camelot-{flavor}", 
                    "path": str(xml_path),
                    "index": global_table_index,
                    "page": page_number_1based
                })
                global_table_index += 1
        except Exception:
            pass
        return out

    def export_tables_tabula() -> List[Dict[str, Any]]:
        nonlocal global_table_index
        out = []
        try:
            dfs = tabula.read_pdf(pdf_path, pages=page_number_1based, multiple_tables=True, guess=True, lattice=False, stream=True)
            for i, df in enumerate(dfs or []):
                root = etree.Element("table", engine="tabula")
                for _, row in df.iterrows():
                    row_el = etree.SubElement(root, "tr")
                    for cell in row:
                        cell_el = etree.SubElement(row_el, "td")
                        cell_el.text = "" if (cell is None or (isinstance(cell, float) and math.isnan(cell))) else str(cell)
                xml_path = tables_dir / f"page_{page_number_1based:06d}_table_{global_table_index:03d}.xml"
                _safe_write_bytes(xml_path, etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))
                out.append({
                    "engine": "tabula", 
                    "path": str(xml_path),
                    "index": global_table_index,
                    "page": page_number_1based
                })
                global_table_index += 1
        except Exception:
            pass
        return out

    for engine in table_order:
        if engine == "camelot" and CAMELOT_AVAILABLE:
            got = export_tables_camelot("lattice") or export_tables_camelot("stream")
            found_tables.extend(got)
            if got:
                break
        elif engine == "tabula" and TABULA_AVAILABLE:
            got = export_tables_tabula()
            found_tables.extend(got)
            if got:
                break

    return found_tables


def _build_xml_scaffold(input_pdf: str, total_pages: int, start_page: int, end_page: int) -> etree._ElementTree:
    root = etree.Element("document")
    meta = etree.SubElement(root, "metadata")
    etree.SubElement(meta, "generator").text = "pdf_to_universal_xml"
    etree.SubElement(meta, "version").text = "1.0"
    etree.SubElement(meta, "timestamp").text = _now_iso()
    file_meta = etree.SubElement(meta, "file")
    etree.SubElement(file_meta, "path").text = os.path.abspath(input_pdf)
    etree.SubElement(file_meta, "pages").text = str(total_pages)
    etree.SubElement(file_meta, "start_page").text = str(start_page)
    etree.SubElement(file_meta, "end_page").text = str(end_page)
    etree.SubElement(root, "content")
    return etree.ElementTree(root)


def _cleanup_old_sessions(output_dir: Path, max_sessions: int = 5, max_age_hours: float = 24.0) -> Dict[str, Any]:
    """
    Clean up old session directories to manage disk space.
    
    Args:
        output_dir: Main output directory containing session folders
        max_sessions: Maximum number of sessions to keep (oldest removed first)
        max_age_hours: Maximum age in hours before session is eligible for cleanup
    
    Returns:
        Dict with cleanup statistics
    """
    import time
    import shutil
    
    cleanup_stats = {
        "sessions_found": 0,
        "sessions_removed": 0,
        "sessions_kept": 0,
        "space_freed_mb": 0,
        "cleanup_reason": []
    }
    
    try:
        if not output_dir.exists():
            return cleanup_stats
            
        # Find all session directories
        session_dirs = [d for d in output_dir.iterdir() 
                       if d.is_dir() and d.name.startswith('session_')]
        
        cleanup_stats["sessions_found"] = len(session_dirs)
        
        if len(session_dirs) <= 1:  # Keep at least current session
            cleanup_stats["sessions_kept"] = len(session_dirs)
            return cleanup_stats
        
        # Sort by modification time (newest first)
        session_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        current_time = time.time()
        sessions_to_remove = []
        
        # Strategy 1: Remove sessions older than max_age_hours
        for session_dir in session_dirs:
            age_hours = (current_time - session_dir.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                sessions_to_remove.append((session_dir, f"aged_{age_hours:.1f}h"))
        
        # Strategy 2: Keep only max_sessions newest sessions
        if len(session_dirs) > max_sessions:
            excess_sessions = session_dirs[max_sessions:]
            for session_dir in excess_sessions:
                if not any(s[0] == session_dir for s in sessions_to_remove):
                    sessions_to_remove.append((session_dir, "excess_count"))
        
        # Remove identified sessions
        for session_dir, reason in sessions_to_remove:
            try:
                # Calculate size before removal
                size_mb = _get_directory_size_mb(session_dir)
                
                shutil.rmtree(session_dir)
                cleanup_stats["sessions_removed"] += 1
                cleanup_stats["space_freed_mb"] += size_mb
                cleanup_stats["cleanup_reason"].append(f"{session_dir.name}:{reason}")
                
            except Exception as e:
                # Log error but continue cleanup
                cleanup_stats["cleanup_reason"].append(f"{session_dir.name}:error_{str(e)[:50]}")
        
        cleanup_stats["sessions_kept"] = cleanup_stats["sessions_found"] - cleanup_stats["sessions_removed"]
        
    except Exception as e:
        cleanup_stats["cleanup_reason"].append(f"cleanup_error:{str(e)[:50]}")
    
    return cleanup_stats


def _get_directory_size_mb(directory: Path) -> float:
    """Calculate total size of directory in MB."""
    total_size = 0
    try:
        for path in directory.rglob('*'):
            if path.is_file():
                total_size += path.stat().st_size
    except Exception:
        pass
    return total_size / (1024 * 1024)


def _append_page(tree: etree._ElementTree, page_index: int, text: str, images: List[Dict[str, Any]], tables: List[Dict[str, Any]]):
    root = tree.getroot()
    content = root.find("content")
    p = etree.SubElement(content, "page", index=str(page_index + 1))

    txt_el = etree.SubElement(p, "text")
    import re
    def clean_xml_text(s):
        # Remove all control characters except tab(\t), newline(\n), carriage return(\r)
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', s)
    cleaned_text = clean_xml_text((text or "").replace("\r", "").strip())
    txt_el.text = etree.CDATA(cleaned_text)

    if images:
        imgs_el = etree.SubElement(p, "images")
        for im in images:
            etree.SubElement(imgs_el, "image",
                             index=str(im["index"]),
                             path=im["path"],
                             width=str(im["width"]),
                             height=str(im["height"]))
    if tables:
        tbls_el = etree.SubElement(p, "tables")
        for t in tables:
            etree.SubElement(tbls_el, "table_ref",
                             engine=t.get("engine", "unknown"),
                             path=t["path"])


def process_pdf(
    input_pdf: str,
    outdir: str,
    start_page: int = 1,
    end_page: int = 0,
    ocr_threshold: int = 40,
    dpi: int = 300,
    ocr_lang: str = "eng",
    ocr_psm: str = "3",
    ocr_oem: str = "3",
    table_order: Optional[List[str]] = None,
    progress_cb: Optional[callable] = None,  # for Streamlit progress
    auto_cleanup: bool = False,
    max_sessions: int = 5,
    max_age_hours: float = 24.0,
) -> Dict[str, Any]:
    """
    Streaming processor. Returns manifest dict.
    """
    table_order = table_order or ["camelot", "tabula"]
    out_dir = Path(outdir)
    
    # Create session-based directory structure to prevent cross-contamination
    import time
    import hashlib
    
    # Generate unique session ID based on input file and timestamp
    session_id = hashlib.md5(f"{input_pdf}_{time.time()}_{start_page}_{end_page}".encode()).hexdigest()[:12]
    
    # Create session-specific subdirectories
    session_dir = out_dir / f"session_{session_id}"
    tables_dir = session_dir / "tables"
    images_dir = session_dir / "assets" / "images"
    
    # Clear and recreate directories to ensure clean state
    import shutil
    if session_dir.exists():
        shutil.rmtree(session_dir)
        
    session_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Also ensure main output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(input_pdf)
    try:
        total_pages = doc.page_count
        if end_page <= 0 or end_page > total_pages:
            end_page = total_pages
        if start_page < 1:
            start_page = 1

        xml_tree = _build_xml_scaffold(input_pdf, total_pages, start_page, end_page)

        stats = {"pages": 0, "ocr_pages": 0, "images": 0, "tables": 0}

        num_pages_to_do = end_page - start_page + 1
        for idx in range(start_page - 1, end_page):
            page = doc[idx]

            text = page.get_text("text") or ""
            did_ocr = False
            if (len(text.strip()) < ocr_threshold) and OCR_AVAILABLE:
                pil_img = _page_to_image(page, dpi=dpi)
                ocr_txt = _ocr_image(pil_img, lang=ocr_lang, psm=ocr_psm, oem=ocr_oem)
                if len(ocr_txt.strip()) > len(text.strip()):
                    text = ocr_txt
                    did_ocr = True

            imgs = _extract_embedded_images(doc, page, idx, images_dir)
            stats["images"] += len(imgs)

            tbls = []
            try:
                tbls = _extract_tables_page(input_pdf, idx + 1, table_order, tables_dir)
            except Exception:
                tbls = []
            stats["tables"] += len(tbls)

            _append_page(xml_tree, idx, text, imgs, tbls)

            stats["pages"] += 1
            if did_ocr:
                stats["ocr_pages"] += 1

            if progress_cb:
                progress_cb(stats["pages"], num_pages_to_do)

        xml_path = session_dir / "combined.xml"
        _safe_write_bytes(xml_path, etree.tostring(xml_tree, pretty_print=True, encoding="utf-8", xml_declaration=True))

        manifest = {
            "input": os.path.abspath(input_pdf),
            "output_dir": str(out_dir),
            "session_dir": str(session_dir),
            "session_id": session_id,
            "xml": str(xml_path),
            "tables_dir": str(tables_dir),
            "images_dir": str(images_dir),
            "pages_processed": stats["pages"],
            "pages_ocr": stats["ocr_pages"],
            "images_extracted": stats["images"],
            "tables_extracted": stats["tables"],
            "started": _now_iso(),
            "finished": _now_iso(),
            "ocr_available": OCR_AVAILABLE,
            "camelot_available": CAMELOT_AVAILABLE,
            "tabula_available": TABULA_AVAILABLE,
            "params": {
                "start_page": start_page,
                "end_page": end_page,
                "ocr_threshold": ocr_threshold,
                "dpi": dpi,
                "ocr_lang": ocr_lang,
                "ocr_psm": ocr_psm,
                "ocr_oem": ocr_oem,
                "table_order": table_order,
            },
        }

        _safe_write_text(out_dir / "manifest.json", json.dumps(manifest, indent=2))
        
        # Optional: Clean up old sessions automatically (only if enabled)
        cleanup_stats = {}
        if auto_cleanup:
            cleanup_stats = _cleanup_old_sessions(out_dir, max_sessions=max_sessions, max_age_hours=max_age_hours)
        
        # Add cleanup stats to manifest for transparency
        manifest["cleanup_stats"] = cleanup_stats
        
        return manifest
        
    finally:
        # Always close the PDF document to free resources
        doc.close()


# CLI entry (optional)
def _parse_args():
    ap = argparse.ArgumentParser(description="Large-file friendly PDF → Universal XML")
    ap.add_argument("--input", required=True, help="Input PDF path")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--end-page", type=int, default=0)
    ap.add_argument("--ocr-threshold", type=int, default=40)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--ocr-lang", type=str, default="eng")
    ap.add_argument("--ocr-psm", type=str, default="3")
    ap.add_argument("--ocr-oem", type=str, default="3")
    ap.add_argument("--tables", type=str, default="camelot,tabula")
    return ap.parse_args()


def main():
    args = _parse_args()
    table_order = [t.strip().lower() for t in args.tables.split(",") if t.strip() in ("camelot", "tabula")]
    manifest = process_pdf(
        input_pdf=args.input,
        outdir=args.outdir,
        start_page=args.start_page,
        end_page=args.end_page,
        ocr_threshold=args.ocr_threshold,
        dpi=args.dpi,
        ocr_lang=args.ocr_lang,
        ocr_psm=args.ocr_psm,
        ocr_oem=args.ocr_oem,
        table_order=table_order or ["camelot", "tabula"],
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
