"""
Extract keyword documentation from .fodt files and generate markdown.

This script extracts the text content from OPM Flow keyword documentation
files (.fodt) and converts them to clean markdown files for easy reading
and AI-assisted search.

Usage:
    fodt-extract-keywords --output build/keywords --verbose
"""
import io
import logging
import xml.sax
import xml.sax.handler
import xml.sax.xmlreader
import re
from pathlib import Path
from typing import Optional

import click

from fodt.constants import ClickOptions


class TextExtractHandler(xml.sax.handler.ContentHandler):
    """SAX handler that extracts text content from .fodt files."""
    
    def __init__(self) -> None:
        self.in_body = False
        self.in_section = False
        self.section_name: Optional[str] = None
        self.current_text = io.StringIO()
        self.content_parts: list[str] = []
        
        # Track element context for formatting
        self.element_stack: list[str] = []
        self.in_heading = False
        self.heading_level = 0
        self.in_list_item = False
        self.in_table = False
        self.in_table_cell = False
        self.table_row: list[str] = []
        self.table_rows: list[list[str]] = []
        self.cell_content = io.StringIO()
        
    def startElement(self, name: str, attrs: xml.sax.xmlreader.AttributesImpl) -> None:
        self.element_stack.append(name)
        
        if name == "office:body":
            self.in_body = True
            
        elif name == "text:section" and self.in_body:
            self.in_section = True
            if "text:name" in attrs.getNames():
                self.section_name = attrs.getValue("text:name")
                
        elif name == "text:h" and self.in_section:
            self.in_heading = True
            if "text:outline-level" in attrs.getNames():
                self.heading_level = int(attrs.getValue("text:outline-level"))
            else:
                self.heading_level = 1
            self._flush_text()
            
        elif name == "text:p" and self.in_section:
            self._flush_text()
            
        elif name == "text:list-item":
            self.in_list_item = True
            self._flush_text()
            
        elif name == "table:table":
            self.in_table = True
            self.table_rows = []
            self._flush_text()
            
        elif name == "table:table-row" and self.in_table:
            self.table_row = []
            
        elif name == "table:table-cell" and self.in_table:
            self.in_table_cell = True
            self.cell_content = io.StringIO()
            
        elif name == "text:s" and self.in_section:
            # Space element - check for count
            count = 1
            if "text:c" in attrs.getNames():
                count = int(attrs.getValue("text:c"))
            self.current_text.write(" " * count)
            
        elif name == "text:line-break" and self.in_section:
            self.current_text.write("\n")
            
        elif name == "text:tab" and self.in_section:
            self.current_text.write("\t")
            
    def endElement(self, name: str) -> None:
        if self.element_stack:
            self.element_stack.pop()
            
        if name == "office:body":
            self.in_body = False
            self._flush_text()
            
        elif name == "text:section":
            self.in_section = False
            self._flush_text()
            
        elif name == "text:h" and self.in_heading:
            text = self._get_and_clear_text().strip()
            if text:
                prefix = "#" * min(self.heading_level, 6)
                self.content_parts.append(f"\n{prefix} {text}\n")
            self.in_heading = False
            self.heading_level = 0
            
        elif name == "text:p":
            if self.in_table_cell:
                # Add to cell content, not main content
                text = self._get_and_clear_text().strip()
                if text:
                    self.cell_content.write(text + " ")
            elif self.in_list_item:
                text = self._get_and_clear_text().strip()
                if text:
                    self.content_parts.append(f"- {text}\n")
            else:
                text = self._get_and_clear_text().strip()
                if text:
                    self.content_parts.append(f"{text}\n\n")
                    
        elif name == "text:list-item":
            self.in_list_item = False
            
        elif name == "table:table-cell":
            self.in_table_cell = False
            cell_text = self.cell_content.getvalue().strip()
            self.table_row.append(cell_text)
            self.cell_content = io.StringIO()
            
        elif name == "table:table-row" and self.in_table:
            if self.table_row:
                self.table_rows.append(self.table_row)
            self.table_row = []
            
        elif name == "table:table":
            self.in_table = False
            self._format_table()
            
    def characters(self, content: str) -> None:
        if self.in_section:
            self.current_text.write(content)
            
    def _flush_text(self) -> None:
        text = self._get_and_clear_text().strip()
        if text:
            self.content_parts.append(text + "\n")
            
    def _get_and_clear_text(self) -> str:
        text = self.current_text.getvalue()
        self.current_text = io.StringIO()
        return text
        
    def _format_table(self) -> None:
        """Format collected table rows as markdown."""
        if not self.table_rows:
            return
            
        # Find max columns
        max_cols = max(len(row) for row in self.table_rows)
        if max_cols == 0:
            return
            
        # Normalize rows
        normalized = []
        for row in self.table_rows:
            while len(row) < max_cols:
                row.append("")
            normalized.append(row)
        
        # Skip empty tables (all cells empty)
        has_content = any(
            any(cell.strip() for cell in row)
            for row in normalized
        )
        if not has_content:
            self.table_rows = []
            return
            
        # Format as markdown table
        self.content_parts.append("\n")
        
        # Header row
        header = normalized[0] if normalized else [""] * max_cols
        self.content_parts.append("| " + " | ".join(header) + " |\n")
        self.content_parts.append("| " + " | ".join(["---"] * max_cols) + " |\n")
        
        # Data rows
        for row in normalized[1:]:
            self.content_parts.append("| " + " | ".join(row) + " |\n")
            
        self.content_parts.append("\n")
        self.table_rows = []
        
    def get_markdown(self) -> str:
        """Return the extracted content as markdown."""
        content = "".join(self.content_parts)
        # Clean up excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r'[ \t]+\n', '\n', content)
        return content.strip()
    
    def get_section_name(self) -> Optional[str]:
        """Return the section name (keyword name)."""
        return self.section_name


class KeywordExtractor:
    """Extract text from a single .fodt keyword file."""
    
    def __init__(self, fodt_path: Path) -> None:
        self.fodt_path = fodt_path
        
    def extract(self) -> tuple[str, Optional[str]]:
        """
        Extract markdown content from the .fodt file.
        
        Returns:
            Tuple of (markdown_content, keyword_name)
        """
        parser = xml.sax.make_parser()
        handler = TextExtractHandler()
        parser.setContentHandler(handler)
        
        with open(self.fodt_path, 'r', encoding='utf-8') as f:
            parser.parse(f)
            
        return handler.get_markdown(), handler.get_section_name()


class KeywordIndexGenerator:
    """Generate markdown files for all keywords in the repository."""
    
    def __init__(
        self,
        repo_root: Path,
        output_dir: Path,
        verbose: bool = False
    ) -> None:
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.verbose = verbose
        self.keywords_dir = repo_root / "parts" / "chapters" / "subsections"
        self.keywords: list[dict] = []
        
    def find_keyword_files(self) -> list[Path]:
        """Find all keyword .fodt files."""
        if not self.keywords_dir.exists():
            raise FileNotFoundError(f"Keywords directory not found: {self.keywords_dir}")
        return sorted(self.keywords_dir.rglob("*.fodt"))
        
    def generate(self) -> None:
        """Generate markdown files for all keywords."""
        fodt_files = self.find_keyword_files()
        total = len(fodt_files)
        
        logging.info(f"Found {total} keyword files to process")
        
        for i, fodt_path in enumerate(fodt_files, 1):
            if self.verbose:
                logging.info(f"[{i}/{total}] Processing {fodt_path.name}")
                
            try:
                self._process_file(fodt_path)
            except Exception as e:
                logging.warning(f"Failed to process {fodt_path}: {e}")
                
        # Generate index
        self._generate_index()
        
        logging.info(f"Generated {len(self.keywords)} keyword files")
        
    def _process_file(self, fodt_path: Path) -> None:
        """Process a single .fodt file and generate markdown."""
        extractor = KeywordExtractor(fodt_path)
        markdown, keyword_name = extractor.extract()
        
        if not markdown.strip():
            logging.warning(f"No content extracted from {fodt_path}")
            return
            
        # Determine output path (mirror source structure)
        relative = fodt_path.relative_to(self.keywords_dir)
        output_path = self.output_dir / relative.with_suffix('.md')
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add header with keyword name
        if keyword_name:
            header = f"# {keyword_name}\n\n"
            # Check if content already starts with same header
            if not markdown.startswith(f"# {keyword_name}"):
                markdown = header + markdown
                
        # Write markdown file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown + "\n")
            
        # Track for index
        self.keywords.append({
            'name': keyword_name or fodt_path.stem,
            'file': fodt_path.stem,
            'path': str(relative.with_suffix('.md')),
            'section': relative.parent.name
        })
        
    def _generate_index(self) -> None:
        """Generate INDEX.md with all keywords."""
        index_path = self.output_dir / "INDEX.md"
        
        # Sort keywords by name
        self.keywords.sort(key=lambda k: k['name'])
        
        # Group by section
        sections: dict[str, list[dict]] = {}
        for kw in self.keywords:
            section = kw['section']
            if section not in sections:
                sections[section] = []
            sections[section].append(kw)
            
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("# OPM Flow Keyword Index\n\n")
            f.write(f"Total keywords: {len(self.keywords)}\n\n")
            f.write("---\n\n")
            
            for section in sorted(sections.keys()):
                f.write(f"## Section {section}\n\n")
                for kw in sorted(sections[section], key=lambda k: k['name']):
                    f.write(f"- [{kw['name']}]({kw['path']})\n")
                f.write("\n")
                
        logging.info(f"Generated index at {index_path}")


@click.command()
@click.option(
    '--repo',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help='Path to opm-reference-manual repository root. Defaults to auto-detect.'
)
@click.option(
    '--output',
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help='Output directory for markdown files. Default: {repo}/build/keywords'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Show progress for each file'
)
def extract_keywords(repo: Optional[Path], output: Optional[Path], verbose: bool) -> None:
    """
    Extract keyword documentation from .fodt files to markdown.
    
    This generates clean, searchable markdown files from the OPM Flow
    Reference Manual keyword documentation.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Find repo root
    if repo is None:
        # Try to find it relative to script location
        script_dir = Path(__file__).parent
        # scripts/python/src/fodt/ -> repo root
        repo = script_dir.parent.parent.parent.parent
        if not (repo / "parts" / "chapters" / "subsections").exists():
            raise click.ClickException(
                "Could not auto-detect repository root. Please specify --repo"
            )
    
    # Set output directory
    if output is None:
        output = repo / "build" / "keywords"
        
    logging.info(f"Repository: {repo}")
    logging.info(f"Output: {output}")
    logging.info("")
    
    # Generate
    generator = KeywordIndexGenerator(repo, output, verbose)
    generator.generate()
    
    logging.info("")
    logging.info(f"Done! Markdown files written to: {output}")
    logging.info(f"Index available at: {output / 'INDEX.md'}")


if __name__ == '__main__':
    extract_keywords()
