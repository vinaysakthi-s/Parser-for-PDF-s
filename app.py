#!/usr/bin/env python3
import os
import re
import json
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
import zipfile
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash

# -------------------
# Flask App Setup
# -------------------
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -------------------
# Core PDF Parsing Logic
# -------------------
def parse_toc(pdf_path):
    """Parses the Table of Contents from the PDF."""
    toc_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            max_pages = len(pdf.pages)
            # Search in the first 40 pages for the ToC
            for page in pdf.pages[:40]:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split("\n"):
                    # Regex to find lines like: "1.2.3 Section Title ...... 42"
                    match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*?)\s+(\d+)$", line)
                    if match:
                        section_id, title, page_num = match.groups()
                        page_num = int(page_num)
                        if page_num > max_pages:
                            continue
                        toc_data.append({
                            "section_id": section_id.strip(),
                            "title": title.strip().rstrip('.'),
                            "page": page_num,
                            "level": section_id.count(".") + 1
                        })
    except Exception as e:
        flash(f"Error parsing table of contents: {e}", "error")
        return None
    return toc_data

def parse_sections(pdf_path, toc):
    """Extracts content for each section defined in the TOC."""
    sections = []
    try:
        doc = fitz.open(pdf_path)
        max_pages = len(doc)
        for i, entry in enumerate(toc):
            start_page = max(0, entry["page"] - 1)
            
            # Determine end page
            if i + 1 < len(toc):
                end_page = min(max_pages, toc[i + 1]["page"] - 1)
            else:
                end_page = max_pages

            # Ensure end_page is not smaller than start_page
            if end_page <= start_page:
                end_page = min(start_page + 1, max_pages)

            text_parts = [doc[p].get_text("text") for p in range(start_page, end_page) if 0 <= p < max_pages]
            content = "\n".join(text_parts).strip()

            # Create a new dictionary to avoid modifying the original toc entry
            section_entry = entry.copy()
            section_entry["content"] = content
            sections.append(section_entry)

    except Exception as e:
        flash(f"Error extracting sections: {e}", "error")
        return None
    return sections

# -------------------
# New Output Generation Functions
# -------------------

def generate_jsonl_outputs(toc, sections, metadata, base_filename, output_dir):
    """Generates all required JSONL output files."""
    output_paths = {}

    # 1. ToC JSONL
    toc_path = os.path.join(output_dir, f"{base_filename}_toc.jsonl")
    with open(toc_path, 'w', encoding='utf-8') as f:
        for entry in toc:
            f.write(json.dumps(entry) + '\n')
    output_paths['toc'] = toc_path

    # 2. Sections (Spec) JSONL
    spec_path = os.path.join(output_dir, f"{base_filename}_spec.jsonl")
    with open(spec_path, 'w', encoding='utf-8') as f:
        for section in sections:
            f.write(json.dumps(section) + '\n')
    output_paths['spec'] = spec_path

    # 3. Metadata JSONL
    metadata_path = os.path.join(output_dir, f"{base_filename}_metadata.jsonl")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(metadata) + '\n')
    output_paths['metadata'] = metadata_path
    
    return output_paths

def generate_validation_report(toc, sections, base_filename, output_dir):
    """Generates an Excel validation report comparing ToC and parsed sections."""
    report_path = os.path.join(output_dir, f"{base_filename}_validation_report.xlsx")
    
    try:
        # Create a summary DataFrame
        summary_data = {
            "Metric": ["Total Entries in ToC", "Total Sections Parsed"],
            "Count": [len(toc), len(sections)]
        }
        summary_df = pd.DataFrame(summary_data)

        # Create a detailed comparison DataFrame
        validation_records = []
        toc_ids = {entry['section_id']: entry for entry in toc}
        section_ids = {sec['section_id']: sec for sec in sections}
        
        all_ids = sorted(list(set(toc_ids.keys()) | set(section_ids.keys())))

        for section_id in all_ids:
            record = {
                "section_id": section_id,
                "toc_title": toc_ids.get(section_id, {}).get('title', 'N/A'),
                "toc_page": toc_ids.get(section_id, {}).get('page', 'N/A'),
                "status": "",
                "notes": ""
            }
            if section_id in toc_ids and section_id in section_ids:
                record["status"] = "OK"
                record["notes"] = "Section found in ToC and successfully parsed."
            elif section_id in toc_ids:
                record["status"] = "Mismatch / Not Parsed"
                record["notes"] = "Section exists in ToC but was not found in the final parsed output."
            else:
                record["status"] = "Gap / Not in ToC"
                record["notes"] = "A section with this ID was parsed but it does not exist in the ToC."
            validation_records.append(record)
        
        detail_df = pd.DataFrame(validation_records)

        # Write to Excel
        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Validation Report', index=False, startrow=1)
            detail_df.to_excel(writer, sheet_name='Validation Report', index=False, startrow=len(summary_df) + 4)
        
        return report_path
    except Exception as e:
        flash(f"Could not generate validation report: {e}", "error")
        return None

# -------------------
# Flask Routes
# -------------------
@app.route('/')
def index():
    """Renders the main upload page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file upload, parsing, and sends a zipped archive for download."""
    if 'pdf_file' not in request.files:
        flash("No file part in the request.", "error")
        return redirect(url_for('index'))
    
    file = request.files['pdf_file']
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        flash("No PDF file selected.", "error")
        return redirect(url_for('index'))

    filename = file.filename
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(pdf_path)

    # --- Main Parsing Process ---
    toc = parse_toc(pdf_path)
    if not toc:
        flash("Failed to parse the Table of Contents. Please check if the PDF has a machine-readable ToC.", "error")
        return redirect(url_for('index'))
    
    sections = parse_sections(pdf_path, toc)
    if not sections:
        flash("Failed to extract content for the sections.", "error")
        return redirect(url_for('index'))

    base_filename = os.path.splitext(filename)[0]

    # --- Generate All Output Files ---
    
    # 1. Prepare Metadata
    doc = fitz.open(pdf_path)
    metadata = {
        "source_filename": filename,
        "total_pages": len(doc),
        "toc_entries_found": len(toc),
        "sections_parsed": len(sections)
    }
    doc.close()

    # 2. Generate JSONL files
    jsonl_paths = generate_jsonl_outputs(toc, sections, metadata, base_filename, OUTPUT_FOLDER)
    
    # 3. Generate Validation Report
    report_path = generate_validation_report(toc, sections, base_filename, OUTPUT_FOLDER)
    
    # --- Zip all generated files for download ---
    zip_filename = f"{base_filename}_output.zip"
    zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for key, path in jsonl_paths.items():
                zipf.write(path, os.path.basename(path))
            if report_path:
                zipf.write(report_path, os.path.basename(report_path))
    except Exception as e:
        flash(f"Error creating zip file: {e}", "error")
        return redirect(url_for('index'))

    # Send the zip file for download
    return send_from_directory(
        OUTPUT_FOLDER, 
        zip_filename, 
        as_attachment=True
    )

@app.route('/view/<filename>')
def view_result(filename):
    """Serves a file from the output directory (for debugging or direct access)."""
    return send_from_directory(OUTPUT_FOLDER, filename)

# -------------------
# Run Flask App
# -------------------
if __name__ == '__main__':
    print("Starting Flask app. Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)