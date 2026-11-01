"""Test Ollama integration with PlaceGuard LLM client."""

from extraction.llm_client import get_llm_client
from config import settings

def test_ollama_connection():
    """Test basic Ollama connection and text generation."""
    print("=" * 60)
    print("Testing Ollama Integration")
    print("=" * 60)
    
    # Display config
    print(f"\nConfiguration:")
    print(f"  Provider: {settings.llm_provider}")
    print(f"  Base URL: {settings.ollama_base_url}")
    print(f"  Model: {settings.ollama_model}")
    print(f"  Temperature: {settings.ollama_temperature}")
    
    # Initialize client
    print(f"\n🔧 Initializing LLM client...")
    try:
        client = get_llm_client()
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # Test 1: Simple text generation
    print(f"\n📝 Test 1: Simple text generation")
    try:
        prompt = "Say 'Hello from Ollama!' and nothing else."
        response = client.generate(prompt, temperature=0.0)
        print(f"  Prompt: {prompt}")
        print(f"  Response: {response}")
        print("✅ Text generation successful")
    except Exception as e:
        print(f"❌ Text generation failed: {e}")
        return False
    
    # Test 2: Structured JSON output (like notice extraction)
    print(f"\n📋 Test 2: Structured JSON output")
    try:
        prompt = """Extract the following notice information:
        
"Google is hiring for SDE-2 positions. Eligibility: BE/BTech with 70% in 10th, 12th and degree. 
No active backlogs allowed. CTC: 15 LPA. Apply by 15th Dec 2024."

Return a JSON object with these fields:
- company_name (string)
- job_role (string)  
- min_percentage (number)
- max_backlogs (number)
- ctc_amount (number)
- deadline (string in YYYY-MM-DD format)
"""
        response = client.generate_structured(prompt, temperature=0.0)
        print(f"  Response JSON:")
        import json
        print(json.dumps(response, indent=2))
        print("✅ Structured output successful")
    except Exception as e:
        print(f"❌ Structured output failed: {e}")
        return False
    
    # Test 3: Token counting
    print(f"\n📊 Test 3: Token counting")
    test_text = "This is a test sentence for token counting."
    tokens = client.count_tokens(test_text)
    print(f"  Text: {test_text}")
    print(f"  Estimated tokens: {tokens}")
    print(f"  Total tokens used in session: {client.total_tokens_used}")
    print("✅ Token counting working")
    
    print(f"\n{'=' * 60}")
    print("🎉 All tests passed! Ollama is working correctly.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_ollama_connection()
    exit(0 if success else 1)
