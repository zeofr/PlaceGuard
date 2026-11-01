"""Ultra-simple test to check if Gemini API is responding at all."""
import sys
from extraction.llm_client import get_llm_client

print("Testing Gemini API with simple request...")
print("-" * 50)

try:
    # Initialize client
    print("1. Creating Gemini client...")
    llm = get_llm_client("gemini")
    print("   ✓ Client created")
    
    # Try a very simple prompt
    print("\n2. Sending simple prompt...")
    response = llm.generate("Say 'Hello'", temperature=0.1, max_tokens=10)
    print(f"   ✓ Response received: '{response}'")
    
    print("\n3. Testing JSON extraction...")
    json_response = llm.generate_structured(
        'Return this as JSON: {"status": "working", "number": 42}',
        temperature=0.1
    )
    print(f"   ✓ JSON response: {json_response}")
    
    print("\n" + "="*50)
    print("SUCCESS! Gemini API is working properly.")
    print("="*50)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
