import re

from django.core import mail


def last_email_link(path_fragment: str) -> str:
    """Return the path of the first link in the latest email containing ``path_fragment``."""
    body = str(mail.outbox[-1].body)
    match = re.search(rf"https?://[^/\s]+(\S*{re.escape(path_fragment)}\S*)", body)
    assert match, f"No link with {path_fragment!r} in email:\n{body}"
    return match.group(1)


def last_email_key(path_fragment: str) -> str:
    """Return the last path segment of the link, i.e. the confirmation key."""
    return last_email_link(path_fragment).rstrip("/").rsplit("/", 1)[-1]
