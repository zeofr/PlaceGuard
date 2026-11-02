"""LLM-based email classifier for PlaceGuard.

Classifies placement emails into categories:
- new_offer: New placement opportunity announcement
- offer_update: Update to existing placement (changed criteria, deadline, etc.)
- shortlist: Shortlist announcement (not relevant for eligibility)
- other: Irrelevant emails (general announcements, reminders, etc.)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from core.schemas import RawMessage
from extraction.llm_client import LLMClient


class EmailClassification(BaseModel):
    """Result of email classification."""
    
    category: str  # "new_offer" | "offer_update" | "shortlist" | "other"
    confidence: float  # 0.0 to 1.0
    reason: str  # Why this classification was chosen
    company_name: str | None = None  # Extracted company name (if relevant)
    drive_id: str | None = None  # Suggested drive_id (if relevant)


class EmailClassifier:
    """Classifies placement emails using LLM."""
    
    def __init__(self, llm_client: LLMClient, confidence_threshold: float = 0.7):
        """Initialize email classifier.
        
        Args:
            llm_client: LLM client for classification
            confidence_threshold: Minimum confidence to accept classification
        """
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold
    
    def classify(self, message: RawMessage) -> EmailClassification:
        """Classify a single email message.
        
        Args:
            message: Raw message to classify
            
        Returns:
            EmailClassification with category and extracted info
        """
        prompt = self._build_classification_prompt(message.body)
        
        try:
            result = self.llm_client.generate_structured(
                prompt,
                temperature=0.1,  # Low temperature for consistent classification
            )
            
            # Validate and normalize category
            category = result.get("category", "other").lower()
            if category not in ["new_offer", "offer_update", "shortlist", "other"]:
                category = "other"
            
            # Extract fields
            confidence = float(result.get("confidence", 0.5))
            reason = result.get("reason", "No reason provided")
            company_name = result.get("company_name")
            drive_id = result.get("drive_id")
            
            # Generate drive_id if company name is available but drive_id is not
            if company_name and not drive_id:
                drive_id = self._generate_drive_id(company_name)
            
            return EmailClassification(
                category=category,
                confidence=confidence,
                reason=reason,
                company_name=company_name,
                drive_id=drive_id,
            )
        
        except Exception as e:
            # If LLM fails, default to "other" with low confidence
            print(f"Warning: Email classification failed: {e}")
            return EmailClassification(
                category="other",
                confidence=0.0,
                reason=f"Classification error: {str(e)}",
                company_name=None,
                drive_id=None,
            )
    
    def classify_batch(
        self, messages: list[RawMessage]
    ) -> list[EmailClassification]:
        """Classify multiple emails.
        
        Args:
            messages: List of raw messages to classify
            
        Returns:
            List of classifications in same order as input
        """
        return [self.classify(msg) for msg in messages]
    
    def is_relevant(self, classification: EmailClassification) -> bool:
        """Check if classified email is relevant for processing.
        
        Only "new_offer" and "offer_update" are relevant for eligibility extraction.
        
        Args:
            classification: Email classification result
            
        Returns:
            True if email should be processed
        """
        return (
            classification.category in ["new_offer", "offer_update"]
            and classification.confidence >= self.confidence_threshold
        )
    
    def _build_classification_prompt(self, email_body: str) -> str:
        """Build LLM prompt for email classification.
        
        Args:
            email_body: Email body text
            
        Returns:
            Prompt string
        """
        return f"""Analyze this placement email and classify it into one of these categories:

1. **new_offer**: A new placement opportunity or job opening announcement
   - Contains company name, role, and eligibility criteria
   - May include salary, deadline, registration link
   - Examples: "Amazon is hiring", "Google placement drive", "New opportunity at Microsoft"

2. **offer_update**: Update to an existing placement opportunity
   - Changes to eligibility criteria (CGPA, branch, backlogs)
   - Extended deadline or changed registration process
   - Clarifications or corrections to previous announcements
   - Examples: "Updated CGPA requirement for TCS", "Deadline extended for Infosys"

3. **shortlist**: Shortlist or selection announcement (NOT eligibility-related)
   - Lists of selected/shortlisted students
   - Interview schedules for specific students
   - Not relevant for eligibility checking
   - Examples: "Shortlisted students for Wipro", "Interview schedule"

4. **other**: Any other email not related to placement eligibility
   - General announcements, reminders
   - Event invitations, workshops
   - Administrative notices
   - Examples: "Reminder: Update your resume", "Workshop on interview skills"

Email:
---
{email_body}
---

Task:
1. Classify the email into ONE of the above categories
2. Extract the company name if this is a new_offer or offer_update
3. Provide your confidence level (0.0 to 1.0)
4. Explain your reasoning

Return JSON:
{{
  "category": "new_offer" | "offer_update" | "shortlist" | "other",
  "confidence": 0.95,
  "reason": "Brief explanation of why this category was chosen",
  "company_name": "Company Name" (or null if not applicable),
  "drive_id": "DRIVE_COMPANYNAME" (or null if not applicable)
}}

Guidelines:
- Be conservative: if unsure between new_offer and offer_update, choose other
- Confidence should be high (>0.8) only if the category is clear
- Extract full company name (e.g., "Tech Mahindra" not "TechM")
- Generate drive_id in format: DRIVE_<UPPERCASE_COMPANY_NAME> (e.g., DRIVE_TECHMAHINDRA)
- Remove spaces and special characters from drive_id
"""
    
    def _generate_drive_id(self, company_name: str) -> str:
        """Generate a drive_id from company name.
        
        Format: DRIVE_<UPPERCASE_COMPANY_NAME_NO_SPACES>
        
        Args:
            company_name: Company name
            
        Returns:
            Generated drive_id
        """
        # Remove special characters and spaces, convert to uppercase
        import re
        clean_name = re.sub(r"[^a-zA-Z0-9]", "", company_name).upper()
        return f"DRIVE_{clean_name}"
    
    def extract_drive_info(
        self, email_body: str, existing_drives: list[dict[str, str]] | None = None
    ) -> tuple[str | None, str | None]:
        """Extract drive/company information from email.
        
        Attempts to match against existing drives or extract new company name.
        This is a more focused extraction than full classification.
        
        Args:
            email_body: Email body text
            existing_drives: List of existing drives with drive_id and company_name
            
        Returns:
            Tuple of (drive_id, company_name) or (None, None)
        """
        drives_context = ""
        if existing_drives:
            drives_context = "\nExisting drives in system:\n" + "\n".join(
                f"- {d['drive_id']}: {d['company_name']}"
                for d in existing_drives
            )
        
        prompt = f"""Extract the company/placement drive information from this email.

Email:
---
{email_body}
---
{drives_context}

Task:
1. Identify the company name mentioned in the email
2. If the company matches an existing drive, use that drive_id
3. If it's a new company, provide the full company name and generate a drive_id
4. Be careful with abbreviations (e.g., "TCS" = "Tata Consultancy Services", "TechM" = "Tech Mahindra")

Return JSON:
{{
  "drive_id": "DRIVE_XXX",
  "company_name": "Full Company Name",
  "confidence": "high" | "medium" | "low"
}}

If no company can be identified, return:
{{
  "drive_id": null,
  "company_name": null,
  "confidence": "none"
}}
"""
        
        try:
            result = self.llm_client.generate_structured(prompt, temperature=0.0)
            
            if result.get("confidence") == "none" or not result.get("drive_id"):
                return None, None
            
            return result["drive_id"], result["company_name"]
        
        except Exception as e:
            print(f"Warning: Drive extraction failed: {e}")
            return None, None
