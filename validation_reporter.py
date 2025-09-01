# validation_reporter.py
import os
import pandas as pd
from flask import flash

class ValidationReporter:
    """Handles the generation of the Excel validation report."""

    def __init__(self, base_filename, toc, sections):
        self.base_filename = base_filename
        self.toc = toc
        self.sections = sections

    def generate_report(self):
        """Generates an Excel validation report."""
        report_path = os.path.join("outputs", f"{self.base_filename}_validation_report.xlsx")
        
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
                summary_df.to_excel(writer, sheet_name='Validation', index=False, startrow=1)
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