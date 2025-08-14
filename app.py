#!/usr/bin/env python3
import os
import re
import json
import fitz  # PyMuPDF
import pdfplumber
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
# Core PDF Parsing Logic (No changes here)
# -------------------
def parse_toc(pdf_path):
    """Parses the Table of Contents from the PDF."""
    toc_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            max_pages = len(pdf.pages)
            for page in pdf.pages[:40]:
                text = page.extract_text()
                if not text: continue
                for line in text.split("\n"):
                    match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*?)\s+(\d+)$", line)
                    if match:
                        section_id, title, page_num = match.groups()
                        page_num = int(page_num)
                        if page_num > max_pages: continue
                        toc_data.append({
                            "section_id": section_id.strip(),
                            "title": title.strip(),
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
            if i + 1 < len(toc):
                end_page = min(max_pages, toc[i + 1]["page"] - 1)
            else:
                end_page = max_pages
            if end_page <= start_page:
                end_page = min(start_page + 1, max_pages)
            text_parts = [doc[p].get_text() for p in range(start_page, end_page) if 0 <= p < max_pages]
            entry["content"] = "\n".join(text_parts).strip()
            sections.append(entry)
    except Exception as e:
        flash(f"Error extracting sections: {e}", "error")
        return None
    return sections

# -------------------
# Flask Routes
# -------------------
@app.route('/')
def index():
    """Renders the main upload page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file upload, parsing, and sends a JSON file for download."""
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

    # --- Run the parsing process ---
    toc = parse_toc(pdf_path)
    if not toc:
        return redirect(url_for('index'))
    
    sections = parse_sections(pdf_path, toc)
    if not sections:
        return redirect(url_for('index'))

    # --- CHANGE: Save data as JSON and prepare for download ---
    base_filename = os.path.splitext(filename)[0]
    json_filename = f"{base_filename}.json"
    json_path = os.path.join(OUTPUT_FOLDER, json_filename)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, indent=4, ensure_ascii=False)
        
    # --- CHANGE: Send the file for download instead of rendering a view ---
    return send_from_directory(
        OUTPUT_FOLDER, 
        json_filename, 
        as_attachment=True # This is crucial, it triggers the browser's download prompt
    )

# The '/view' route is no longer used but can be left for future use
@app.route('/view/<filename>')
def view_result(filename):
    """Serves a file from the output directory."""
    return send_from_directory(OUTPUT_FOLDER, filename)

# -------------------
# Run Flask App
# -------------------
if __name__ == '__main__':
    print("Starting Flask app. Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)