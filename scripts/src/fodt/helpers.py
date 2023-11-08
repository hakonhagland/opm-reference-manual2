import importlib.resources  # access non-code resources
import shutil
import xml.sax.saxutils

from pathlib import Path
from fodt.constants import Directories, FileNames
from fodt.exceptions import InputException

class Helpers:

    @staticmethod
    def create_backup_document(filename) -> None:
        outputdir = filename.parent
        backupdir = outputdir / Directories.backup
        backupdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(filename, backupdir)
        backup_file = backupdir / filename.name
        return backup_file

    @staticmethod
    def keyword_file(outputdir: Path, chapter: int, section: int) -> Path:
        directory = f"{chapter}.{section}"
        filename = FileNames.keywords
        dir_ = outputdir / Directories.info / Directories.keywords / directory
        file = dir_ / filename
        return file

    @staticmethod
    def keywords_inverse_map(keyw_list: list[str]) -> dict[str, int]:
        return {keyw_list[i]: i + 1 for i in range(len(keyw_list))}

    @staticmethod
    def read_keyword_order(outputdir: Path, chapter: int, section: int) -> list[str]:
        file = Helpers.keyword_file(outputdir, chapter, section)
        if not file.exists():
            raise InputException(f"Could not find file {file}.")
        with open(file, "r", encoding='utf8') as f:
            keywords = [line.strip() for line in f.readlines()]
        return keywords

    @staticmethod
    def read_keyword_template() -> str:
        # NOTE: This template was created from the COLUMNS keyword in section 4.3
        path = importlib.resources.files("fodt.data").joinpath("keyword_template.xml")
        with open(path, "r", encoding='utf8') as f:
            template = f.read()
        return template

    @staticmethod
    def replace_section_callback(part: str, keyword: str) -> str:
        section = ".".join(part.split(".")[:2])
        href = f"{Directories.subsections}/{section}/{keyword}.fodt"
        href = xml.sax.saxutils.escape(href)
        return (f"""<text:section text:style-name="Sect1" text:name="Section{section}:{keyword}" """
                   f"""text:protected="true">\n"""
                f"""     <text:section-source xlink:href="{href}" """
                   f"""text:filter-name="OpenDocument Text Flat XML" """
                   f"""text:section-name="{keyword}"/>\n"""
                f"""    </text:section>\n""")

    @staticmethod
    def write_keyword_order(outputdir: Path, chapter: int, section: int,
                            keywords: list[str]
    ) -> None:
        file = Helpers.keyword_file(outputdir, chapter, section)
        with open(file, "w", encoding='utf8') as f:
            for keyword in keywords:
                f.write(f"{keyword}\n")
        return
