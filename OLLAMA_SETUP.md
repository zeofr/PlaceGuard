# Using Ollama with PlaceGuard

Ollama allows you to run LLMs locally - no API keys, no rate limits, completely free!

## Why Ollama?

✅ **Free forever** - No API costs  
✅ **No rate limits** - Test as much as you want  
✅ **Works offline** - No internet required after model download  
✅ **Privacy** - Your data stays on your machine  
✅ **Fast** - Local inference with GPU acceleration support  

## Setup Steps

### 1. Install Ollama

Download and install from: **https://ollama.ai**

Windows: Download the installer and run it  
Mac: `brew install ollama`  
Linux: `curl -fsSL https://ollama.com/install.sh | sh`

### 2. Pull a Model

After installation, pull a model. For PlaceGuard, we recommend:

```bash
# Good balance of quality and speed (4.7GB)
ollama pull llama3.1:8b

# Or for better quality if you have RAM (40GB)
ollama pull llama3.1:70b

# Or a smaller/faster option (2GB)
ollama pull llama3.2:3b
```

### 3. Verify Ollama is Running

```bash
# Check if Ollama service is running
ollama list

# Test a simple prompt
ollama run llama3.1:8b "Hello, how are you?"
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install `langchain-ollama` which is needed for the integration.

### 5. Configure PlaceGuard

Your `.env` is already configured to use Ollama by default:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TEMPERATURE=0.1
```

If you pulled a different model, update `OLLAMA_MODEL` accordingly.

### 6. Test It!

```bash
# Run the test script
python test_llm_client_list.py

# Or test the full extraction
python test_gemini_fix.py
```

## Switching Between Providers

You can easily switch between Ollama and Gemini by changing `.env`:

```env
# Use Ollama (local, free)
LLM_PROVIDER=ollama

# Or use Gemini (cloud, may have rate limits)
LLM_PROVIDER=gemini
```

No code changes needed!

## Troubleshooting

**"Connection refused" error:**
- Make sure Ollama is running: `ollama serve`
- Check the base URL in `.env` matches: `http://localhost:11434`

**Model not found:**
- Pull the model first: `ollama pull llama3.1:8b`
- Check available models: `ollama list`

**Slow performance:**
- Try a smaller model: `ollama pull llama3.2:3b`
- Or ensure GPU acceleration is working (check Ollama logs)

## Recommended Models for PlaceGuard

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| llama3.2:3b | 2GB | Fast | Good | Quick testing, limited RAM |
| llama3.1:8b | 4.7GB | Medium | Very Good | **Recommended** - Best balance |
| llama3.1:70b | 40GB | Slower | Excellent | Production, high accuracy needed |
| mistral:7b | 4.1GB | Fast | Good | Alternative to Llama |

Choose based on your RAM and accuracy needs!
