import re

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

CSS_DIR = settings.BASE_DIR / "static" / "css"


def test_every_css_file_is_imported_once_by_main() -> None:
    imports = re.findall(r'@import url\("([^"]+)"\)', (CSS_DIR / "main.css").read_text())
    files = sorted(
        str(p.relative_to(CSS_DIR)) for p in CSS_DIR.rglob("*.css") if p.name != "main.css"
    )

    assert sorted(imports) == files


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["home", "account_login", "account_signup"])
def test_pages_use_design_system(client: Client, url_name: str) -> None:
    content = client.get(reverse(url_name)).content.decode()

    assert "css/main.css" in content
    assert 'class="header"' in content
    assert "OpenID" not in content
