# parser.py

import os
import re
import json
import fitz
import pdfplumber
import pandas as pd
from flask import flash

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

    def _create_structured_entry(self, entry_data):
        """Helper function to create a detailed JSON object."""
        section_id = entry_data['section_id']
        title = entry_data.get('title', '')
        
        # Determine parent_id
        parent_id = '.'.join(section_id.split('.')[:-1]) if '.' in section_id else None
        
        # Generate tags from the title
        words = re.findall(r'\b[a-z]+\b', title.lower())
        tags = sorted(
            list(set(word for word in words if word not in STOP_WORDS))
        )

        return {
            "doc_title": self.doc_title,
            "section_id": section_id,
            "title": title,
            "page": entry_data.get('page'),
            "level": entry_data.get('level'),
            "parent_id": parent_id,
            "full_path": f"{section_id} {title}",
            "tags": tags
        }

    def _generate_jsonl_file(self, data_list, file_suffix, add_content=False):
        """Generates a JSONL file from a list of data entries."""
        output_path = os.path.join(
            "outputs", f"{self.base_filename}_{file_suffix}.jsonl"
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in data_list:
                structured_entry = self._create_structured_entry(entry)
                if add_content:
                    structured_entry['content'] = entry.get('content', '') 
                f.write(json.dumps(structured_entry, ensure_ascii=False) + '\n')
        return output_path

    def _generate_metadata_file(self):
        """Generates the metadata JSONL file."""
        self.metadata = {
            "source_filename": os.path.basename(self.pdf_path),
            "total_pages": len(self.doc),
            "toc_entries_found": len(self.toc),
            "sections_parsed": len(self.sections)
        }
        metadata_path = os.path.join(
            "outputs", f"{self.base_filename}_metadata.jsonl"
        )
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.metadata, ensure_ascii=False) + '\n')
        return metadata_path

    def generate_outputs(self):
        """Generates all required JSONL output files."""
        if not self.toc or not self.sections:
            return None

        output_paths = {
            'toc': self._generate_jsonl_file(self.toc, 'toc'),
            'spec': self._generate_jsonl_file(self.sections, 'spec', True),
            'metadata': self._generate_metadata_file()
        }
        return output_paths

    def generate_validation_report(self):
        """Generates an Excel validation report."""
        report_path = os.path.join(
            "outputs", f"{self.base_filename}_validation_report.xlsx"
        )
        
        try:
            summary_df = pd.DataFrame({
                "Metric": ["Total Entries in ToC", "Total Sections Parsed"],
                "Count": [len(self.toc), len(self.sections)]
            })

            toc_map = {entry['section_id']: entry for entry in self.toc}
            sections_map = {sec['section_id']: sec for sec in self.sections}
            all_ids = sorted(list(set(toc_map.keys()) | set(sections_map.keys())))

            validation_records = []
            for section_id in all_ids:
                record = {"section_id": section_id}
                status = "OK"
                notes = ""
                
                if section_id in toc_map and section_id in sections_map:
                    notes = "Section found in ToC and parsed."
                elif section_id in toc_map:
                    status = "Mismatch / Not Parsed"
                    notes = "Section in ToC but not found in parsed output."
                else:  # in sections_map only
                    status = "Gap / Not in ToC"
                    notes = "Section parsed but does not exist in ToC."

                record.update({
                    "toc_title": toc_map.get(section_id, {}).get('title', 'N/A'),
                    "toc_page": toc_map.get(section_id, {}).get('page', 'N/A'),
                    "status": status,
                    "notes": notes
                })
                validation_records.append(record)
            
            detail_df = pd.DataFrame(validation_records)

            with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
                summary_df.to_excel(
                    writer, sheet_name='Validation', index=False, startrow=1
                )
                detail_df.to_excel(
                    writer,
                    sheet_name='Validation',
                    index=False,
                    startrow=len(summary_df) + 4
                )
            
            return report_path
        except Exception as e:
            flash(f"Could not generate validation report: {e}", "error")
            return None

    def parse(self):
        """Main method to run the full parsing process."""
        self.toc = self._parse_toc()
        if not self.toc:
            return None

        self.sections = self._parse_sections()
        if not self.sections:
            return None
        
        return True