from functools import lru_cache
from html import escape
from pathlib import Path
from string import Template

from .exceptions import EmailTemplateError


TEMPLATE_DIRECTORY = Path(__file__).parent / "templates"


@lru_cache(maxsize=32)
def load_template(template_name: str) -> Template:
    template_path = TEMPLATE_DIRECTORY / template_name
    try:
        return Template(template_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EmailTemplateError(
            f"Email template not found: {template_name}"
        ) from exc


def render_template(
    template_name: str,
    context: dict[str, object],
) -> str:
    escaped_context = {
        key: escape(str(value), quote=True)
        for key, value in context.items()
    }
    try:
        return load_template(template_name).substitute(escaped_context)
    except (KeyError, ValueError) as exc:
        raise EmailTemplateError(
            f"Email template could not be rendered: {template_name}"
        ) from exc
