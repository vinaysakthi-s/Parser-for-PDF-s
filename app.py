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

# A set of common English "stop words" to filter out from tags.
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can', 'did', 'do',
    'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'has', 'have', 'having',
    'he', 'her', 'here', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it',
    'its', 'itself', 'just', 'me', 'more', 'most', 'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 'on',
    'once', 'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 's', 'same', 'she', 'should',
    'so', 'some', 'such', 't', 'than', 'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there',

    'these', 'they', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were',
    'what', 'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'you', 'your', 'yours',
    'yourself', 'yourselves'
}

# -------------------
# Core PDF Parsing Logic
# -------------------
def parse_toc(pdf_path):
    """Parses the Table of Contents from the PDF."""
    toc_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            max_pages = len(pdf.pages)
            # Example Regex: ^(\d+(.\d+)*)(\s+)([^\n.]+)(.+)\s+(\d+)$
            # Using a simpler, more robust regex for broader compatibility.
            toc_regex = re.compile(r'^(\d+(?:\.\d+)*)\s+(.*?)\s+(?:\.|\s)*\s*(\d+)$')

            for page in pdf.pages[:40]: # Search in the first 40 pages
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                if not text:
                    continue
                for line in text.split("\n"):
                    match = toc_regex.match(line)
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
            
            if i + 1 < len(toc):
                end_page = min(max_pages, toc[i + 1]["page"] - 1)
            else:
                end_page = max_pages

            if end_page <= start_page:
                end_page = min(start_page + 1, max_pages)

            text_parts = [doc[p].get_text("text") for p in range(start_page, end_page) if 0 <= p < max_pages]
            content = "\n".join(text_parts).strip()
            
            section_entry = entry.copy()
            section_entry["content"] = content
            sections.append(section_entry)

    except Exception as e:
        flash(f"Error extracting sections: {e}", "error")
        return None
    return sections

# -------------------
# Final Output Generation
# -------------------

def generate_jsonl_outputs(toc, sections, metadata, base_filename, output_dir):
    """Generates all required JSONL output files with the specified schema."""
    output_paths = {}
    doc_title = re.sub(r'[\-_]', ' ', base_filename).title()

    def create_structured_entry(entry_data):
        """Helper function to create the detailed JSON object per the new schema."""
        section_id = entry_data['section_id']
        title = entry_data.get('title', '')
        
        # Determine parent_id
        parent_id = '.'.join(section_id.split('.')[:-1]) if '.' in section_id else None
        
        # Generate tags from the title
        words = re.findall(r'\b[a-z]+\b', title.lower())
        tags = sorted(list(set(word for word in words if word not in STOP_WORDS)))

        return {
            "doc_title": doc_title,
            "section_id": section_id,
            "title": title,
            "page": entry_data.get('page'),
            "level": entry_data.get('level'),
            "parent_id": parent_id,
            "full_path": f"{section_id} {title}",
            "tags": tags
        }

    # 1. ToC JSONL
    toc_path = os.path.join(output_dir, f"{base_filename}_toc.jsonl")
    with open(toc_path, 'w', encoding='utf-8') as f:
        for entry in toc:
            structured_entry = create_structured_entry(entry)
            f.write(json.dumps(structured_entry, ensure_ascii=False) + '\n')
    output_paths['toc'] = toc_path

    # 2. Sections (Spec) JSONL
    spec_path = os.path.join(output_dir, f"{base_filename}_spec.jsonl")
    with open(spec_path, 'w', encoding='utf-8') as f:
        for section in sections:
            structured_entry = create_structured_entry(section)
            structured_entry['content'] = section.get('content', '') 
            f.write(json.dumps(structured_entry, ensure_ascii=False) + '\n')
    output_paths['spec'] = spec_path

    # 3. Metadata JSONL
    metadata_path = os.path.join(output_dir, f"{base_filename}_metadata.jsonl")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
    output_paths['metadata'] = metadata_path
    
    return output_paths

def generate_validation_report(toc, sections, base_filename, output_dir):
    """Generates an Excel validation report."""
    report_path = os.path.join(output_dir, f"{base_filename}_validation_report.xlsx")
    
    try:
        summary_df = pd.DataFrame({
            "Metric": ["Total Entries in ToC", "Total Sections Parsed"],
            "Count": [len(toc), len(sections)]
        })

        toc_map = {entry['section_id']: entry for entry in toc}
        sections_map = {sec['section_id']: sec for sec in sections}
        all_ids = sorted(list(set(toc_map.keys()) | set(sections_map.keys())))

        validation_records = []
        for section_id in all_ids:
            record = { "section_id": section_id }
            status = "OK"
            notes = ""
            
            if section_id in toc_map and section_id in sections_map:
                notes = "Section found in ToC and parsed."
            elif section_id in toc_map:
                status = "Mismatch / Not Parsed"
                notes = "Section in ToC but not found in parsed output."
            else: # in sections_map only
                status = "Gap / Not in ToC"
                notes = "Section parsed but does not exist in ToC."

            record.update({
                "toc_title": toc_map.get(section_id, {}).get('title', 'N/A'),
                "toc_page": toc_map.get(section_id, {}).get('page', 'N/A'),
                "status": status, "notes": notes
            })
            validation_records.append(record)
        
        detail_df = pd.DataFrame(validation_records)

        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Validation', index=False, startrow=1)
            detail_df.to_excel(writer, sheet_name='Validation', index=False, startrow=len(summary_df) + 4)
        
        return report_path
    except Exception as e:
        flash(f"Could not generate validation report: {e}", "error")
        return None

# -------------------
# Flask Routes
# -------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
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

    toc = parse_toc(pdf_path)
    if not toc:
        flash("Failed to parse the Table of Contents. Please check if the PDF has a machine-readable ToC.", "error")
        return redirect(url_for('index'))
    
    sections = parse_sections(pdf_path, toc)
    if not sections:
        flash("Failed to extract content for the sections.", "error")
        return redirect(url_for('index'))

    base_filename = os.path.splitext(filename)[0]

    with fitz.open(pdf_path) as doc:
        metadata = {
            "source_filename": filename,
            "total_pages": len(doc),
            "toc_entries_found": len(toc),
            "sections_parsed": len(sections)
        }
    
    output_files = generate_jsonl_outputs(toc, sections, metadata, base_filename, OUTPUT_FOLDER)
    report_path = generate_validation_report(toc, sections, base_filename, OUTPUT_FOLDER)
    if report_path:
        output_files['report'] = report_path

    zip_filename = f"{base_filename}_output.zip"
    zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for key, path in output_files.items():
                zipf.write(path, os.path.basename(path))
    except Exception as e:
        flash(f"Error creating zip file: {e}", "error")
        return redirect(url_for('index'))

    return send_from_directory(OUTPUT_FOLDER, zip_filename, as_attachment=True)

# -------------------
# Run Flask App
# -------------------
if __name__ == '__main__':
    print("🚀 Starting Flask PDF Parser. Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)