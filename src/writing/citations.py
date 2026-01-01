from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import re
import os
import json
import logging

logger = logging.getLogger(__name__)

class CitationStyle(Enum):
    APA7 = "apa7"
    MLA9 = "mla9"
    HARVARD = "harvard"
    VANCOUVER = "vancouver"
    CHICAGO = "chicago"
    IEEE = "ieee"

@dataclass
class Reference:
    title: str
    authors: List[str]  # ["Smith, J.", "Doe, A."]
    year: str
    source: str  # Journal or Publisher
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    ref_type: Optional[str] = None  # article, book, thesis, etc.

class CitationManager:
    """
    Manages citation formatting for manuscripts.
    """

    @staticmethod
    def format_in_text(ref: Reference, style: CitationStyle = CitationStyle.APA7) -> str:
        authors = ref.authors
        year = ref.year or "n.d."
        
        if style == CitationStyle.APA7 or style == CitationStyle.HARVARD:
            if len(authors) == 1:
                return f"({authors[0].split(',')[0]}, {year})"
            elif len(authors) == 2:
                return f"({authors[0].split(',')[0]} & {authors[1].split(',')[0]}, {year})"
            else:
                return f"({authors[0].split(',')[0]} et al., {year})"
        
        elif style == CitationStyle.MLA9:
            return f"({authors[0].split(',')[0]})"
            
        elif style == CitationStyle.VANCOUVER:
            return "[1]" # Placeholder, requires a running counter in a real context
            
        return f"({authors[0]}, {year})"

    @staticmethod
    def format_entry(ref: Reference, style: CitationStyle = CitationStyle.APA7) -> str:
        """
        Format full bibliographic entry.
        """
        if style == CitationStyle.APA7:
            # Author, A. A., & Author, B. B. (Year). Title of article. Title of Periodical, xx(x), pp-pp.
            auth_str = "& ".join(ref.authors) if len(ref.authors) < 20 else f"{ref.authors[0]}... {ref.authors[-1]}"
            entry = f"{auth_str} ({ref.year}). {ref.title}. *{ref.source}*"
            if ref.volume:
                entry += f", *{ref.volume}*"
            if ref.issue:
                entry += f"({ref.issue})"
            if ref.pages:
                entry += f", {ref.pages}."
            if ref.doi:
                entry += f" https://doi.org/{ref.doi}"
            return entry
            
        elif style == CitationStyle.MLA9:
            # Author. "Title." Container, vol, issue, date, location.
            auth_str = ref.authors[0] if ref.authors else "Unknown"
            entry = f"{auth_str}. \"{ref.title}.\" *{ref.source}*"
            return entry
            
        # Fallback
        return f"{ref.authors}. {ref.title}. {ref.source}, {ref.year}."


class ReferenceParser:
    """
    Universal reference file parser supporting multiple formats.
    
    Supported formats:
    - RIS (.ris) - Research Information Systems
    - BibTeX (.bib, .bibtex) - LaTeX bibliography
    - EndNote XML (.xml) - EndNote export
    - PubMed XML (.xml) - PubMed/NCBI export
    - MEDLINE (.txt, .nbib) - PubMed MEDLINE format
    - CSV (.csv) - Comma-separated values
    - JSON (.json) - JSON format
    - RefWorks (.refworks, .txt) - RefWorks tagged format
    - MODS (.mods, .xml) - Metadata Object Description Schema
    - ISI/Web of Science (.isi, .ciw) - ISI tagged format
    - Zotero RDF (.rdf) - Zotero export
    - Plain text (.txt) - Simple text format
    """
    
    SUPPORTED_EXTENSIONS = [
        '.ris', '.bib', '.bibtex', '.xml', '.txt', '.nbib',
        '.csv', '.json', '.refworks', '.mods', '.isi', '.ciw',
        '.rdf', '.enw', '.end', '.refer', '.medline'
    ]
    
    @classmethod
    def get_supported_formats(cls) -> str:
        """Return formatted string of supported formats."""
        return ", ".join(cls.SUPPORTED_EXTENSIONS)
    
    @classmethod
    def parse_file(cls, file_path: str) -> Tuple[List[Reference], str]:
        """
        Parse a reference file and return list of Reference objects.
        
        Args:
            file_path: Path to the reference file
            
        Returns:
            Tuple of (list of References, status message)
        """
        if not os.path.exists(file_path):
            return [], f"File not found: {file_path}"
        
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return [], f"Error reading file: {str(e)}"
        
        # Detect format and parse
        if ext in ['.ris']:
            return cls._parse_ris(content)
        elif ext in ['.bib', '.bibtex']:
            return cls._parse_bibtex(content)
        elif ext in ['.xml']:
            return cls._parse_xml(content)
        elif ext in ['.nbib', '.medline']:
            return cls._parse_medline(content)
        elif ext in ['.csv']:
            return cls._parse_csv(content)
        elif ext in ['.json']:
            return cls._parse_json(content)
        elif ext in ['.isi', '.ciw']:
            return cls._parse_isi(content)
        elif ext in ['.enw', '.end']:
            return cls._parse_endnote(content)
        elif ext in ['.txt', '.refworks', '.refer']:
            # Try to auto-detect format from content
            return cls._parse_auto_detect(content)
        else:
            # Attempt auto-detection for unknown extensions
            return cls._parse_auto_detect(content)
    
    @classmethod
    def _parse_ris(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse RIS format."""
        refs = []
        entries = re.split(r'\nER\s*-', content)
        
        for entry in entries:
            if not entry.strip():
                continue
            
            ref_data = {
                'authors': [],
                'title': '',
                'year': '',
                'source': '',
                'volume': None,
                'issue': None,
                'pages': None,
                'doi': None
            }
            
            for line in entry.split('\n'):
                line = line.strip()
                if len(line) < 6:
                    continue
                    
                tag = line[:2]
                value = line[6:].strip() if len(line) > 6 else ''
                
                if tag == 'AU' or tag == 'A1':
                    ref_data['authors'].append(value)
                elif tag == 'TI' or tag == 'T1':
                    ref_data['title'] = value
                elif tag == 'PY' or tag == 'Y1':
                    ref_data['year'] = value[:4] if value else ''
                elif tag == 'JO' or tag == 'T2' or tag == 'JF':
                    ref_data['source'] = value
                elif tag == 'VL':
                    ref_data['volume'] = value
                elif tag == 'IS':
                    ref_data['issue'] = value
                elif tag == 'SP':
                    ref_data['pages'] = value
                elif tag == 'EP':
                    if ref_data['pages']:
                        ref_data['pages'] += f"-{value}"
                elif tag == 'DO':
                    ref_data['doi'] = value
            
            if ref_data['title'] or ref_data['authors']:
                refs.append(Reference(
                    title=ref_data['title'],
                    authors=ref_data['authors'] or ['Unknown'],
                    year=ref_data['year'] or 'n.d.',
                    source=ref_data['source'] or 'Unknown',
                    volume=ref_data['volume'],
                    issue=ref_data['issue'],
                    pages=ref_data['pages'],
                    doi=ref_data['doi']
                ))
        
        return refs, f"Parsed {len(refs)} references from RIS format"
    
    @classmethod
    def _parse_bibtex(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse BibTeX format."""
        refs = []
        
        # Find all entries
        entries = re.findall(r'@(\w+)\s*\{([^@]+)\}', content, re.DOTALL)
        
        for entry_type, entry_content in entries:
            ref_data = {
                'authors': [],
                'title': '',
                'year': '',
                'source': '',
                'volume': None,
                'issue': None,
                'pages': None,
                'doi': None,
                'ref_type': entry_type.lower()
            }
            
            # Parse fields
            fields = re.findall(r'(\w+)\s*=\s*[\{"]([^}"]+)[\}"]', entry_content)
            
            for field, value in fields:
                field = field.lower()
                value = value.strip()
                
                if field == 'author':
                    # Split on 'and' for multiple authors
                    authors = re.split(r'\s+and\s+', value)
                    ref_data['authors'] = [a.strip() for a in authors]
                elif field == 'title':
                    ref_data['title'] = re.sub(r'[{}]', '', value)
                elif field == 'year':
                    ref_data['year'] = value[:4]
                elif field in ['journal', 'booktitle', 'publisher']:
                    ref_data['source'] = value
                elif field == 'volume':
                    ref_data['volume'] = value
                elif field == 'number':
                    ref_data['issue'] = value
                elif field == 'pages':
                    ref_data['pages'] = value.replace('--', '-')
                elif field == 'doi':
                    ref_data['doi'] = value
            
            if ref_data['title'] or ref_data['authors']:
                refs.append(Reference(
                    title=ref_data['title'],
                    authors=ref_data['authors'] or ['Unknown'],
                    year=ref_data['year'] or 'n.d.',
                    source=ref_data['source'] or 'Unknown',
                    volume=ref_data['volume'],
                    issue=ref_data['issue'],
                    pages=ref_data['pages'],
                    doi=ref_data['doi'],
                    ref_type=ref_data['ref_type']
                ))
        
        return refs, f"Parsed {len(refs)} references from BibTeX format"
    
    @classmethod
    def _parse_xml(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse XML format (EndNote, PubMed, general)."""
        refs = []
        
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            
            # Try different XML structures
            # EndNote format
            for record in root.findall('.//record') or root.findall('.//Record'):
                ref_data = cls._extract_xml_record(record)
                if ref_data:
                    refs.append(ref_data)
            
            # PubMed format
            for article in root.findall('.//PubmedArticle') or root.findall('.//Article'):
                ref_data = cls._extract_pubmed_article(article)
                if ref_data:
                    refs.append(ref_data)
            
        except Exception as e:
            logger.warning(f"XML parsing error: {e}")
            # Try regex fallback
            return cls._parse_xml_fallback(content)
        
        return refs, f"Parsed {len(refs)} references from XML format"
    
    @classmethod
    def _extract_xml_record(cls, record) -> Optional[Reference]:
        """Extract reference from EndNote-style XML record."""
        try:
            title = record.findtext('.//title') or record.findtext('.//Title') or ''
            authors = [a.text for a in record.findall('.//author') or record.findall('.//Author') if a.text]
            year = record.findtext('.//year') or record.findtext('.//Year') or 'n.d.'
            source = record.findtext('.//secondary-title') or record.findtext('.//Journal') or ''
            
            if title or authors:
                return Reference(
                    title=title,
                    authors=authors or ['Unknown'],
                    year=year[:4] if year else 'n.d.',
                    source=source or 'Unknown'
                )
        except:
            pass
        return None
    
    @classmethod
    def _extract_pubmed_article(cls, article) -> Optional[Reference]:
        """Extract reference from PubMed XML article."""
        try:
            title = article.findtext('.//ArticleTitle') or ''
            authors = []
            for author in article.findall('.//Author'):
                lastname = author.findtext('LastName') or ''
                initials = author.findtext('Initials') or ''
                if lastname:
                    authors.append(f"{lastname}, {initials}")
            
            year = article.findtext('.//PubDate/Year') or 'n.d.'
            journal = article.findtext('.//Journal/Title') or article.findtext('.//Journal/ISOAbbreviation') or ''
            
            if title or authors:
                return Reference(
                    title=title,
                    authors=authors or ['Unknown'],
                    year=year[:4] if year else 'n.d.',
                    source=journal or 'Unknown'
                )
        except:
            pass
        return None
    
    @classmethod
    def _parse_xml_fallback(cls, content: str) -> Tuple[List[Reference], str]:
        """Fallback XML parsing using regex."""
        refs = []
        
        # Try to find common patterns
        titles = re.findall(r'<title>([^<]+)</title>', content, re.IGNORECASE)
        
        for title in titles[:50]:  # Limit to 50
            refs.append(Reference(
                title=title.strip(),
                authors=['Unknown'],
                year='n.d.',
                source='Unknown'
            ))
        
        return refs, f"Parsed {len(refs)} references from XML (fallback mode)"
    
    @classmethod
    def _parse_medline(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse MEDLINE/PubMed format."""
        refs = []
        entries = content.split('\n\n')
        
        for entry in entries:
            if not entry.strip():
                continue
            
            ref_data = {
                'authors': [],
                'title': '',
                'year': '',
                'source': ''
            }
            
            current_tag = ''
            current_value = ''
            
            for line in entry.split('\n'):
                if re.match(r'^[A-Z]{2,4}\s*-', line):
                    # New tag
                    if current_tag and current_value:
                        cls._process_medline_tag(current_tag, current_value.strip(), ref_data)
                    
                    parts = line.split('-', 1)
                    current_tag = parts[0].strip()
                    current_value = parts[1].strip() if len(parts) > 1 else ''
                else:
                    current_value += ' ' + line.strip()
            
            if current_tag and current_value:
                cls._process_medline_tag(current_tag, current_value.strip(), ref_data)
            
            if ref_data['title'] or ref_data['authors']:
                refs.append(Reference(
                    title=ref_data['title'],
                    authors=ref_data['authors'] or ['Unknown'],
                    year=ref_data['year'] or 'n.d.',
                    source=ref_data['source'] or 'Unknown'
                ))
        
        return refs, f"Parsed {len(refs)} references from MEDLINE format"
    
    @classmethod
    def _process_medline_tag(cls, tag: str, value: str, ref_data: dict):
        """Process a MEDLINE tag-value pair."""
        if tag in ['AU', 'FAU']:
            ref_data['authors'].append(value)
        elif tag == 'TI':
            ref_data['title'] = value
        elif tag == 'DP':
            ref_data['year'] = value[:4]
        elif tag in ['JT', 'TA']:
            ref_data['source'] = value
    
    @classmethod
    def _parse_csv(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse CSV format."""
        refs = []
        lines = content.split('\n')
        
        if len(lines) < 2:
            return refs, "CSV file appears empty"
        
        # Get headers
        import csv
        from io import StringIO
        
        reader = csv.DictReader(StringIO(content))
        
        for row in reader:
            # Try common column names
            title = row.get('title') or row.get('Title') or row.get('TITLE') or ''
            author = row.get('author') or row.get('Author') or row.get('authors') or row.get('Authors') or ''
            year = row.get('year') or row.get('Year') or row.get('date') or row.get('Date') or ''
            source = row.get('journal') or row.get('Journal') or row.get('source') or row.get('Source') or ''
            
            if title or author:
                authors = [a.strip() for a in author.split(';')] if ';' in author else [author] if author else ['Unknown']
                refs.append(Reference(
                    title=title,
                    authors=authors,
                    year=str(year)[:4] if year else 'n.d.',
                    source=source or 'Unknown'
                ))
        
        return refs, f"Parsed {len(refs)} references from CSV format"
    
    @classmethod
    def _parse_json(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse JSON format."""
        refs = []
        
        try:
            data = json.loads(content)
            
            # Handle list or dict
            items = data if isinstance(data, list) else data.get('references', data.get('items', [data]))
            
            for item in items:
                if isinstance(item, dict):
                    title = item.get('title', '')
                    authors = item.get('authors', item.get('author', []))
                    if isinstance(authors, str):
                        authors = [authors]
                    year = str(item.get('year', item.get('date', 'n.d.')))[:4]
                    source = item.get('journal', item.get('source', item.get('publisher', '')))
                    
                    if title or authors:
                        refs.append(Reference(
                            title=title,
                            authors=authors or ['Unknown'],
                            year=year or 'n.d.',
                            source=source or 'Unknown',
                            doi=item.get('doi'),
                            url=item.get('url')
                        ))
        except json.JSONDecodeError as e:
            return refs, f"JSON parse error: {str(e)}"
        
        return refs, f"Parsed {len(refs)} references from JSON format"
    
    @classmethod
    def _parse_isi(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse ISI/Web of Science format."""
        refs = []
        entries = re.split(r'\nER\s*\n', content)
        
        for entry in entries:
            if not entry.strip():
                continue
            
            ref_data = {'authors': [], 'title': '', 'year': '', 'source': ''}
            
            for line in entry.split('\n'):
                if len(line) < 3:
                    continue
                tag = line[:2].strip()
                value = line[3:].strip()
                
                if tag == 'AU':
                    ref_data['authors'].append(value)
                elif tag == 'TI':
                    ref_data['title'] += value + ' '
                elif tag == 'PY':
                    ref_data['year'] = value[:4]
                elif tag in ['SO', 'JI']:
                    ref_data['source'] = value
            
            if ref_data['title'] or ref_data['authors']:
                refs.append(Reference(
                    title=ref_data['title'].strip(),
                    authors=ref_data['authors'] or ['Unknown'],
                    year=ref_data['year'] or 'n.d.',
                    source=ref_data['source'] or 'Unknown'
                ))
        
        return refs, f"Parsed {len(refs)} references from ISI format"
    
    @classmethod
    def _parse_endnote(cls, content: str) -> Tuple[List[Reference], str]:
        """Parse EndNote tagged format (.enw)."""
        return cls._parse_ris(content)  # Similar format
    
    @classmethod
    def _parse_auto_detect(cls, content: str) -> Tuple[List[Reference], str]:
        """Auto-detect format and parse."""
        # Check for RIS markers
        if re.search(r'^TY\s*-', content, re.MULTILINE):
            return cls._parse_ris(content)
        
        # Check for BibTeX
        if re.search(r'@\w+\s*\{', content):
            return cls._parse_bibtex(content)
        
        # Check for XML
        if content.strip().startswith('<?xml') or content.strip().startswith('<'):
            return cls._parse_xml(content)
        
        # Check for MEDLINE
        if re.search(r'^PMID-', content, re.MULTILINE):
            return cls._parse_medline(content)
        
        # Check for ISI
        if re.search(r'^PT\s+', content, re.MULTILINE):
            return cls._parse_isi(content)
        
        # Check for JSON
        if content.strip().startswith('{') or content.strip().startswith('['):
            return cls._parse_json(content)
        
        # Fallback: try to extract any titles
        refs = []
        lines = [l.strip() for l in content.split('\n') if l.strip() and len(l.strip()) > 10]
        for line in lines[:20]:
            refs.append(Reference(
                title=line[:200],
                authors=['Unknown'],
                year='n.d.',
                source='Unknown'
            ))
        
        return refs, f"Auto-detected {len(refs)} potential references from plain text"
