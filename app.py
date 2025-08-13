#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
from pathlib import Path
import xml.etree.ElementTree as ET

import streamlit as st

# If you installed Tesseract in a custom path, uncomment & edit the next line:
# import pytesseract; pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from pdf_to_universal_xml import process_pdf  # our backend

st.set_page_config(page_title="Universal PDF Extractor (Large-file Friendly)", page_icon="📄", layout="wide")

st.title("📄 Universal PDF Extractor (Large-file Friendly)")
st.caption("Process huge PDFs: text + OCR fallback + images + tables → Combined XML")

with st.sidebar:
    st.header("⚙️ Settings")
    # Processing mode
    mode = st.radio("Input Mode", ["Server file path (recommended for large files)", "Upload (smaller files)"], index=0)

    st.subheader("Pages")
    start_page = st.number_input("Start page (1-based)", min_value=1, value=1)
    end_page = st.number_input("End page (0 = till end)", min_value=0, value=0)

    st.subheader("OCR")
    ocr_threshold = st.slider("OCR threshold (min chars before OCR)", min_value=0, max_value=500, value=40)
    dpi = st.select_slider("OCR render DPI", options=[150, 200, 300, 400], value=300)
    ocr_lang = st.text_input("Tesseract languages", value="eng", help="e.g., eng or eng+deu")
    ocr_psm = st.selectbox("PSM", options=["3", "4", "6", "11", "12", "13"], index=0)
    ocr_oem = st.selectbox("OEM", options=["3", "1", "0", "2"], index=0)

    st.subheader("Tables")
    tbl_order = st.multiselect("Table engines (order of preference)", ["camelot", "tabula"], default=["camelot", "tabula"])

    st.subheader("Preview")
    preview_pages = st.slider("Preview first N pages (for UI)", min_value=0, max_value=50, value=10)

    st.markdown("---")
    outdir = st.text_input("Output directory", value=str(Path.cwd() / "output"))
    run_btn = st.button("🚀 Run Extraction")

# input section
pdf_bytes = None
pdf_name = None
server_path = None

st.markdown("### 📥 Input")
if mode.startswith("Server"):
    server_path = st.text_input("Absolute path to PDF on server (e.g., /data/inbox/huge.pdf or C:\\data\\huge.pdf)")
else:
    up = st.file_uploader("Upload a PDF (prefer small/medium files here)", type=["pdf"])
    if up:
        pdf_bytes = up.read()
        pdf_name = up.name

# progress placeholders
prog_bar = st.progress(0)
status_text = st.empty()

def _progress_cb(done, total):
    if total <= 0:
        frac = 0.0
    else:
        frac = min(max(done / total, 0), 1)
    prog_bar.progress(frac)
    status_text.info(f"Processing pages: {done}/{total}")

def _read_first_n_pages_from_xml(xml_path: Path, n: int):
    pages = []
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        content = root.find("content")
        if content is None:
            return pages
        for page in content.findall("page")[:n]:
            idx = page.attrib.get("index", "?")
            text_el = page.find("text")
            text = text_el.text if text_el is not None else ""
            pages.append({"index": idx, "text": text or ""})
    except Exception as e:
        st.warning(f"Failed to parse XML preview: {e}")
    return pages

# Run
if run_btn:
    # ensure outdir exists
    Path(outdir).mkdir(parents=True, exist_ok=True)

    # persist uploaded file to a temp path if needed
    if pdf_bytes and pdf_name:
        temp_path = Path(outdir) / f"_upload_{pdf_name}"
        with open(temp_path, "wb") as f:
            f.write(pdf_bytes)
        input_path = str(temp_path)
    elif server_path:
        input_path = server_path
    else:
        st.error("Please provide a server file path or upload a PDF.")
        st.stop()

    if not os.path.exists(input_path):
        st.error(f"File not found: {input_path}")
        st.stop()

    st.info("Starting extraction… (this may take a while for large PDFs)")
    prog_bar.progress(0)

    manifest = process_pdf(
        input_pdf=input_path,
        outdir=outdir,
        start_page=int(start_page),
        end_page=int(end_page),
        ocr_threshold=int(ocr_threshold),
        dpi=int(dpi),
        ocr_lang=ocr_lang.strip(),
        ocr_psm=str(ocr_psm),
        ocr_oem=str(ocr_oem),
        table_order=tbl_order if tbl_order else ["camelot", "tabula"],
        progress_cb=_progress_cb,
    )

    prog_bar.progress(1.0)
    status_text.success("Done!")

    # Summary metrics
    st.success("✅ Extraction complete")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pages processed", manifest["pages_processed"])
    col2.metric("Pages OCR'd", manifest["pages_ocr"])
    col3.metric("Images extracted", manifest["images_extracted"])
    col4.metric("Tables extracted", manifest["tables_extracted"])

    xml_path = Path(manifest["xml"])
    tables_dir = Path(manifest["tables_dir"])
    images_dir = Path(manifest["images_dir"])

    tabs = st.tabs(["Overview", "Preview Pages", "Downloads", "Images", "Tables", "Manifest"])
    with tabs[0]:
        st.json({
            "input": manifest["input"],
            "output_dir": manifest["output_dir"],
            "xml": manifest["xml"],
            "tables_dir": manifest["tables_dir"],
            "images_dir": manifest["images_dir"],
            "ocr_available": manifest["ocr_available"],
            "camelot_available": manifest["camelot_available"],
            "tabula_available": manifest["tabula_available"],
            "params": manifest["params"],
        })

    with tabs[1]:
        st.subheader(f"Preview (first {preview_pages} pages)")
        if preview_pages > 0:
            pages = _read_first_n_pages_from_xml(xml_path, preview_pages)
            for p in pages:
                with st.expander(f"📄 Page {p['index']}"):
                    st.text_area("Text", value=(p["text"][:10000] + ("..." if len(p["text"]) > 10000 else "")), height=240)
        else:
            st.info("Set preview_pages > 0 in the sidebar to see a quick preview.")

    with tabs[2]:
        st.subheader("Downloads")
        if xml_path.exists():
            with open(xml_path, "rb") as f:
                st.download_button("📥 Download combined.xml", f, file_name="combined.xml", mime="application/xml")
        manifest_path = Path(outdir) / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "rb") as f:
                st.download_button("📥 Download manifest.json", f, file_name="manifest.json", mime="application/json")

    with tabs[3]:
        st.subheader("Extracted Images (first 20)")
        imgs = sorted(images_dir.glob("*.png"))[:20]
        if imgs:
            st.caption(f"Showing {len(imgs)} of {len(list(images_dir.glob('*.png')))} images.")
            st.image([str(p) for p in imgs], use_container_width=True)
        else:
            st.info("No embedded images found (or engine skipped).")

    with tabs[4]:
        st.subheader("Table Files (first 20)")
        tpaths = sorted(tables_dir.glob("*.xml"))[:20]
        if tpaths:
            for p in tpaths:
                with open(p, "rb") as f:
                    st.download_button(label=f"Download {p.name}", data=f.read(), file_name=p.name, mime="application/xml", key=str(p))
        else:
            st.info("No tables detected (or no table engine available).")

    with tabs[5]:
        st.subheader("Manifest")
        man_path = Path(outdir) / "manifest.json"
        if man_path.exists():
            import json
            st.json(json.loads(man_path.read_text(encoding="utf-8")))
        else:
            st.info("manifest.json not found.")
