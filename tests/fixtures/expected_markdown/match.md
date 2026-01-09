---
source: unit_test
id: 123
match_percentage: 100.0
missing_headings: []
matched_headings: [{'expected': 'INITIAL ALL CAPS HEADING', 'matched_text': 'INITIAL ALL CAPS HEADING', 'extraction_method': 'existing_heading', 'confidence': 100.0, 'line_number': 3, 'heading_signature': '#1-CAPS', 'was_extracted': False}, {'expected': 'Heading 2', 'matched_text': 'Heading 2', 'extraction_method': 'extracted_from_content', 'confidence': 100.0, 'line_number': 5, 'heading_signature': 'extracted-inline-#2', 'was_extracted': True}, {'expected': 'Heading 3', 'matched_text': 'heading 3', 'extraction_method': 'extracted_from_content', 'confidence': 100.0, 'line_number': 7, 'heading_signature': 'extracted-inline-*2', 'was_extracted': True}, {'expected': 'Inline Heading', 'matched_text': 'Inline Heading', 'extraction_method': 'extracted_from_content', 'confidence': 100.0, 'line_number': 9, 'heading_signature': 'extracted-inline-*2-inline', 'was_extracted': True}, {'expected': 'ANOTHER HEADING WITHOUT MARKESR', 'matched_text': 'ANOTHER ALL CAPS HEADING WITHOUT MARKERS', 'extraction_method': 'extracted_from_content', 'confidence': 83.64, 'line_number': 13, 'heading_signature': 'extracted-standalone-markerless-CAPS', 'was_extracted': True}]
---

This document contains headings that does not follow the expected markdown syntax.

# INITIAL ALL CAPS HEADING

For example this

## Heading 2

should be captured and the rest of this line should be its content.

This line should also continue to be content of Heading 2. Sometimes the headings are in bold like

### heading 3

and they should also be captured correctly.

Other times, new lines get deleted by mistake and headings appear inline like this

**Inline Heading:** with the rest of the line being its content.

But this line is just a normal sentence without any heading.

# ANOTHER ALL CAPS HEADING WITHOUT MARKERS

Second all caps heading should be the same level as the initial one and this line should be considered its content.
