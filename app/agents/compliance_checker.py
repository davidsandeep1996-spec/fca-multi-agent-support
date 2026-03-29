"""
Compliance Checker Agent

Ensures all communications and recommendations comply with FCA regulations.
Validates messages, products, and customer interactions for regulatory compliance.
"""

from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from pydantic import BaseModel, Field

from langfuse import observe
from langfuse import get_client

from app.agents.base import BaseAgent, AgentConfig, AgentResponse

# ============================================================================
# ENTERPRISE SCHEMAS
# ============================================================================

class ComplianceAnalysis(BaseModel):
    """Strict schema for FCA compliance evaluation."""
    is_compliant: bool = Field(description="True if the content strictly adheres to FCA principles.")
    issues: List[str] = Field(description="List of specific compliance violations. Empty if none.")
    warnings: List[str] = Field(description="List of potential warnings or borderline issues.")
    suggestions: str = Field(description="Suggestions to improve compliance or clarity.")

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
            "guaranteed", "risk-free", "no risk", "can't lose",
            "zero risk", "100% safe", "definitely", "promise",
        ],
        "required_disclaimers": {
            "investment": "Investments can go down as well as up",
            "loan": "Subject to status and affordability assessment",
            "credit": "Representative APR - your rate may differ",
            "savings": "Interest rates are variable and subject to change",
        },
        "sensitive_topics": [
            "debt", "bankruptcy", "foreclosure", "repossession", "default", "arrears",
        ],
        "mandatory_warnings": {
            "high_risk": "This product carries significant risk",
            "affordability": "Borrow only what you can afford to repay",
            "credit_impact": "Missed payments may affect your credit score",
        },
    }

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
        super().__init__(name="compliance_checker", config=config)
        self.client = AsyncGroq(api_key=self.config.api_key)

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    def _get_description(self) -> str:
        return "Compliance Checker Agent - Validates all communications and recommendations for FCA regulatory compliance."

    def _get_capabilities(self) -> List[str]:
        return [
            "FCA compliance validation",
            "Prohibited language detection",
            "Required disclaimer verification",
            "Risk assessment",
            "Regulatory guidance",
        ]

    def _filter_contextual_false_positives(self, content_lower: str, issues: List[str]) -> List[str]:
        filtered = []
        for issue in issues:
            if "guaranteed" in issue and ("not guaranteed" in content_lower or "no loan is guaranteed" in content_lower):
                continue
            filtered.append(issue)
        return filtered

    # ========================================================================
    # CORE PROCESSING
    # ========================================================================

    @observe(name="ComplianceChecker")
    async def process(self, input_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        self.log_request(input_data)

        # ENTERPRISE FIX: Move EVERYTHING into the try block to prevent 500 crashes
        try:
            await self.validate_input(input_data)
            content = input_data.get("content", "")

            if not content:
                raise ValueError("Content is required for compliance check")

            product_type = context.get("product_type", "") if context else ""

            compliance_result = await self._check_compliance(content, product_type)
            is_compliant = compliance_result["is_compliant"]

            if is_compliant:
                response_content = "✅ Content is FCA compliant"
            else:
                response_content = "⚠️ Compliance issues detected:\n\n"
                for issue in compliance_result["issues"]:
                    response_content += f"- {issue}\n"

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
            self.log_response(response)
            return response

        except Exception as e:
            self.logger.error(f"Compliance check error: {e}")
            return self.create_response(
                content="⚠️ Compliance check failed due to technical difficulties. Content must be manually reviewed.",
                metadata={
                    "is_compliant": False,
                    "error": str(e),
                    "issues": ["System validation failed"],
                    "warnings": [],
                    "suggestions": "",
                    "required_disclaimers": []
                },
                confidence=0.0,
            )

    # ========================================================================
    # COMPLIANCE CHECKING LOGIC (SHORT-CIRCUIT UPGRADE)
    # ========================================================================

    async def _check_compliance(self, content: str, product_type: str) -> Dict[str, Any]:
        """Hybrid Short-Circuit Logic: Fast rules first, LLM second."""

        # 1. FAST HEURISTIC CHECK (Zero Cost, 1ms latency)
        rule_issues = self._check_rules(content)

        # [NEW] SHORT-CIRCUIT: If a hard rule is violated, stop immediately!
        if len(rule_issues) > 0:
            return {
                "is_compliant": False,
                "issues": rule_issues,
                "warnings": ["Fast keyword heuristic triggered. LLM check bypassed to save time/cost."],
                "suggestions": "Remove prohibited words before requesting a full review.",
                "required_disclaimers": self._get_required_disclaimers(content, product_type),
                "confidence": 0.99  # 99% confident because it's a hard-coded strict rule
            }

        # 2. DEEP SEMANTIC CHECK (Only runs if the text passed the fast heuristics)
        llm_result = await self._llm_compliance_check(content, product_type)
        is_compliant = len(llm_result["issues"]) == 0

        return {
            "is_compliant": is_compliant,
            "issues": llm_result["issues"],
            "warnings": llm_result["warnings"],
            "suggestions": llm_result["suggestions"],
            "required_disclaimers": self._get_required_disclaimers(content, product_type),
            "confidence": 0.95 if is_compliant else 0.85,
        }

    def _check_rules(self, content: str) -> List[str]:
        issues = []
        content_lower = content.lower()
        for word in self.COMPLIANCE_RULES["prohibited_words"]:
            if word in content_lower:
                issues.append(f"Prohibited language detected: '{word}'. FCA requires balanced, not misleading information.")
        return self._filter_contextual_false_positives(content_lower, issues)

    @observe(as_type="generation", name="Groq-Compliance-Check")
    async def _llm_compliance_check(self, content: str, product_type: str) -> Dict[str, Any]:
        langfuse = get_client()
        langfuse.update_current_generation(model=self.config.model_name, model_parameters={"temperature": 0.1})

        prompt = self._build_compliance_prompt(content, product_type)

        try:
            async def _call_llm():
                return await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"}
                )

            response = await self.execute_with_retry(_call_llm)

            if hasattr(response, 'usage') and response.usage:
                langfuse.update_current_generation(
                    usage_details={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                )

            analysis = ComplianceAnalysis.model_validate_json(response.choices[0].message.content)
            return analysis.model_dump()

        except Exception as e:
            self.logger.error(f"LLM Parsing Error: {e}")
            return {
                "is_compliant": False,
                "issues": ["LLM Validation Failed. Requires manual review."],
                "warnings": [],
                "suggestions": "Check system logs."
            }

    def _build_compliance_prompt(self, content: str, product_type: str) -> str:
        principles_text = "\n".join([f"- {p}" for p in self.FCA_PRINCIPLES[:7]])
        product_context = f"\nProduct Type: {product_type}" if product_type else ""

        return f"""Review the following content for FCA (Financial Conduct Authority) compliance.

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

You MUST respond with a single valid JSON object. Do NOT wrap it in a list or array.
It must contain exactly these keys: "is_compliant" (boolean), "issues" (list of strings), "warnings" (list of strings), and "suggestions" (string).

Example Output:
{{
    "is_compliant": false,
    "issues": ["The content promises high returns without mentioning risk."],
    "warnings": ["Tone is slightly aggressive."],
    "suggestions": "Add the standard investment risk warning."
}}

Be strict - FCA compliance is critical for customer protection.
"""

    def _get_system_prompt(self) -> str:
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

    def _get_required_disclaimers(self, content: str, product_type: str) -> List[str]:
        disclaimers = []
        content_lower = content.lower()

        if product_type:
            disclaimer = self.COMPLIANCE_RULES["required_disclaimers"].get(product_type)
            if disclaimer:
                disclaimers.append(disclaimer)

        if any(word in content_lower for word in ["invest", "return", "profit"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["investment"])

        if any(word in content_lower for word in ["loan", "borrow", "mortgage"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["loan"])

        if any(word in content_lower for word in ["credit card", "apr", "credit limit", "overdraft"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["credit"])

        if any(word in content_lower for word in ["savings", "bond", "deposit", "interest rate"]):
            disclaimers.append(self.COMPLIANCE_RULES["required_disclaimers"]["savings"])

        for topic in self.COMPLIANCE_RULES["sensitive_topics"]:
            if topic in content_lower:
                disclaimers.append(
                    "We understand this may be a difficult situation. "
                    "Free debt advice is available from MoneyHelper or StepChange."
                )
                break

        return list(set(disclaimers))

    def get_prohibited_words(self) -> List[str]:
        return self.COMPLIANCE_RULES["prohibited_words"]

    def get_fca_principles(self) -> List[str]:
        return self.FCA_PRINCIPLES
