"""Test a single notice extraction to verify categorization works correctly."""
import json
from datetime import datetime
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice
from core.schemas import SourceType

# Sample placement notice
notice_text = """
Subject: Amazon SDE Internship - Summer 2025

Dear Students,

Amazon is hiring for Software Development Engineer (SDE) Intern positions for Summer 2025.

Eligibility Criteria:
- Branches: CSE, ISE, AIML only
- B.Tech CGPA: Minimum 7.5
- 10th Percentage: >= 75%
- 12th Percentage: >= 75%
- No active backlogs allowed
- Students with prior internship offers are NOT eligible

Interview Details:
- Date: 15th December 2024
- Time: 10:00 AM
- Venue: Seminar Hall

Please register by 10th December 2024.

Regards,
Placement Cell
"""

print("="*70)
print("TESTING PLACEMENT NOTICE EXTRACTION")
print("="*70)
print("\nNotice Text:")
print("-" * 70)
print(notice_text)
print("-" * 70)

try:
    # Initialize LLM client
    print("\n1. Initializing LLM client...")
    llm = get_llm_client()
    print(f"   ✓ Using provider: {llm.__class__.__name__}")
    
    # Extract criteria
    print("\n2. Extracting criteria from notice...")
    facts = extract_criteria_from_notice(
        notice_text=notice_text,
        source_id="test_amazon_notice_001",
        source_type=SourceType.PLACEMENT_CELL_EMAIL,
        timestamp=datetime.fromisoformat("2024-12-01T10:00:00"),
        drive_id="amazon_sde_2025",
        llm_client=llm
    )
    
    print(f"   ✓ Extracted {len(facts)} criteria")
    
    # Display results
    print("\n3. Extracted Criteria:")
    print("="*70)
    
    for i, fact in enumerate(facts, 1):
        print(f"\n   Criterion #{i}:")
        print(f"      Type: {fact.criterion_type}")
        print(f"      Operator: {fact.operator}")
        print(f"      Value: {fact.value}")
        print(f"      Scope: {fact.scope}")
        print(f"      Confidence: {fact.confidence}")
        if fact.extracted_text:
            print(f"      Source Text: '{fact.extracted_text}'")
    
    # Verify expected criteria
    print("\n4. Verification:")
    print("="*70)
    
    expected_types = {
        'allowed_branches': False,
        'min_cgpa': False,
        'min_tenth': False,
        'min_twelfth': False,
        'max_backlogs': False,
        'has_prior_offer': False
    }
    
    for fact in facts:
        if fact.criterion_type in expected_types:
            expected_types[fact.criterion_type] = True
    
    print("\n   Expected Criteria Check:")
    for criterion_type, found in expected_types.items():
        status = "✓" if found else "✗"
        print(f"      {status} {criterion_type}: {'Found' if found else 'MISSING'}")
    
    missing = [k for k, v in expected_types.items() if not v]
    if missing:
        print(f"\n   ⚠️  Missing criteria: {', '.join(missing)}")
    else:
        print(f"\n   ✓ All expected criteria extracted!")
    
    # Check specific values
    print("\n   Value Verification:")
    for fact in facts:
        if fact.criterion_type == 'allowed_branches':
            expected = "CSE, ISE, AIML"
            matches = set(fact.value.upper().replace(' ', '').split(',')) == set(expected.upper().replace(' ', '').split(','))
            status = "✓" if matches else "✗"
            print(f"      {status} Branches: Expected '{expected}', Got '{fact.value}'")
        
        elif fact.criterion_type == 'min_cgpa':
            expected = "7.5"
            matches = fact.value == expected
            status = "✓" if matches else "✗"
            print(f"      {status} CGPA: Expected '{expected}', Got '{fact.value}'")
        
        elif fact.criterion_type == 'min_tenth':
            expected = "75"
            matches = fact.value == expected
            status = "✓" if matches else "✗"
            print(f"      {status} 10th: Expected '{expected}%', Got '{fact.value}%'")
        
        elif fact.criterion_type == 'min_twelfth':
            expected = "75"
            matches = fact.value == expected
            status = "✓" if matches else "✗"
            print(f"      {status} 12th: Expected '{expected}%', Got '{fact.value}%'")
        
        elif fact.criterion_type == 'max_backlogs':
            expected = "0"
            matches = fact.value == expected
            status = "✓" if matches else "✗"
            print(f"      {status} Backlogs: Expected '{expected}', Got '{fact.value}'")
        
        elif fact.criterion_type == 'has_prior_offer':
            expected = "false"
            matches = fact.value.lower() == expected
            status = "✓" if matches else "✗"
            print(f"      {status} Prior Offer: Expected '{expected}', Got '{fact.value}'")
    
    print("\n" + "="*70)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("="*70)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()
