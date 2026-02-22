"""XSS Detection Plugin - Reflected Cross-Site Scripting scanner."""

import re
from typing import Any

__vuln_info__ = {
    "name": "Reflected XSS",
    "vuln_id": "CVE-2024-DEMO-XSS",
    "severity": "medium",
    "category": "xss",
    "description": "Detects reflected cross-site scripting vulnerabilities",
    "author": "VulnScan Team",
    "version": "1.0.0",
    "references": [
        "https://owasp.org/www-community/attacks/xss/"
    ],
    "tags": ["xss", "injection", "client-side"],
    "fingerprints": {
        "technologies": ["php", "asp", "jsp"],
        "paths": ["/search", "/result", "/query", "/error"],
    },
}


class XssReflected:
    """Reflected XSS vulnerability checker."""

    def __init__(self) -> None:
        self._payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "'\"><script>alert('XSS')</script>",
            "<body onload=alert('XSS')>",
        ]
        self._detection_pattern = re.compile(
            r"<script.*?>.*?alert.*?</script>",
            re.IGNORECASE | re.DOTALL,
        )

    async def verify(
        self, target: str, http_client: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Verify if target is vulnerable to reflected XSS.

        Args:
            target: Target URL to test
            http_client: HTTP client instance
            **kwargs: Additional parameters

        Returns:
            Vulnerability result with status and details
        """
        result = {
            "vulnerable": False,
            "vulnerability": "Reflected XSS",
            "severity": "medium",
            "details": [],
            "evidence": None,
        }

        try:
            for payload in self._payloads:
                # Test GET parameter
                test_url = f"{target}?q={payload}"

                try:
                    response = await http_client.get(test_url)
                    response_text = response.text

                    # Check if payload is reflected in response
                    if payload in response_text:
                        result["vulnerable"] = True
                        result["details"].append(
                            {
                                "payload": payload,
                                "location": "GET parameter",
                                "status_code": response.status_code,
                            }
                        )
                        result["evidence"] = f"Payload reflected: {payload[:50]}..."

                    # Check for script injection pattern
                    elif self._detection_pattern.search(response_text):
                        result["vulnerable"] = True
                        result["details"].append(
                            {
                                "payload": payload,
                                "location": "GET parameter",
                                "pattern_matched": True,
                            }
                        )

                except Exception:
                    continue

        except Exception as e:
            result["error"] = str(e)

        return result

    async def cleanup(self, target: str, **kwargs: Any) -> None:
        """Cleanup after testing."""
        pass
