# output_generator.py
import os
import re
import json

class OutputGenerator:
    """Handles the generation of JSON/JSONL output files."""

    def __init__(self, doc_title, stop_words):
        self.doc_title = doc_title
        self.stop_words = stop_words
        self.output_dir = "outputs"
        os.makedirs(self.output_dir, exist_ok=True)

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

    def generate_toc_file(self, toc_data):
        """Generates the ToC JSON file."""
        output_path = os.path.join(self.output_dir, "usb_pd_toc.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([self._create_structured_entry(entry) for entry in toc_data], f, ensure_ascii=False, indent=2)
        return output_path

    def generate_spec_file(self, spec_data, add_content=False):
        """Generates the spec JSONL file (all other contents)."""
        output_path = os.path.join(self.output_dir, "usb_pd_spec.jsonl")
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in spec_data:
                structured_entry = self._create_structured_entry(entry)
                if add_content:
                    structured_entry['content'] = entry.get('content', '')
                f.write(json.dumps(structured_entry, ensure_ascii=False) + '\n')
        return output_path

    def generate_metadata_file(self, metadata):
        """Generates the metadata JSONL file."""
        output_path = os.path.join(self.output_dir, "usb_pd_metadata.jsonl")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
        return output_path
