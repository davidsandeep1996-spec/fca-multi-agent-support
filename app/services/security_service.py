"""
Security Service

Handles PII redaction and Prompt Injection detection.
Acts as a middleware for safety guardrails.
"""
import re
from typing import Tuple, List
from app.config import settings

class SecurityService:
    def __init__(self):
        self.enabled = settings.security_enabled
        self.redact_pii = settings.pii_redaction_enabled

        # 1. PII Regex Patterns
        self.pii_patterns = {
            "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "PHONE_UK": r'(?:(?:\+44\s?|0)(?:7\d{3}|\d{4})\s?\d{6})',
            "CREDIT_CARD": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        }

        # 2. Jailbreak / Injection Keywords (Heuristic)
        # In production, use a dedicated classifier model (e.g., Lakera Guard or specialized LLM check)
        self.injection_keywords = [
            # Standard Jailbreaks
            "ignore previous instructions",
            "act as a pirate",
            "system prompt",
            "developer mode",
            "you are now",

            # Financial Crimes (Catches "launder money")
            "launder money",
            "money laundering",
            "forge a check",
            "bypass 2fa",

            # Technical/Obfuscation Attacks (Catches "Base64")
            "base64",
            "encoded string",

            # Persona/System Attacks (Catches "System Override", "Forget you are")
            "system override",
            "disable_content_filter",
            "unrestrained ai",
            "forget you are",
            "simulated",
            "hypothetically" # Risky, but good for banking safety
        ]

    def sanitize_input(self, text: str) -> str:
        """
        Redact PII from text if enabled.
        """
        if not self.enabled or not self.redact_pii:
            return text

        sanitized = text
        for label, pattern in self.pii_patterns.items():
            sanitized = re.sub(pattern, f"[{label}_REDACTED]", sanitized)

        return sanitized

    def check_jailbreak(self, text: str) -> Tuple[bool, str]:
        """
        Check for prompt injection attempts.
        Returns: (is_safe: bool, reason: str)
        """
        if not self.enabled:
            return True, ""

        text_lower = text.lower()

        # 1. Heuristic Check (Fast)
        for keyword in self.injection_keywords:
            if keyword in text_lower:
                return False, f"Blocked keyword detected: '{keyword}'"

        # 2. Length Check (Simple anti-flood)
        if len(text) > 10000:
            return False, "Input exceeds safety length limits"

        return True, ""
