"""Tests for safe, explicit webpage source retrieval."""

import unittest
from datetime import datetime

import httpx

from careerlens.source_retrieval import (
    EmptySourceContentError,
    InvalidSourceURLError,
    PDFSourceUnsupportedError,
    SourceConnectionError,
    SourceHTTPStatusError,
    SourceRedirectError,
    SourceResponseTooLargeError,
    SourceTimeoutError,
    UnsafeSourceURLError,
    UnsupportedSourceContentTypeError,
    extract_html_text,
    retrieve_webpage,
    validate_public_url,
)


PUBLIC_IPV4 = "93.184.216.34"


def public_resolver(hostname: str, port: int) -> list[str]:
    """Resolve every test hostname to a documentation-only public address."""
    return [PUBLIC_IPV4]


def html_response(
    request: httpx.Request,
    body: str = "<html><body><main><h1>企業情報</h1><p>公開ページの本文です。</p></main></body></html>",
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    response_headers = {"content-type": "text/html; charset=utf-8"}
    if headers:
        response_headers.update(headers)
    return httpx.Response(
        status_code,
        headers=response_headers,
        content=body.encode("utf-8"),
        request=request,
    )


class SourceRetrievalTests(unittest.TestCase):
    """Verify network limits, SSRF protection, extraction, and result metadata."""

    def retrieve(self, url: str, handler, **kwargs):
        return retrieve_webpage(
            url,
            resolver=kwargs.pop("resolver", public_resolver),
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    def test_valid_https_page_returns_structured_metadata(self) -> None:
        result = self.retrieve(
            "https://example.com/company",
            lambda request: html_response(
                request,
                """
                <html>
                    <head><title>企業サイト</title></head>
                    <body><main><h1>会社概要</h1><p>公開情報の本文です。</p></main></body>
                </html>
                """,
            ),
        )

        self.assertEqual(
            set(result),
            {
                "source_url",
                "final_url",
                "content_type",
                "retrieved_at",
                "title",
                "text",
                "character_count",
                "truncated",
            },
        )
        self.assertEqual(result["source_url"], "https://example.com/company")
        self.assertEqual(result["final_url"], "https://example.com/company")
        self.assertEqual(result["content_type"], "text/html")
        self.assertEqual(result["title"], "企業サイト")
        self.assertEqual(result["character_count"], len(result["text"]))
        self.assertFalse(result["truncated"])
        self.assertIsNotNone(datetime.fromisoformat(result["retrieved_at"]).tzinfo)

    def test_valid_http_page_is_supported(self) -> None:
        result = self.retrieve(
            "http://example.com/",
            lambda request: html_response(request),
        )

        self.assertEqual(result["source_url"], "http://example.com/")
        self.assertEqual(result["content_type"], "text/html")

    def test_html_extraction_removes_hidden_code_and_normalizes_whitespace(self) -> None:
        page_title, text = extract_html_text(
            """
            <html>
                <head>
                    <title>  Example   Company </title>
                    <style>.hidden { display: none; }</style>
                    <script>secretScript()</script>
                </head>
                <body>
                    <noscript>JavaScript fallback</noscript>
                    <main>
                        <h1>  Business   Overview </h1>
                        <p>First\n paragraph with   spacing.</p>
                        <ul><li>Item one</li><li>Item two</li></ul>
                        <table><tr><th>Region</th><td>Japan</td></tr></table>
                    </main>
                </body>
            </html>
            """
        )

        self.assertEqual(page_title, "Example Company")
        self.assertEqual(
            text,
            "Business Overview\n"
            "First paragraph with spacing.\n"
            "Item one\nItem two\nRegion\nJapan",
        )
        self.assertNotIn("secretScript", text)
        self.assertNotIn("display: none", text)
        self.assertNotIn("JavaScript fallback", text)

    def test_html_extraction_removes_exact_and_whitespace_equivalent_blocks(self) -> None:
        _, text = extract_html_text(
            """
            <main>
                <h2>BluStellar</h2>
                <p>AIを社会に実装し、 社会課題の解決へ導きます。</p>
                <h2>BluStellar</h2>
                <p>AIを社会に実装し、
                    社会課題の解決へ導きます。</p>
            </main>
            """
        )

        self.assertEqual(
            text,
            "BluStellar\nAIを社会に実装し、 社会課題の解決へ導きます。",
        )
        self.assertEqual(text.count("BluStellar"), 1)

    def test_html_deduplication_preserves_unique_blocks_and_original_order(self) -> None:
        _, text = extract_html_text(
            """
            <main>
                <h2>BluStellar</h2>
                <p>AIを社会に実装します。</p>
                <h2>安全保障</h2>
                <p>社会の安全を支えます。</p>
                <h2>BluStellar</h2>
                <p>AIを社会に実装します。</p>
                <h2>PICK UP</h2>
                <p>最新のお知らせです。</p>
            </main>
            """
        )

        self.assertEqual(
            text.splitlines(),
            [
                "BluStellar",
                "AIを社会に実装します。",
                "安全保障",
                "社会の安全を支えます。",
                "PICK UP",
                "最新のお知らせです。",
            ],
        )

    def test_html_deduplication_keeps_similar_but_non_identical_blocks(self) -> None:
        _, text = extract_html_text(
            """
            <main>
                <p>AIを社会に実装します。</p>
                <p>AIを安全に社会へ実装します。</p>
                <p>AIを社会に実装しています。</p>
            </main>
            """
        )

        self.assertEqual(
            text.splitlines(),
            [
                "AIを社会に実装します。",
                "AIを安全に社会へ実装します。",
                "AIを社会に実装しています。",
            ],
        )

    def test_plain_text_content_is_supported(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8"},
                content="Company   overview\n\nPublic source text".encode(),
                request=request,
            )

        result = self.retrieve("https://example.com/company.txt", handler)

        self.assertEqual(result["content_type"], "text/plain")
        self.assertEqual(result["text"], "Company overview\nPublic source text")

    def test_safe_redirect_is_validated_and_followed_once(self) -> None:
        requested_urls = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested_urls.append(str(request.url))
            if request.url.host == "example.com":
                return httpx.Response(
                    302,
                    headers={"location": "https://www.example.org/final"},
                    request=request,
                )
            return html_response(request)

        result = self.retrieve("https://example.com/start", handler)

        self.assertEqual(
            requested_urls,
            ["https://example.com/start", "https://www.example.org/final"],
        )
        self.assertEqual(result["final_url"], "https://www.example.org/final")

    def test_redirect_to_private_address_is_blocked_before_second_request(self) -> None:
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(
                302,
                headers={"location": "http://127.0.0.1/internal"},
                request=request,
            )

        with self.assertRaises(UnsafeSourceURLError):
            self.retrieve("https://example.com/start", handler)

        self.assertEqual(request_count, 1)

    def test_redirect_limit_is_enforced(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            next_step = int(request.url.params.get("step", "0")) + 1
            return httpx.Response(
                302,
                headers={"location": f"https://example.com/?step={next_step}"},
                request=request,
            )

        with self.assertRaises(SourceRedirectError):
            self.retrieve("https://example.com/?step=0", handler)

    def test_localhost_private_and_loopback_addresses_are_rejected(self) -> None:
        blocked_urls = (
            "http://localhost/",
            "http://127.0.0.1/",
            "http://127.20.30.40/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://[::1]/",
            "http://169.254.1.1/",
        )

        for blocked_url in blocked_urls:
            with self.subTest(url=blocked_url):
                with self.assertRaises(UnsafeSourceURLError):
                    validate_public_url(blocked_url, public_resolver)

    def test_hostname_resolving_to_private_address_is_rejected(self) -> None:
        with self.assertRaises(UnsafeSourceURLError):
            validate_public_url(
                "https://internal.example/",
                lambda hostname, port: ["10.0.0.10"],
            )

    def test_unsupported_schemes_and_embedded_credentials_are_rejected(self) -> None:
        invalid_urls = (
            "file:///etc/passwd",
            "ftp://example.com/file",
            "data:text/plain,hello",
            "https://user:password@example.com/",
            "not-a-url",
        )

        for invalid_url in invalid_urls:
            with self.subTest(url=invalid_url):
                with self.assertRaises(InvalidSourceURLError):
                    validate_public_url(invalid_url, public_resolver)

    def test_timeout_is_mapped_without_retry(self) -> None:
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            raise httpx.ReadTimeout("too slow", request=request)

        with self.assertRaises(SourceTimeoutError):
            self.retrieve("https://example.com/slow", handler)

        self.assertEqual(request_count, 1)

    def test_connection_failure_is_mapped(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        with self.assertRaises(SourceConnectionError):
            self.retrieve("https://example.com/unavailable", handler)

    def test_http_404_and_500_are_reported(self) -> None:
        for status_code in (404, 500):
            with self.subTest(status=status_code):
                with self.assertRaises(SourceHTTPStatusError) as raised:
                    self.retrieve(
                        "https://example.com/error",
                        lambda request, code=status_code: html_response(
                            request,
                            status_code=code,
                        ),
                    )
                self.assertEqual(raised.exception.status_code, status_code)

    def test_oversized_response_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return html_response(
                request,
                body="<p>本文が上限を超えています。</p>",
                headers={"content-length": "101"},
            )

        with self.assertRaises(SourceResponseTooLargeError):
            self.retrieve(
                "https://example.com/large",
                handler,
                max_response_bytes=100,
            )

    def test_streamed_body_over_limit_is_rejected_without_content_length(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<p>" + (b"a" * 200) + b"</p>",
                request=request,
            )

        with self.assertRaises(SourceResponseTooLargeError):
            self.retrieve(
                "https://example.com/large",
                handler,
                max_response_bytes=100,
            )

    def test_unsupported_binary_content_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "image/png"},
                content=b"binary image",
                request=request,
            )

        with self.assertRaises(UnsupportedSourceContentTypeError):
            self.retrieve("https://example.com/image", handler)

    def test_pdf_content_type_has_specific_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF-1.7",
                request=request,
            )

        with self.assertRaises(PDFSourceUnsupportedError):
            self.retrieve("https://example.com/report.pdf", handler)

    def test_empty_or_script_only_html_is_rejected(self) -> None:
        with self.assertRaises(EmptySourceContentError):
            self.retrieve(
                "https://example.com/app",
                lambda request: html_response(
                    request,
                    "<html><body><script>renderApplication()</script></body></html>",
                ),
            )

    def test_request_uses_descriptive_agent_without_credentials_or_cookies(self) -> None:
        observed_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed_headers.update(request.headers)
            return html_response(request)

        self.retrieve("https://example.com/", handler)

        self.assertEqual(
            observed_headers["user-agent"],
            "CareerLens/0.1 source-retrieval",
        )
        self.assertNotIn("authorization", observed_headers)
        self.assertNotIn("cookie", observed_headers)


if __name__ == "__main__":
    unittest.main()
