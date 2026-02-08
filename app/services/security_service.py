"""
Security Service

Handles PII redaction and Prompt Injection detection.
Acts as a middleware for safety guardrails.
"""
import re
from app.config import settings

import requests
import logging

from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime, timedelta
from jose import jwt, JWTError # Requires python-jose
from passlib.context import CryptContext # Requires passlib

# Setup logger
logger = logging.getLogger(__name__)

class SecurityService:
    def __init__(self):
        self.enabled = settings.security_enabled
        self.redact_pii = settings.pii_redaction_enabled

        # ====================================================================
        # AUTHENTICATION SETUP
        # ====================================================================
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.secret_key
        self.algorithm = settings.jwt_algorithm
        self.expire_minutes = settings.access_token_expire_minutes
        self.lakera_guard_api_key = settings.lakera_guard_api_key

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


    # ========================================================================
    # NEW: LAKERA GUARD INTEGRATION
    # ========================================================================
    def _check_with_lakera(self, text: str) -> Tuple[bool, str]:
        """
        Query Lakera Guard API to detect prompt injections.

        Returns:
            (is_safe: bool, reason: str)
        """
# DEBUG 1: Check if key is loaded
        if not self.lakera_guard_api_key:
            print("❌ DEBUG: Lakera API Key is MISSING or Empty.")
            return True, ""

        print(f"✅ DEBUG: Key found (starts with {self.lakera_guard_api_key[:4]}...)")

        try:
            response = requests.post(
                "https://api.lakera.ai/v2/guard",
                headers={"Authorization": f"Bearer {self.lakera_guard_api_key}"},
                json={
                    "messages": [
                        {"role": "user", "content": text}
                    ]
                }
            )

            # DEBUG 2: Print the raw response
            print(f"📡 DEBUG: Lakera Status: {response.status_code}")
            print(f"📡 DEBUG: Lakera Response: {response.text}")

            if response.status_code != 200:
                logger.warning(f"Lakera Guard API Warning: {response.status_code} - {response.text}")
                return True, ""

            result = response.json()
            # [CHANGE 1a] Check the 'flagged' boolean in the response
            if result.get("flagged") is True:
                logger.info(f"Lakera Blocked Input: {result}")
                return False, "Lakera Guard: Prompt Injection Detected"

        except Exception as e:
            logger.error(f"Lakera Guard API Error: {e}")
            # Fail open (allow) if external service is down, but log error
            # Or fail closed (return False) depending on security policy
            return True, ""

        return True, ""

    def check_jailbreak(self, text: str) -> Tuple[bool, str]:
        """
        Check for prompt injection attempts.
        Returns: (is_safe: bool, reason: str)
        """
        if not self.enabled:
            return True, ""

        # 1. Check External Guardrail (Lakera) FIRST
        # This provides advanced AI-based detection before falling back to heuristics
        is_safe, reason = self._check_with_lakera(text)
        if not is_safe:
            return False, reason
        text_lower = text.lower()

        # 1. Heuristic Check (Fast)
        for keyword in self.injection_keywords:
            if keyword in text_lower:
                return False, f"Blocked keyword detected: '{keyword}'"

        # 2. Length Check (Simple anti-flood)
        if len(text) > 10000:
            return False, "Input exceeds safety length limits"

        return True, ""

    # ========================================================================
    #  PASSWORD & TOKEN MANAGEMENT
    # ========================================================================

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return self.pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        Encodes user ID, role, and scopes.
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)

        to_encode.update({"exp": expire})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT token.
        Returns payload dict if valid, None otherwise.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
