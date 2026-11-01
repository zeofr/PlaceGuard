"""Simple test to verify LLM client handles list response format."""
import json
from extraction.llm_client import get_llm_client

print("Testing LLM client with list response format...")

# Initialize LLM client
llm = get_llm_client()

# Simple test prompt
prompt = """Extract criteria from this text and return as JSON array:

"We need CSE or AIML branch students with CGPA >= 7.5"

Return format:
[
  {"criterion_type": "allowed_branches", "operator": "in", "value": "CSE, AIML"},
  {"criterion_type": "min_cgpa", "operator": ">=", "value": "7.5"}
]
"""

print("Calling LLM...")
try:
    result = llm.generate_structured(prompt, temperature=0.1)
    print("\nSuccess! LLM returned:")
    print(json.dumps(result, indent=2))
    print(f"\nResponse type: {type(result)}")
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
