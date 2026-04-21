import logging

from pathlib import Path

from pick import pick

from readtok.books.services import BookImportService
from readtok.infra.bootstrap.seeder import DatabaseSeeder

logger = logging.getLogger(__name__)


async def initdb(seeder: DatabaseSeeder):
    await seeder.seed()


async def import_book(
    file_path: Path,
    output_dir: Path,
    service: BookImportService,
):
    logger.info("Starting book import")

    # select book category
    categories = await service.book_service.get_category_titles()
    logger.info(f"Categories: {categories}")
    selected = pick(
        categories,
        title=("Select category (SPACE to select multiple, ENTER to confirm)"),
    )
    selected_category = selected[0]
    logger.info(f"Selected category: {selected_category}")

    # select book sections
    section_groups = service.get_section_groups(file_path)
    logger.info(f"Section groups: {section_groups}")

    options = [" > ".join(group) for group in section_groups]
    selected = pick(
        options,
        title=(
            "Select chapters to import "
            "(SPACE to select multiple, ENTER to confirm)"
        ),
        multiselect=True,
        min_selection_count=1,
    )

    selected_groups = [section_groups[index] for _, index in selected]
    logger.info(f"Selected groups: {selected_groups}")
    selected_sections = []
    for group in selected_groups:
        selected_sections.extend(
            service.get_sections_by_group(file_path, group),
        )

    logger.info(f"Selected sections: {selected_sections}")
    await service.import_book(
        file_path,
        selected_category,
        selected_sections,
        output_dir,
    )
    logger.info("Book import completed")
