#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import tempfile
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
    
    st.subheader("💾 Storage")
    
    # Session management options
    st.write("**Session Management:**")
    auto_cleanup = st.checkbox("🧹 Auto-cleanup old sessions", 
                               value=True, 
                               help="Automatically remove old session directories (keeps 5 newest, max 24h age)")
    
    if auto_cleanup:
        col1, col2 = st.columns(2)
        max_sessions = col1.number_input("Max sessions to keep", min_value=1, max_value=20, value=5)
        max_age_hours = col2.number_input("Max age (hours)", min_value=0.5, max_value=168.0, value=24.0, step=0.5)
    else:
        max_sessions, max_age_hours = 5, 24
    
    manual_cleanup = st.checkbox("🗑️ Manual cleanup after viewing", 
                                  value=False, 
                                  help="Show cleanup button after processing")
    
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

# Initialize session state
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'manifest' not in st.session_state:
    st.session_state.manifest = None
if 'xml_content' not in st.session_state:
    st.session_state.xml_content = None

# Run
if run_btn:
    # ensure outdir exists
    Path(outdir).mkdir(parents=True, exist_ok=True)

    # Handle input file (temporary for uploads, direct for server paths)
    temp_file_handle = None
    try:
        if pdf_bytes and pdf_name:
            # Create temporary file that will be automatically cleaned up
            temp_file_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file_handle.write(pdf_bytes)
            temp_file_handle.close()
            input_path = temp_file_handle.name
            st.info(f"📤 Processing uploaded file: {pdf_name}")
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
            auto_cleanup=auto_cleanup,
            max_sessions=max_sessions,
            max_age_hours=max_age_hours,
        )
    
    finally:
        # Clean up temporary file if it was created
        if temp_file_handle and os.path.exists(temp_file_handle.name):
            try:
                os.unlink(temp_file_handle.name)
                st.success("🧹 Temporary upload file cleaned up")
            except Exception as e:
                st.warning(f"Could not clean up temporary file: {e}")

    prog_bar.progress(1.0)
    status_text.success("Done!")
    
    # Store results in session state
    st.session_state.processing_complete = True
    st.session_state.manifest = manifest
    
    # Load and store XML content
    xml_path = Path(manifest["xml"])
    if xml_path.exists():
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                st.session_state.xml_content = f.read()
        except Exception as e:
            st.warning(f"Could not load XML content: {e}")
            st.session_state.xml_content = None

# Clear session state button
if st.session_state.processing_complete:
    col_clear, col_spacer = st.columns([1, 4])
    with col_clear:
        if st.button("🔄 Process New PDF", help="Clear current results and start fresh"):
            st.session_state.processing_complete = False
            st.session_state.manifest = None
            st.session_state.xml_content = None
            st.rerun()

# Display results if processing is complete
if st.session_state.processing_complete and st.session_state.manifest:
    manifest = st.session_state.manifest
    
    # Summary metrics
    st.success(f"✅ Extraction complete - Session ID: {manifest['session_id']}")
    st.info(f"🔒 **Isolated Processing**: Files stored in session `{manifest['session_id']}` to prevent cross-contamination")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pages processed", manifest["pages_processed"])
    col2.metric("Pages OCR'd", manifest["pages_ocr"])
    col3.metric("Images extracted", manifest["images_extracted"])
    col4.metric("Tables extracted", manifest["tables_extracted"])

    xml_path = Path(manifest["xml"])
    tables_dir = Path(manifest["tables_dir"])
    images_dir = Path(manifest["images_dir"])

    tabs = st.tabs(["Overview", "Preview Pages", "XML Output", "Downloads", "Images", "Tables", "Manifest"])
    with tabs[0]:
        st.json({
            "input": manifest["input"],
            "output_dir": manifest["output_dir"],
            "session_id": manifest["session_id"],
            "session_dir": manifest["session_dir"],
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
                  st.text_area("Text", value=(p["text"][:10000] + ("..." if len(p["text"]) > 10000 else "")), height=240, key=f"text_{p['index']}")
        else:
            st.info("Set preview_pages > 0 in the sidebar to see a quick preview.")

    with tabs[2]:
        st.subheader("📄 Combined XML Output")
        
        if xml_path.exists() and st.session_state.xml_content:
            try:
                # Use XML content from session state
                xml_content = st.session_state.xml_content
                
                # Display XML file info
                file_size = xml_path.stat().st_size
                if file_size < 1024:
                    size_str = f"{file_size} bytes"
                elif file_size < 1024*1024:
                    size_str = f"{file_size/1024:.1f} KB"
                else:
                    size_str = f"{file_size/(1024*1024):.1f} MB"
                
                st.info(f"📊 **File**: `combined.xml` | **Size**: {size_str} | **Session**: {manifest['session_id']}")
                
                # Option to show full XML or truncated
                col1, col2 = st.columns([3, 1])
                with col1:
                    show_full = st.checkbox("Show full XML content", value=False, help="Warning: Large files may slow down the browser")
                with col2:
                    st.download_button("📥 Download XML", xml_content.encode(), file_name="combined.xml", mime="application/xml")
                
                # Display options
                display_mode = st.radio(
                    "Display format:",
                    ["🖥️ Formatted XML", "📝 Raw Text", "🔍 Search & Highlight"],
                    horizontal=True
                )
                
                # Determine content to display
                if show_full:
                    display_content = xml_content
                    st.warning(f"⚠️ Showing full content ({size_str}). This may take time to load for large files.")
                else:
                    # Show first 50KB for preview
                    max_chars = 50000
                    if len(xml_content) > max_chars:
                        display_content = xml_content[:max_chars]
                        truncated = True
                    else:
                        display_content = xml_content
                        truncated = False
                
                if display_mode == "🔍 Search & Highlight":
                    # Search functionality
                    search_term = st.text_input("🔍 Search in XML:", placeholder="Enter text to search...", key="xml_search")
                    
                    if search_term and search_term.strip():
                        # Count occurrences (case insensitive)
                        search_lower = search_term.lower().strip()
                        content_lower = display_content.lower()
                        count = content_lower.count(search_lower)
                        
                        if count > 0:
                            st.success(f"Found {count} occurrence(s) of '{search_term}'")
                            
                            # Case insensitive highlighting
                            import re
                            # Use regex for case-insensitive replacement
                            highlighted_content = re.sub(
                                re.escape(search_term), 
                                lambda m: f"**{m.group()}**",
                                display_content, 
                                flags=re.IGNORECASE
                            )
                            
                            st.text_area(
                                "XML Content (with highlights):",
                                value=highlighted_content,
                                height=600,
                                help="Search term highlighted in bold (case insensitive)",
                                key="xml_search_content"
                            )
                        else:
                            st.info(f"No matches found for '{search_term}'")
                            st.text_area(
                                "XML Content:", 
                                value=display_content, 
                                height=600,
                                key="xml_search_no_match"
                            )
                    else:
                        st.text_area(
                            "XML Content:", 
                            value=display_content, 
                            height=600,
                            key="xml_search_empty"
                        )
                        
                elif display_mode == "📝 Raw Text":
                    # Raw text display
                    st.text_area(
                        "Raw XML Content:",
                        value=display_content,
                        height=600,
                        help="Plain text view of XML content",
                        key="xml_raw_text"
                    )
                    
                else:  # Formatted XML
                    # Try to format XML nicely
                    try:
                        import xml.dom.minidom as minidom
                        # Parse and pretty print (only for smaller content)
                        if len(display_content) < 100000:  # Only format smaller files
                            dom = minidom.parseString(display_content)
                            pretty_xml = dom.toprettyxml(indent="  ")
                            # Remove empty lines and XML declaration
                            lines = pretty_xml.split('\n')
                            # Skip the XML declaration line and empty lines
                            filtered_lines = [line for line in lines[1:] if line.strip()]
                            pretty_xml = '\n'.join(filtered_lines)
                            st.code(pretty_xml, language="xml")
                        else:
                            st.info("File too large for formatting. Showing as plain text.")
                            st.text_area(
                                "XML Content:", 
                                value=display_content, 
                                height=600,
                                key="xml_formatted_large"
                            )
                    except Exception as e:
                        st.warning(f"Could not format XML: {e}. Showing as plain text.")
                        st.text_area(
                            "XML Content:", 
                            value=display_content, 
                            height=600,
                            key="xml_formatted_error"
                        )
                
                # Show truncation notice
                if not show_full and truncated:
                    st.info(f"📄 Showing first {max_chars:,} characters. Enable 'Show full XML content' to see everything.")
                    
            except Exception as e:
                st.error(f"Failed to read XML file: {e}")
                
        else:
            st.error("XML file not found. Please run the extraction first.")

    with tabs[3]:
        st.subheader("Downloads")
        if xml_path.exists():
            with open(xml_path, "rb") as f:
                xml_data = f.read()
            st.download_button("📥 Download combined.xml", xml_data, file_name="combined.xml", mime="application/xml")
        manifest_path = Path(outdir) / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "rb") as f:
                manifest_data = f.read()
            st.download_button("📥 Download manifest.json", manifest_data, file_name="manifest.json", mime="application/json")

    with tabs[4]:
        st.subheader("Extracted Images (first 20)")
        imgs = sorted(images_dir.glob("*.png"))[:20]
        if imgs:
            st.caption(f"Showing {len(imgs)} of {len(list(images_dir.glob('*.png')))} images.")
            st.image([str(p) for p in imgs], use_container_width=True)
        else:
            st.info("No embedded images found (or engine skipped).")

    with tabs[5]:
        st.subheader("Table Files (first 20)")
        tpaths = sorted(tables_dir.glob("*.xml"))[:20]
        if tpaths:
            st.caption(f"Showing {len(tpaths)} of {len(list(tables_dir.glob('*.xml')))} table files.")
            st.info(f"🔒 **Session Isolation**: Tables stored in isolated session `{manifest['session_id']}` directory")
            
            # Create columns for better layout
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write("**File Name**")
            col2.write("**Size**")
            col3.write("**Download**")
            
            for p in tpaths:
                col1, col2, col3 = st.columns([2, 1, 1])
                
                # Extract page and table info from filename
                filename_parts = p.stem.split('_')
                if len(filename_parts) >= 4:  # page_XXXXXX_table_XXX
                    page_num = filename_parts[1]
                    table_num = filename_parts[3]
                    display_name = f"Page {int(page_num):,} - Table {int(table_num)}"
                else:
                    display_name = p.name
                
                col1.write(display_name)
                
                # File size
                try:
                    size_bytes = p.stat().st_size
                    if size_bytes < 1024:
                        size_str = f"{size_bytes}B"
                    elif size_bytes < 1024*1024:
                        size_str = f"{size_bytes/1024:.1f}KB"
                    else:
                        size_str = f"{size_bytes/(1024*1024):.1f}MB"
                    col2.write(size_str)
                except:
                    col2.write("N/A")
                
                # Download button
                with col3:
                    with open(p, "rb") as f:
                        file_data = f.read()
                    st.download_button(
                        label="📥",
                        data=file_data,
                        file_name=p.name,
                        mime="application/xml",
                        key=str(p),
                        help=f"Download {p.name}"
                    )
        else:
            st.info("No tables detected (or no table engine available).")
            st.write("💡 **Tips for better table detection:**")
            st.write("- Ensure your PDF contains clear, structured tables")
            st.write("- Try different table engines (Camelot vs Tabula)")
            st.write("- Check if tables are text-based rather than image-based")

    with tabs[6]:
        st.subheader("Manifest")
        man_path = Path(outdir) / "manifest.json"
        if man_path.exists():
            import json
            st.json(json.loads(man_path.read_text(encoding="utf-8")))
        else:
            st.info("manifest.json not found.")
    
    # Session cleanup information and manual controls
    if manual_cleanup:
        st.markdown("---")
        st.subheader("🧹 Session Management")
        
        # Show current session info
        session_path = Path(manifest['session_dir'])
        if session_path.exists():
            try:
                from pdf_to_universal_xml import _get_directory_size_mb
                session_size = _get_directory_size_mb(session_path)
                st.info(f"💾 Current session size: **{session_size:.1f} MB**")
            except:
                st.info("💾 Current session is active")
        
        # Manual session cleanup
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Delete Current Session", help="Remove this session's files to save disk space"):
                try:
                    import shutil
                    if session_path.exists():
                        shutil.rmtree(session_path)
                        st.success(f"✅ Deleted session {manifest['session_id']}")
                        st.info("🔄 Refresh the page to process another PDF")
                        st.rerun()
                    else:
                        st.info("Session already cleaned up")
                except Exception as e:
                    st.error(f"Failed to delete session: {e}")
        
        with col2:
            if st.button("🧹 Cleanup All Old Sessions", help="Remove all old sessions based on settings"):
                try:
                    from pdf_to_universal_xml import _cleanup_old_sessions
                    cleanup_stats = _cleanup_old_sessions(Path(outdir), max_sessions, max_age_hours)
                    
                    if cleanup_stats['sessions_removed'] > 0:
                        st.success(f"✅ Cleaned up {cleanup_stats['sessions_removed']} old sessions")
                        st.info(f"💾 Freed {cleanup_stats['space_freed_mb']:.1f} MB of disk space")
                        st.info(f"📁 Kept {cleanup_stats['sessions_kept']} recent sessions")
                    else:
                        st.info("No old sessions to clean up")
                except Exception as e:
                    st.error(f"Failed to cleanup old sessions: {e}")
    
    # Show automatic cleanup info and stats
    if auto_cleanup and 'cleanup_stats' in manifest:
        st.markdown("---")
        st.subheader("⚙️ Automatic Cleanup Report")
        
        cleanup_stats = manifest['cleanup_stats']
        
        if cleanup_stats['sessions_removed'] > 0:
            st.success(f"🧹 **Auto-cleanup completed**: Removed {cleanup_stats['sessions_removed']} old sessions")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Sessions Found", cleanup_stats['sessions_found'])
            col2.metric("Sessions Removed", cleanup_stats['sessions_removed'])
            col3.metric("Space Freed", f"{cleanup_stats['space_freed_mb']:.1f} MB")
            
            if cleanup_stats['cleanup_reason']:
                st.info("📝 **Cleanup Details**: " + ", ".join(cleanup_stats['cleanup_reason']))
        else:
            st.info("⚙️ **Auto-cleanup**: No old sessions found to remove")
            st.caption(f"Settings: Keep {max_sessions} sessions, max {max_age_hours}h age")
    elif auto_cleanup:
        st.markdown("---")
        st.info(f"⚙️ **Auto-cleanup enabled**: Keeping {max_sessions} newest sessions, max {max_age_hours}h age")
