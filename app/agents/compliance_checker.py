"""
Compliance Checker Agent

Ensures all communications and recommendations comply with FCA regulations.
Validates messages, products, and customer interactions for regulatory compliance.
"""

from typing import Dict, Any, Optional, List
from groq import AsyncGroq

from langfuse import observe
from langfuse import get_client

from app.agents.base import BaseAgent, AgentConfig, AgentResponse


class ComplianceCheckerAgent(BaseAgent):
    """
    Compliance checker agent.

    Validates communications and recommendations for FCA compliance.
    """

    # ========================================================================
    # COMPLIANCE RULES
    # ========================================================================

    COMPLIANCE_RULES = {
        "prohibited_words": [
            "guaranteed",
            "risk-free",
            "no risk",
            "can't lose",
            "zero risk",
            "100% safe",
            "definitely",
            "promise",
        ],
        "required_disclaimers": {
            "investment": "Investments can go down as well as up",
            "loan": "Subject to status and affordability assessment",
            "credit": "Representative APR - your rate may differ",
            "savings": "Interest rates are variable and subject to change",
        },
        "sensitive_topics": [
            "debt",
            "bankruptcy",
            "foreclosure",
            "repossession",
            "default",
            "arrears",
        ],
        "mandatory_warnings": {
            "high_risk": "This product carries significant risk",
            "affordability": "Borrow only what you can afford to repay",
            "credit_impact": "Missed payments may affect your credit score",
        },
    }

    # FCA Principles (PRIN)
    FCA_PRINCIPLES = [
        "Integrity: Act with integrity in all dealings",
        "Skill, care and diligence: Exercise due skill, care and diligence",
        "Management and control: Take reasonable care to organize affairs responsibly",
        "Financial prudence: Maintain adequate financial resources",
        "Market conduct: Observe proper standards of market conduct",
        "Customers' interests: Pay due regard to customers' interests",
        "Communications: Pay due regard to information needs and communicate fairly",
        "Conflicts of interest: Manage conflicts of interest fairly",
        "Customers: relationships of trust: Take reasonable care for suitable relationships",
        "Clients' assets: Arrange adequate protection for clients' assets",
        "Relations with regulators: Deal with regulators in open and cooperative way",
    ]

    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize compliance checker agent."""
        super().__init__(name="compliance_checker", config=config)

        # Initialize Groq client
        self.client = AsyncGroq(api_key=self.config.api_key)

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    def _get_description(self) -> str:
        """Get agent description."""
        return (
            "Compliance Checker Agent - Validates all communications and "
            "recommendations for FCA regulatory compliance."
        )

    def _get_capabilities(self) -> List[str]:
        """Get agent capabilities."""
        return [
            "FCA compliance validation",
            "Prohibited language detection",
            "Required disclaimer verification",
            "Risk assessment",
            "Regulatory guidance",
        ]

    def _filter_contextual_false_positives(self, content_lower: str, issues: List[str]) -> List[str]:
        """Helper to remove false positives like 'not guaranteed'."""
        filtered = []
        for issue in issues:
            # Ignore if the bot explicitly said it is NOT guaranteed
            if "guaranteed" in issue and ("not guaranteed" in content_lower or "no loan is guaranteed" in content_lower):
                continue
            filtered.append(issue)
        return filtered

    # ========================================================================
    # CORE PROCESSING
    # ========================================================================
    @observe(name="ComplianceChecker")
    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Check content for FCA compliance.

        Args:
            input_data: Must contain 'content' (text to check)
            context: Optional context (product type, customer info)

        Returns:
            AgentResponse: Compliance check result
        """
        # Validate input
        await self.validate_input(input_data)

        # Log request
        self.log_request(input_data)

        # Extract content
        content = input_data.get("content", "")
        if not content:
            raise ValueError("Content is required for compliance check")

        # Extract context
        product_type = context.get("product_type", "") if context else ""

        # Perform compliance check
        compliance_result = await self._check_compliance(content, product_type)

        # Determine if compliant
        is_compliant = compliance_result["is_compliant"]

        # Build response message
        if is_compliant:
            response_content = "✅ Content is FCA compliant"
        else:
            response_content = f"⚠️ Compliance issues detected:\n\n"
            for issue in compliance_result["issues"]:
                response_content += f"- {issue}\n"

        # Create response
        response = self.create_response(
            content=response_content,
            metadata={
                "is_compliant": is_compliant,
                "issues": compliance_result["issues"],
                "warnings": compliance_result["warnings"],
                "suggestions": compliance_result["suggestions"],
                "required_disclaimers": compliance_result["required_disclaimers"],
            },
            confidence=compliance_result["confidence"],
        )

        # Log response
        self.log_response(response)

        return response

    # ========================================================================
    # COMPLIANCE CHECKING LOGIC
    # ========================================================================

    async def _check_compliance(
        self,
        content: str,
        product_type: str,
    ) -> Dict[str, Any]:
        """
        Check content for compliance issues.

        Args:
            content: Text to check
            product_type: Type of product (for context)

        Returns:
            dict: Compliance check results
        """
        # Rule-based checks
        rule_issues = self._check_rules(content)

        # LLM-based deep check
        llm_result = await self._llm_compliance_check(content, product_type)

        # Combine results
        all_issues = rule_issues + llm_result["issues"]

        # Determine compliance
        is_compliant = len(all_issues) == 0

        # Get required disclaimers
        required_disclaimers = self._get_required_disclaimers(content, product_type)

        return {
            "is_compliant": is_compliant,
            "issues": all_issues,
            "warnings": llm_result["warnings"],
            "suggestions": llm_result["suggestions"],
            "required_disclaimers": required_disclaimers,
            "confidence": 0.95 if is_compliant else 0.85,
        }

    def _check_rules(self, content: str) -> List[str]:
        """
        Check content against rule-based compliance.

        Args:
            content: Text to check

        Returns:
            List[str]: List of issues found
        """
        issues = []
        content_lower = content.lower()

        # Check for prohibited words
        for word in self.COMPLIANCE_RULES["prohibited_words"]:
            if word in content_lower:
                issues.append(
                    f"Prohibited language detected: '{word}'. "
                    f"FCA requires balanced, not misleading information."
                )

        return self._filter_contextual_false_positives(content_lower, issues)
    
    @observe(as_type="generation", name="Groq-Compliance-Check")
    async def _llm_compliance_check(
        self,
        content: str,
        product_type: str,
    ) -> Dict[str, Any]:
        """
        Deep compliance check using LLM.

        Args:
            content: Text to check
            product_type: Product type

        Returns:
            dict: LLM check results
        """

        langfuse = get_client()
        langfuse.update_current_generation(
            model=self.config.model_name,
            model_parameters={"temperature": 0.1}
        )
        # Build prompt
        prompt = self._build_compliance_prompt(content, product_type)

        try:

            # WRAP LLM CALL
            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=self.config.max_tokens,
                )

            response = await self.execute_with_retry(_call_llm)
            # Update Usage
            langfuse.update_current_generation(
                usage_details={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
            # Parse response
            result = self._parse_compliance_response(response.choices[0].message.content)

            return result
        except Exception as e:
            raise e

    def _build_compliance_prompt(
        self,
        content: str,
        product_type: str,
    ) -> str:
        """
        Build prompt for compliance check.

        Args:
            content: Text to check
            product_type: Product type

        Returns:
            str: Formatted prompt
        """
        # FCA principles summary
        principles_text = "\n".join([f"- {p}" for p in self.FCA_PRINCIPLES[:7]])

        product_context = ""
        if product_type:
            product_context = f"\nProduct Type: {product_type}"

        prompt = f"""Review the following content for FCA (Financial Conduct Authority) compliance.

Key FCA Principles:
{principles_text}

Content to Review:
"{content}"{product_context}

Check for:
1. Misleading or unclear language
2. Missing risk warnings
3. Unbalanced information (only benefits, no risks)
4. Guarantees or promises that can't be kept
5. Clarity of terms and conditions
6. Appropriate disclaimers
7. Fair treatment of customers

Respond in this format:
COMPLIANT: <YES or NO>
ISSUES: <comma-separated list of issues, or NONE>
WARNINGS: <comma-separated warnings, or NONE>
SUGGESTIONS: <improvements to make content more compliant>

Be strict - FCA compliance is critical for customer protection.
"""

        return prompt

    def _get_system_prompt(self) -> str:
        """
        Get system prompt for LLM.

        Returns:
            str: System prompt
        """
        return """You are an FCA compliance expert for a UK financial services company.

Your role:
- Review all customer-facing content for regulatory compliance
- Identify potential violations of FCA principles
- Ensure clear, fair, and not misleading communications
- Verify appropriate risk warnings and disclaimers
- Protect customer interests

FCA Standards:
- Communications must be clear, fair and not misleading (PRIN 7)
- Customers' interests must be paramount (PRIN 6)
- All material information must be disclosed
- Risk warnings must be prominent and clear
- No guarantees or promises unless absolutely certain
- Representative APR must be disclosed for credit products

Be thorough and strict - compliance violations can result in significant penalties."""

    def _parse_compliance_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM compliance response.

        Args:
            response_text: Raw LLM response

        Returns:
            dict: Parsed compliance result
        """
        # Extract fields
        compliant = True
        issues = []
        warnings = []
        suggestions = ""

        for line in response_text.strip().split("\n"):
            line = line.strip()

            if line.startswith("COMPLIANT:"):
                compliant_str = line.split(":", 1)[1].strip().upper()
                compliant = compliant_str == "YES"
            elif line.startswith("ISSUES:"):
                issues_str = line.split(":", 1)[1].strip()
                if issues_str != "NONE":
                    issues = [i.strip() for i in issues_str.split(",")]
            elif line.startswith("WARNINGS:"):
                warnings_str = line.split(":", 1)[1].strip()
                if warnings_str != "NONE":
                    warnings = [w.strip() for w in warnings_str.split(",")]
            elif line.startswith("SUGGESTIONS:"):
                suggestions = line.split(":", 1)[1].strip()

        return {
            "compliant": compliant,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _get_required_disclaimers(
        self,
        content: str,
        product_type: str,
    ) -> List[str]:
        """
        Get required disclaimers based on content and product type.

        Args:
            content: Message content
            product_type: Product type

        Returns:
            List[str]: Required disclaimers
        """
        disclaimers = []
        content_lower = content.lower()

        # Check product type
        if product_type:
            disclaimer = self.COMPLIANCE_RULES["required_disclaimers"].get(product_type)
            if disclaimer:
                disclaimers.append(disclaimer)

        # Check content for keywords
        if any(word in content_lower for word in ["invest", "return", "profit"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["investment"])

        if any(word in content_lower for word in ["loan", "borrow", "mortgage"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["loan"])

        if any(word in content_lower for word in ["credit", "apr", "interest rate"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["credit"])

        # Check for sensitive topics
        for topic in self.COMPLIANCE_RULES["sensitive_topics"]:
            if topic in content_lower:
                disclaimers.append(
                    "We understand this may be a difficult situation. "
                    "Free debt advice is available from MoneyHelper or StepChange."
                )
                break

        return list(set(disclaimers))  # Remove duplicates

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def get_prohibited_words(self) -> List[str]:
        """
        Get list of prohibited words.

        Returns:
            List[str]: Prohibited words
        """
        return self.COMPLIANCE_RULES["prohibited_words"]

    def get_fca_principles(self) -> List[str]:
        """
        Get FCA principles.

        Returns:
            List[str]: FCA principles
        """
        return self.FCA_PRINCIPLES
