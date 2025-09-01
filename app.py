#!/usr/bin/env python3
import os
import zipfile
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
from parser import PDFParser

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

    parser = PDFParser(pdf_path)
    if not parser.parse():
        return redirect(url_for('index'))

    output_files = parser.generate_outputs()
    if not output_files:
        return redirect(url_for('index'))
    
    report_path = parser.generate_validation_report()
    if report_path:
        output_files['report'] = report_path

    zip_filename = f"{parser.base_filename}_output.zip"
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