# parser.py

import os
import re
import fitz
import pdfplumber
from flask import flash
from output_generator import OutputGenerator
from validation_reporter import ValidationReporter

# A set of common English "stop words" to filter out from tags.
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can', 'did', 'do',
    'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'has', 'have', 'having',
    'he', 'her', 'here', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it',
    'its', 'itself', 'just', 'me', 'more', 'most', 'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 'on',
    'once', 'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 's', 'same', 'she',
    'should', 'so', 'some', 'such', 't', 'than', 'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then',
    'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was',
    'we', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'you',
    'your', 'yours', 'yourself', 'yourselves'
}

class PDFParser:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.base_filename = os.path.splitext(os.path.basename(pdf_path))[0]
        self.doc_title = re.sub(r'[\-_]', ' ', self.base_filename).title()
        self.toc = None
        self.sections = None
        self.metadata = None
        self.output_generator = OutputGenerator(
            self.base_filename, self.doc_title, STOP_WORDS
        )

    def _parse_toc(self):
        """Parses the Table of Contents from the PDF."""
        toc_data = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                max_pages = len(pdf.pages)
                toc_regex = re.compile(
                    r'^(\d+(?:\.\d+)*)\s+(.*?)\s+(?:\.|\s)*\s*(\d+)$'
                )
                for page in pdf.pages[:40]:  # Search in the first 40 pages
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
        self.toc = toc_data
        return self.toc

    def _parse_sections(self):
        """Extracts content for each section defined in the TOC."""
        if not self.toc:
            self._parse_toc()
            if not self.toc:
                return None
        
        sections = []
        max_pages = len(self.doc)
        try:
            for i, entry in enumerate(self.toc):
                start_page = max(0, entry["page"] - 1)
                
                if i + 1 < len(self.toc):
                    end_page = min(max_pages, self.toc[i + 1]["page"] - 1)
                else:
                    end_page = max_pages

                if end_page <= start_page:
                    end_page = min(start_page + 1, max_pages)

                text_parts = [
                    self.doc[p].get_text("text") for p in
                    range(start_page, end_page) if 0 <= p < max_pages
                ]
                content = "\n".join(text_parts).strip()
                
                section_entry = entry.copy()
                section_entry["content"] = content
                sections.append(section_entry)
        except Exception as e:
            flash(f"Error extracting sections: {e}", "error")
            return None
        self.sections = sections
        return self.sections

    def parse(self):
        """Main method to run the full parsing process."""
        self.toc = self._parse_toc()
        if not self.toc:
            return None

        self.sections = self._parse_sections()
        if not self.sections:
            return None
        
        self.metadata = {
            "source_filename": os.path.basename(self.pdf_path),
            "total_pages": len(self.doc),
            "toc_entries_found": len(self.toc),
            "sections_parsed": len(self.sections)
        }
        
        return True

    def generate_outputs(self):
        """Generates all required JSONL output files."""
        if not self.toc or not self.sections or not self.metadata:
            return None

        output_paths = {
            'toc': self.output_generator.generate_jsonl_file(self.toc, 'toc'),
            'spec': self.output_generator.generate_jsonl_file(self.sections, 'spec', True),
            'metadata': self.output_generator.generate_metadata_file(self.metadata)
        }
        return output_paths

    def generate_validation_report(self):
        """Generates an Excel validation report."""
        if not self.toc or not self.sections:
            return None

        reporter = ValidationReporter(self.base_filename, self.toc, self.sections)
        return reporter.generate_report()