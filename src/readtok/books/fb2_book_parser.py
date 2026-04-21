import logging
import re

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)


@dataclass
class NoteData:
    id: int
    title: str
    text: str


@dataclass
class SectionData:
    path: list[str]
    paragraphs: list[str]


@dataclass
class BookData:
    author: str | None
    title: str | None
    sections: list[SectionData]
    notes: list[NoteData]


class Fb2BookParser:
    def __init__(self):
        self.ns = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}

    def _extract_full_author(self, root: etree.Element) -> None | str:
        author = root.find(
            ".//fb:description/fb:title-info/fb:author",
            namespaces=self.ns,
        )
        if author is None:
            return None

        first = author.findtext(
            "fb:first-name",
            default="",
            namespaces=self.ns,
        )
        middle = author.findtext(
            "fb:middle-name",
            default="",
            namespaces=self.ns,
        )
        last = author.findtext("fb:last-name", default="", namespaces=self.ns)
        full_name = " ".join(
            part.strip() for part in (first, middle, last) if part.strip()
        )
        return full_name

    def _extract_book_title(self, root: etree.Element) -> str | None:
        title = root.findtext(
            ".//fb:description/fb:title-info/fb:book-title",
            namespaces=self.ns,
        )
        return title.strip() if title else None

    def has_paragraphs(self, section: etree.Element):
        return bool(section.xpath("fb:p", namespaces=self.ns))

    def has_subtitles(self, section: etree.Element) -> bool:
        return bool(section.xpath("fb:subtitle", namespaces=self.ns))

    def get_paragraphs(self, section: etree.Element) -> list[etree.Element]:
        return section.xpath("fb:p", namespaces=self.ns)

    def get_title(self, section: etree.Element) -> None | str:
        title_el = section.find("fb:title", namespaces=self.ns)
        if title_el is None:
            return None
        return self.get_element_clened_text(title_el)

    def get_element_clened_text(self, paragraph: etree.Element) -> str:
        text = " ".join(paragraph.itertext())
        text = re.sub(r"\s+", " ", text)
        text = text.strip()
        return text

    def get_paragraphs_as_text(
        self,
        section: etree.Element,
        with_tags: bool = False,
    ):
        paragraphs = self.get_paragraphs(section)
        result = []
        for p in paragraphs:
            text = self.get_element_clened_text(p)
            if with_tags:
                result.append(f"<p>{text}</p>")
            else:
                result.append(text)
        return result

    def get_poem_as_text(self, section: etree.Element) -> list[str]:
        """Извлекает строки из <poem><stanza><v>...</v></stanza></poem>."""
        result = []
        poems = section.xpath("fb:poem", namespaces=self.ns)
        for poem in poems:
            verses = poem.xpath(".//fb:v", namespaces=self.ns)
            lines = [
                self.get_element_clened_text(v)
                for v in verses
                if v.text or len(v)
            ]
            if lines:
                # Оборачиваем строфу в тег, чтобы сохранить структуру
                stanza_text = "\n".join(lines)
                result.append(stanza_text)
        return result

    def get_split_sections_by_subtitle(
        self,
        section: etree.Element,
        base_path: list[str],
    ) -> list[SectionData]:
        # Разбиваем секции по подзаголовкам, которые могут быть внутри секции
        result = []
        current_subtitle = None
        current_paragraphs = []
        for elem in section.iterchildren():
            tag = etree.QName(elem).localname
            if tag == "subtitle":
                subtitle = "".join(elem.itertext())
                if current_paragraphs:
                    path = base_path + (
                        [current_subtitle] if current_subtitle else []
                    )
                    result.append(
                        self.build_section_data(path, current_paragraphs),
                    )
                current_subtitle = subtitle
                current_paragraphs = []
            elif tag == "p":
                text = self.get_element_clened_text(elem)
                text_with_tag = f"<p>{text}</p>"
                current_paragraphs.append(text_with_tag)

        if current_paragraphs:
            path = base_path + ([current_subtitle] if current_subtitle else [])
            result.append(self.build_section_data(path, current_paragraphs))
        return result

    def get_main_sections(
        self,
        root: etree.Element,
    ) -> list[etree.Element] | None:
        bodies = root.xpath("(//fb:body[not(@name)])[1]", namespaces=self.ns)
        if bodies:
            body = bodies[0]
            main_sections = body.xpath(
                "fb:section[not(@name)]",
                namespaces=self.ns,
            )
            return main_sections
        return None

    def get_note_sections(
        self,
        root: etree.Element,
    ) -> etree.Element | None:
        note_sections = root.xpath(
            "(//fb:body[@name='notes'])[1]//fb:section[@id]",
            namespaces=self.ns,
        )
        if note_sections:
            return note_sections
        return None

    def extract_note_id(self, note_section: etree.Element) -> int | None:
        note_id = None
        raw_id = note_section.attrib.get("id")
        if not raw_id:
            return None

        if "n" not in raw_id:
            return None

        res = re.search(r"\d+", raw_id)
        if res:
            note_id = int(res.group())
        return note_id

    def get_note_text(self, note_section: etree.Element) -> list[str]:
        """Собирает текст примечания из <p> и <poem>."""
        text = self.get_paragraphs_as_text(note_section)  # из <p>
        if not text:
            text = self.get_poem_as_text(note_section)    # из <poem>
        return text

    def get_notes(self, note_sections: etree.Element) -> list[NoteData]:
        notes = []
        for n_s in note_sections:
            note_id = self.extract_note_id(n_s)
            title = self.get_title(n_s)
            if note_id is None or title is None:
                continue
            text = self.get_note_text(n_s)
            note = NoteData(note_id, title, "\n".join(text))
            notes.append(note)
        return notes

    def build_section_data(self, path: list[str], paragraphs: list[str]):
        return SectionData(path, paragraphs)

    def collect_subsections(
        self,
        section: etree.Element,
        path: list | None = None,
    ) -> list[SectionData]:
        result = []
        if path is None:
            path = []

        section_title = self.get_title(section)
        current_path = path + ([section_title] if section_title else [])
        subsections = section.xpath("fb:section", namespaces=self.ns)

        if not subsections:
            if self.has_subtitles(section):
                result += self.get_split_sections_by_subtitle(
                    section,
                    current_path,
                )
            else:
                paragraphs = self.get_paragraphs_as_text(
                    section,
                    with_tags=True,
                )
                if paragraphs:
                    result.append(
                        self.build_section_data(current_path, paragraphs),
                    )
            return result

        for subsection in subsections:
            result += self.collect_subsections(
                subsection,
                path=current_path,
            )
        return result

    def parse(self, book_path: Path) -> BookData:
        sections = []
        notes = []
        tree = etree.parse(book_path)
        root = tree.getroot()

        main_sections = self.get_main_sections(root)
        if main_sections:
            for section in main_sections:
                sections += self.collect_subsections(section)

        notes_section = self.get_note_sections(root)
        if notes_section:
            notes += self.get_notes(notes_section)

        return BookData(
            author=self._extract_full_author(root),
            title=self._extract_book_title(root),
            sections=sections,
            notes=notes,
        )
