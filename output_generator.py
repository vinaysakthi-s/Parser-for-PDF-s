# output_generator.py
import os
import re
import json

class OutputGenerator:
    """Handles the generation of JSONL output files."""

    def __init__(self, base_filename, doc_title, stop_words):
        self.base_filename = base_filename
        self.doc_title = doc_title
        self.stop_words = stop_words

    def _create_structured_entry(self, entry_data):
        """Helper function to create a detailed JSON object."""
        section_id = entry_data['section_id']
        title = entry_data.get('title', '')
        
        parent_id = '.'.join(section_id.split('.')[:-1]) if '.' in section_id else None
        
        words = re.findall(r'\b[a-z]+\b', title.lower())
        tags = sorted(list(set(word for word in words if word not in self.stop_words)))

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

    def generate_jsonl_file(self, data_list, file_suffix, add_content=False):
        """Generates a JSONL file from a list of data entries."""
        output_path = os.path.join("outputs", f"{self.base_filename}_{file_suffix}.jsonl")
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in data_list:
                structured_entry = self._create_structured_entry(entry)
                if add_content:
                    structured_entry['content'] = entry.get('content', '') 
                f.write(json.dumps(structured_entry, ensure_ascii=False) + '\n')
        return output_path

    def generate_metadata_file(self, metadata):
        """Generates the metadata JSONL file."""
        metadata_path = os.path.join("outputs", f"{self.base_filename}_metadata.jsonl")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
        return metadata_path