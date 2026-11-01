"""Quick test to verify Gemini extraction works with list response format."""
import json
from datetime import datetime
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice
from core.schemas import SourceType

# Initialize LLM client
llm = get_llm_client()

# Test notice
notice_text = """
We are hiring for AI Role!

Requirements:
- Branch: CSE or AIML only
- 10th: >= 75%
- 12th: >= 75%
- B.Tech CGPA: >= 7.5
- No active backlogs
- Interview scheduled for 15th December 2024
"""

print("Testing Gemini extraction with list response format fix...")
print(f"Notice text: {notice_text[:100]}...")
print()
print("Calling Gemini API...")
print()

# Extract criteria
result = extract_criteria_from_notice(
    notice_text=notice_text,
    source_id="test_msg_001",
    source_type=SourceType.PLACEMENT_CELL_EMAIL,
    timestamp=datetime.fromisoformat("2024-12-01T10:00:00"),
    drive_id="drive_001",
    llm_client=llm
)

print("Extraction successful!")
print(json.dumps(result, indent=2))
print()
print(f"Total criteria extracted: {len(result['criteria'])}")
