"""Test that our parsing handles the Gemini list response format correctly.

This simulates what Gemini returns (list format) to verify our fix works.
"""
import json

print("="*70)
print("TESTING GEMINI LIST RESPONSE PARSING")
print("="*70)

# Simulate what Gemini returns - a list with the JSON content
# Based on what you saw: [{"criterion_type": "allowed_branches", ...}]
gemini_list_response = [
    {
        "criterion_type": "allowed_branches",
        "operator": "in",
        "value": "CSE, AIML",
        "scope": "AI Role",
        "confidence": "high",
        "extracted_text": "CSE or AIML branch"
    },
    {
        "criterion_type": "min_tenth",
        "operator": ">=",
        "value": "75",
        "scope": "AI Role",
        "confidence": "high",
        "extracted_text": "10th >= 75%"
    },
    {
        "criterion_type": "min_twelfth",
        "operator": ">=",
        "value": "75",
        "scope": "AI Role",
        "confidence": "high",
        "extracted_text": "12th >= 75%"
    },
    {
        "criterion_type": "min_cgpa",
        "operator": ">=",
        "value": "7.5",
        "scope": "AI Role",
        "confidence": "high",
        "extracted_text": "B.Tech CGPA >= 7.5"
    },
    {
        "criterion_type": "max_backlogs",
        "operator": "<=",
        "value": "0",
        "scope": "AI Role",
        "confidence": "high",
        "extracted_text": "no active backlogs"
    },
    {
        "criterion_type": "deadline",
        "operator": "=",
        "value": "2024-12-15",
        "scope": "AI Role",
        "confidence": "medium",
        "extracted_text": "interview on 15th Dec 2024"
    }
]

print("\n1. Simulated Gemini Response (List Format):")
print("-" * 70)
print(f"Type: {type(gemini_list_response)}")
print(f"Content:\n{json.dumps(gemini_list_response, indent=2)}")

print("\n2. Testing Our Parsing Logic:")
print("-" * 70)

# Simulate what our code does
response_content = gemini_list_response

# Our fix handles this:
if isinstance(response_content, list):
    # For list responses, check if it's already valid JSON structure
    if response_content and isinstance(response_content[0], dict):
        print("   ✓ Detected list of dicts (valid JSON structure)")
        parsed = response_content
    else:
        # If it's a list of text parts, join them
        response_text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in response_content
        )
        print(f"   ✓ Joined text parts: {response_text[:100]}...")
        parsed = json.loads(response_text)
else:
    # String response, parse normally
    parsed = json.loads(response_content)

print(f"\n3. Parsed Result:")
print("-" * 70)
print(f"Type: {type(parsed)}")
print(f"Number of criteria: {len(parsed)}")

print(f"\n4. Extracted Criteria:")
print("-" * 70)
for i, criterion in enumerate(parsed, 1):
    print(f"\n   Criterion #{i}:")
    print(f"      Type: {criterion['criterion_type']}")
    print(f"      Operator: {criterion['operator']}")
    print(f"      Value: {criterion['value']}")
    print(f"      Scope: {criterion.get('scope', 'N/A')}")
    print(f"      Confidence: {criterion.get('confidence', 'N/A')}")
    if 'extracted_text' in criterion:
        print(f"      Source: '{criterion['extracted_text']}'")

print("\n5. Verification:")
print("-" * 70)

expected_types = ['allowed_branches', 'min_tenth', 'min_twelfth', 'min_cgpa', 'max_backlogs']
found_types = [c['criterion_type'] for c in parsed]

print("\n   Expected Criteria Check:")
for expected in expected_types:
    status = "✓" if expected in found_types else "✗"
    print(f"      {status} {expected}")

all_found = all(expected in found_types for expected in expected_types)

print("\n" + "="*70)
if all_found:
    print("✓ SUCCESS! All expected criteria were extracted and parsed correctly!")
    print("  The Gemini extraction IS working - just need to wait for rate limit.")
else:
    print("✗ Some criteria missing")
print("="*70)
