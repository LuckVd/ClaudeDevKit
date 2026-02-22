"""SQL Injection Detection Plugin - Basic SQL injection vulnerability scanner."""

import re
from typing import Any

__vuln_info__ = {
    "name": "SQL Injection Basic",
    "vuln_id": "CVE-2024-DEMO-SQLI",
    "severity": "high",
    "category": "injection",
    "description": "Detects basic SQL injection vulnerabilities in URL parameters",
    "author": "VulnScan Team",
    "version": "1.0.0",
    "references": [
        "https://owasp.org/www-community/attacks/SQL_Injection"
    ],
    "tags": ["sqli", "injection", "database"],
    "fingerprints": {
        "technologies": ["php", "asp", "jsp", "asp.net"],
        "paths": ["/search", "/product", "/user", "/api"],
    },
}

# Error patterns for SQL injection detection
SQL_ERRORS = [
    r"SQL syntax.*MySQL",
    r"Warning.*mysql_.*",
    r"MySqlException",
    r"PostgreSQL.*ERROR",
    r"Warning.*pg_.*",
    r"ORA-\d{5}",
    r"Microsoft SQL Server",
    r"SQLite3::SQLException",
    r"Syntax error.*query",
    r"unclosed quotation mark",
]


class SqlInjectionBasic:
    """SQL injection vulnerability checker."""

    def __init__(self) -> None:
        self._patterns = [re.compile(p, re.IGNORECASE) for p in SQL_ERRORS]
        self._payloads = [
            "'",
            '"',
            "' OR '1'='1",
            '" OR "1"="1',
            "1' AND '1'='1",
            "1\" AND \"1\"=\"1",
            "' UNION SELECT NULL--",
            "' UNION SELECT NULL,NULL--",
        ]

    async def verify(
        self, target: str, http_client: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Verify if target is vulnerable to SQL injection.

        Args:
            target: Target URL to test
            http_client: HTTP client instance
            **kwargs: Additional parameters

        Returns:
            Vulnerability result with status and details
        """
        result = {
            "vulnerable": False,
            "vulnerability": "SQL Injection",
            "severity": "high",
            "details": [],
            "evidence": None,
        }

        try:
            # Test each payload
            for payload in self._payloads:
                test_url = f"{target}?id={payload}"

                try:
                    response = await http_client.get(test_url)
                    response_text = response.text

                    # Check for SQL error patterns
                    for pattern in self._patterns:
                        match = pattern.search(response_text)
                        if match:
                            result["vulnerable"] = True
                            result["details"].append(
                                {
                                    "payload": payload,
                                    "error_pattern": match.group(),
                                    "status_code": response.status_code,
                                }
                            )
                            result["evidence"] = match.group()
                            return result

                except Exception:
                    continue

        except Exception as e:
            result["error"] = str(e)

        return result

    async def cleanup(self, target: str, **kwargs: Any) -> None:
        """Cleanup after testing."""
        pass
