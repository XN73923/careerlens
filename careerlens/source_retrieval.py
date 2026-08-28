"""Safe, explicit retrieval of one public webpage for source preview."""

import ipaddress
import re
import socket
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup


USER_AGENT = "CareerLens/0.1 source-retrieval"
TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
MIN_EXTRACTED_CHARACTERS = 1

SUPPORTED_CONTENT_TYPES = {"text/html", "text/plain"}
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")
READABLE_HTML_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "blockquote",
    "dt",
    "dd",
    "th",
    "td",
}

Resolver = Callable[[str, int], list[str]]


class SourceRetrievalError(Exception):
    """Base error for safe webpage retrieval failures."""


class InvalidSourceURLError(SourceRetrievalError):
    """Raised when a source URL is malformed or uses a forbidden scheme."""


class UnsafeSourceURLError(SourceRetrievalError):
    """Raised when a URL resolves to a local, private, or reserved address."""


class SourceDNSResolutionError(SourceRetrievalError):
    """Raised when the public host cannot be resolved."""


class SourceTimeoutError(SourceRetrievalError):
    """Raised when connection or reading exceeds the configured timeout."""


class SourceConnectionError(SourceRetrievalError):
    """Raised when the remote host cannot be reached."""


class SourceHTTPStatusError(SourceRetrievalError):
    """Raised for an unsuccessful HTTP status response."""

    def __init__(self, status_code: int):
        super().__init__(f"The webpage returned HTTP {status_code}.")
        self.status_code = status_code


class SourceRedirectError(SourceRetrievalError):
    """Raised when a redirect is malformed or exceeds the redirect limit."""


class SourceResponseTooLargeError(SourceRetrievalError):
    """Raised when a response body exceeds the configured safety limit."""


class UnsupportedSourceContentTypeError(SourceRetrievalError):
    """Raised for non-webpage response content."""

    def __init__(self, content_type: str):
        super().__init__(f"Unsupported content type: {content_type or 'unknown'}")
        self.content_type = content_type


class PDFSourceUnsupportedError(SourceRetrievalError):
    """Raised when a source response is a PDF."""


class EmptySourceContentError(SourceRetrievalError):
    """Raised when no meaningful visible text can be extracted."""


def resolve_host_addresses(hostname: str, port: int) -> list[str]:
    """Resolve all stream addresses for one hostname."""
    try:
        address_info = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise SourceDNSResolutionError(
            "The source hostname could not be resolved."
        ) from error

    return sorted({item[4][0].split("%", 1)[0] for item in address_info})


def _is_public_ip(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def validate_public_url(
    url: str,
    resolver: Resolver = resolve_host_addresses,
) -> str:
    """Validate one HTTP(S) URL and every IP currently resolved for its host."""
    normalized_url = url.strip()
    try:
        parsed_url = urlsplit(normalized_url)
        port = parsed_url.port
    except ValueError as error:
        raise InvalidSourceURLError("The source URL is invalid.") from error

    if parsed_url.scheme.lower() not in {"http", "https"}:
        raise InvalidSourceURLError("Only HTTP and HTTPS source URLs are supported.")
    if not parsed_url.hostname:
        raise InvalidSourceURLError("The source URL must include a hostname.")
    if parsed_url.username is not None or parsed_url.password is not None:
        raise InvalidSourceURLError("Credentials are not allowed in source URLs.")

    hostname = parsed_url.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(BLOCKED_HOST_SUFFIXES):
        raise UnsafeSourceURLError("Local and internal hostnames are blocked.")

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        effective_port = port or (443 if parsed_url.scheme.lower() == "https" else 80)
        try:
            resolved_addresses = resolver(hostname, effective_port)
        except SourceRetrievalError:
            raise
        except (OSError, socket.gaierror) as error:
            raise SourceDNSResolutionError(
                "The source hostname could not be resolved."
            ) from error
        if not resolved_addresses:
            raise SourceDNSResolutionError("The source hostname returned no addresses.")
        if not all(_is_public_ip(address) for address in resolved_addresses):
            raise UnsafeSourceURLError(
                "The source hostname resolves to a non-public address."
            )
    else:
        if not literal_ip.is_global:
            raise UnsafeSourceURLError("The source address is not public.")

    return urlunsplit(
        (
            parsed_url.scheme.lower(),
            parsed_url.netloc,
            parsed_url.path or "/",
            parsed_url.query,
            "",
        )
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _deduplicate_text_blocks(text_blocks: list[str]) -> list[str]:
    """Remove only normalization-equivalent blocks, keeping the first in order."""
    unique_blocks = []
    seen_blocks = set()
    for text_block in text_blocks:
        comparison_text = _normalize_text(text_block)
        if not comparison_text or comparison_text in seen_blocks:
            continue
        seen_blocks.add(comparison_text)
        unique_blocks.append(text_block)
    return unique_blocks


def extract_html_text(html_text: str) -> tuple[str, str]:
    """Extract a document title and normalized human-readable HTML text."""
    soup = BeautifulSoup(html_text, "html.parser")
    page_title = (
        _normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    )

    for hidden_element in soup.find_all(
        ["script", "style", "noscript", "template", "svg"]
    ):
        hidden_element.decompose()

    content_root = soup.find("main") or soup.find("article") or soup.body or soup
    text_blocks = []
    for element in content_root.find_all(READABLE_HTML_TAGS):
        if any(parent.name in READABLE_HTML_TAGS for parent in element.parents):
            continue
        block_text = _normalize_text(element.get_text(" ", strip=True))
        if block_text:
            text_blocks.append(block_text)

    if not text_blocks:
        fallback_text = content_root.get_text("\n", strip=True)
        text_blocks = [
            normalized_line
            for line in fallback_text.splitlines()
            if (normalized_line := _normalize_text(line))
        ]

    return page_title, "\n".join(_deduplicate_text_blocks(text_blocks))


def _extract_plain_text(body_text: str) -> str:
    return "\n".join(
        normalized_line
        for line in body_text.splitlines()
        if (normalized_line := _normalize_text(line))
    )


def _decode_response_body(response: httpx.Response, body: bytes) -> str:
    encoding = response.encoding or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def retrieve_webpage(
    source_url: str,
    *,
    resolver: Resolver = resolve_host_addresses,
    transport: httpx.BaseTransport | None = None,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> dict[str, object]:
    """Retrieve and extract one public webpage without following linked pages."""
    current_url = validate_public_url(source_url, resolver)
    redirect_count = 0
    timeout = httpx.Timeout(TIMEOUT_SECONDS)

    with httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
        trust_env=False,
        transport=transport,
    ) as client:
        while True:
            try:
                with client.stream(
                    "GET",
                    current_url,
                    headers={"Accept": "text/html,text/plain;q=0.9"},
                ) as response:
                    if response.status_code in REDIRECT_STATUS_CODES:
                        location = response.headers.get("location")
                        if not location:
                            raise SourceRedirectError(
                                "The webpage redirect did not include a destination."
                            )
                        if redirect_count >= MAX_REDIRECTS:
                            raise SourceRedirectError(
                                "The webpage exceeded the redirect limit."
                            )
                        next_url = urljoin(current_url, location)
                        current_url = validate_public_url(next_url, resolver)
                        redirect_count += 1
                        client.cookies.clear()
                        continue

                    if 300 <= response.status_code < 400:
                        raise SourceRedirectError(
                            "The webpage returned an unsupported redirect response."
                        )
                    if response.status_code >= 400:
                        raise SourceHTTPStatusError(response.status_code)

                    content_type = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if content_type == "application/pdf":
                        raise PDFSourceUnsupportedError(
                            "PDF source retrieval is not supported yet."
                        )
                    if content_type not in SUPPORTED_CONTENT_TYPES:
                        raise UnsupportedSourceContentTypeError(content_type)

                    content_length = response.headers.get("content-length")
                    if content_length:
                        try:
                            if int(content_length) > max_response_bytes:
                                raise SourceResponseTooLargeError(
                                    "The webpage response is too large."
                                )
                        except ValueError:
                            pass

                    body_parts = []
                    body_length = 0
                    for chunk in response.iter_bytes():
                        body_length += len(chunk)
                        if body_length > max_response_bytes:
                            raise SourceResponseTooLargeError(
                                "The webpage response is too large."
                            )
                        body_parts.append(chunk)

                    body_text = _decode_response_body(
                        response,
                        b"".join(body_parts),
                    )
                    if content_type == "text/html":
                        page_title, extracted_text = extract_html_text(body_text)
                    else:
                        page_title = ""
                        extracted_text = _extract_plain_text(body_text)

                    if len(extracted_text) < MIN_EXTRACTED_CHARACTERS:
                        raise EmptySourceContentError(
                            "No meaningful visible webpage text was extracted."
                        )

                    return {
                        "source_url": source_url.strip(),
                        "final_url": str(response.url),
                        "content_type": content_type,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "title": page_title,
                        "text": extracted_text,
                        "character_count": len(extracted_text),
                        "truncated": False,
                    }
            except httpx.TimeoutException as error:
                raise SourceTimeoutError(
                    "The webpage request exceeded the timeout."
                ) from error
            except httpx.RequestError as error:
                raise SourceConnectionError(
                    "The webpage could not be reached."
                ) from error
