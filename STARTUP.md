# PlaceGuard — Getting Started Guide

Complete setup instructions for developers cloning PlaceGuard for the first time.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** and **npm** - [Download](https://nodejs.org/)
- **Git** - [Download](https://git-scm.com/)

### Optional (Recommended)

- **Ollama** (for local LLM) - [Download](https://ollama.ai/) - Free, no API key needed
- **Gemini API Key** - [Get Free Key](https://makersuite.google.com/app/apikey) - Alternative to Ollama

### Verify Installations

```bash
python --version    # Should be 3.10 or higher
node --version      # Should be 18 or higher
npm --version       # Should be included with Node.js
git --version       # Any recent version
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/placeguard.git
cd placeguard
```

### 2. Backend Setup

#### Install Python Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your preferred text editor
# Minimum required: Set LLM_PROVIDER and corresponding API key
```

**Quick LLM Setup Options:**

**Option A: Use Ollama (Local, Free, No API Key)**
```bash
# Install Ollama from https://ollama.ai
# Pull the model:
ollama pull llama3.1:8b

# In .env, set:
# LLM_PROVIDER=ollama
```

**Option B: Use Gemini (Cloud, Free Tier Available)**
```bash
# Get API key from https://makersuite.google.com/app/apikey

# In .env, set:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your_actual_api_key_here
```

#### Initialize the Database

```bash
# Run database migrations
alembic upgrade head

# Load sample data (students, drives, criteria)
python data/load_data.py
```

#### Start the Backend Server

```bash
# Start the FastAPI server
uvicorn api.main:app --reload --port 8000
```

The backend API should now be running at **http://localhost:8000**

You can verify it's working by visiting: http://localhost:8000/docs

### 3. Frontend Setup

Open a **new terminal window** (keep the backend running):

```bash
cd frontend

# Install Node.js dependencies
npm install

# Copy environment file
cp .env.local.example .env.local

# Start the development server
npm run dev
```

The frontend should now be running at **http://localhost:3000**

---

## 🎓 Using the Application

### Test Login Credentials

After loading sample data, you can log in with any of these test accounts:

| USN (Username) | Date of Birth | Name | Branch |
|---------------|---------------|------|--------|
| 1MS22CS042 | 2003-04-15 | Arjun Mehta | CSE |
| 1MS22IS017 | 2003-08-22 | Priya Sharma | ISE |
| 1MS22CS008 | 2003-02-28 | Sneha Patel | CSE |

### Navigation Flow

1. **Login** → Enter USN and Date of Birth
2. **Dashboard** → View all placement drives
3. **Drive Details** → Click any drive to see:
   - Current eligibility requirements (formatted)
   - Timeline of requirement updates
   - Check your eligibility button
4. **Check Eligibility** → Click button to see if you qualify

---

## 📨 Ingesting Test Notices

Two ways to feed new placement notices into the pipeline (extraction → reconciliation →
rule engine) without waiting on real Gmail/WhatsApp integrations. Both require the backend
server running (`uvicorn api.main:app --reload --port 8000`).

### Mock WhatsApp Console

A small web UI for posting WhatsApp-style messages (placement cell, coordinator, or student),
which get auto-processed into Facts a few seconds after posting.

```bash
uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001
```

Open **http://localhost:8001**, pick a sender role, write a message (e.g. "Tech Mahindra
minimum CGPA changed to 6.5"), and submit. It's processed automatically in the background —
no extra command needed. To trigger processing manually instead (e.g. if auto-processing is
disabled or you posted while the API server was down):

```bash
curl -X POST http://localhost:8000/ingest/process-whatsapp
```

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ingest/process-whatsapp
```

### Manual Email Notice Ingestion

There's no console UI for email — post the notice text directly to the generic ingestion
endpoint instead, with `source_type` set to the email channel:

```bash
curl -X POST http://localhost:8000/ingest/notice \
  -H "Content-Type: application/json" \
  -d '{
        "notice_text": "TechCorp hiring 2027 — CGPA 7.5+, CSE/ISE only, no active backlogs. Link to apply: https://forms.gle/example",
        "source_id": "manual_email_techcorp_001",
        "source_type": "placement_cell_email",
        "drive_id": "DRIVE_TECHCORP",
        "drive_name": "TechCorp"
      }'
```

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ingest/notice `
  -ContentType "application/json" `
  -Body (@{
      notice_text = "TechCorp hiring 2027 — CGPA 7.5+, CSE/ISE only, no active backlogs. Link to apply: https://forms.gle/example"
      source_id   = "manual_email_techcorp_001"
      source_type = "placement_cell_email"
      drive_id    = "DRIVE_TECHCORP"
      drive_name  = "TechCorp"
  } | ConvertTo-Json)
```

- `source_id` must be unique per message (re-posting the same `source_id` is a no-op — Facts
  are append-only and never re-extracted).
- `source_type` can be any of: `official_company_pdf`, `placement_cell_email`,
  `placement_cell_whatsapp`, `coordinator_whatsapp`, `student_portal`, `student_whatsapp` —
  this is what sets the message's authority rank for reconciliation.
- `timestamp` is optional (defaults to now); pass an ISO datetime to backdate a message when
  testing temporal-conflict scenarios.
- The same endpoint also works for WhatsApp-style text if you'd rather skip the console —
  just set `source_type` to one of the WhatsApp values above.

---

## 📁 Project Structure

```
PlaceGuard/
├── api/                    # FastAPI backend
│   ├── main.py            # API entry point
│   └── routes/            # API endpoints
├── database/              # Database models and connection
│   ├── models.py          # SQLAlchemy models
│   └── crud.py            # Database operations
├── extraction/            # LLM-based notice extraction
│   └── notice_extractor.py
├── explanation/           # Eligibility explanation generation
│   └── generator.py
├── ingestion/             # Multi-source notice ingestion
│   ├── mock_email/
│   └── mock_whatsapp/
├── data/                  # Sample data and loaders
│   ├── students.json      # Test student profiles
│   ├── notices.json       # Sample placement notices
│   └── load_data.py       # Data loading script
├── alembic/               # Database migrations
├── frontend/              # Next.js frontend
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── components/   # React components
│   │   └── lib/          # Utilities (API, auth, formatters)
│   ├── public/           # Static assets
│   └── package.json      # Node.js dependencies
├── .env.example          # Backend environment template
├── requirements.txt      # Python dependencies
└── README.md            # Project overview
```

---

## 🔧 Detailed Setup

### Backend Environment Variables Explained

Open `.env` and configure:

#### Database
```bash
# Default (SQLite - no setup needed):
DATABASE_URL=sqlite:///./placeguard_dev.db

# For Production (PostgreSQL):
# DATABASE_URL=postgresql://user:password@localhost:5432/placeguard
```

#### LLM Provider
```bash
# Choose one: ollama | gemini | openai | claude
LLM_PROVIDER=gemini

# If using Gemini (RECOMMENDED for beginners):
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash-latest

# If using Ollama (for offline/local use):
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1:8b
```

#### Security
```bash
# Change this in production!
JWT_SECRET=your_secret_key_here_change_in_production
JWT_EXPIRATION_HOURS=24
```

### Frontend Environment Variables

The frontend uses Next.js API rewrites, so minimal configuration is needed:

```bash
# frontend/.env.local
NEXT_PUBLIC_APP_NAME=PlaceGuard
```

The API proxy is configured in `frontend/next.config.js` to forward requests from `/api/*` to `http://localhost:8000/*`.

---

## 🧪 Running Tests (Optional)

```bash
# Backend tests
pytest

# Frontend tests (if available)
cd frontend
npm test
```

---

## 🐛 Troubleshooting

### Backend Issues

**Issue: `alembic: command not found`**
```bash
# Make sure virtual environment is activated and dependencies installed
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Issue: `ModuleNotFoundError: No module named 'langchain'`**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Issue: `Connection refused` when starting backend**
```bash
# Port 8000 might be in use. Try a different port:
uvicorn api.main:app --reload --port 8001
# Update frontend/next.config.js to match the new port
```

**Issue: LLM errors or "No API key" errors**
```bash
# Verify .env file exists and has correct values
cat .env  # On Windows: type .env

# Make sure you've set LLM_PROVIDER and the corresponding API key
# OR install and run Ollama if using local LLM
```

### Frontend Issues

**Issue: `npm install` fails**
```bash
# Clear npm cache and retry
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

**Issue: "Invalid hook call" errors**
```bash
# Clean Next.js cache and restart
rm -rf .next
npm run dev
```

**Issue: Frontend can't connect to backend**
```bash
# Verify backend is running on port 8000
# Check browser console for CORS errors
# Verify next.config.js has correct backend URL
```

**Issue: Login doesn't work**
```bash
# Make sure you've loaded sample data:
cd .. # Go back to project root
python data/load_data.py

# Use test credentials from the "Test Login Credentials" section above
```

---

## 🚢 Production Deployment

### Backend

1. **Use PostgreSQL instead of SQLite**
   ```bash
   # Install PostgreSQL driver
   pip install psycopg2-binary
   
   # Update DATABASE_URL in .env
   DATABASE_URL=postgresql://user:password@host:5432/dbname
   ```

2. **Generate a secure JWT secret**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Use a production WSGI server**
   ```bash
   pip install gunicorn
   gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

### Frontend

```bash
cd frontend
npm run build
npm start
```

Or deploy to Vercel/Netlify:
```bash
# Vercel
vercel --prod

# Netlify
netlify deploy --prod
```

---

## 📚 Additional Resources

- **Backend API Docs**: http://localhost:8000/docs (when server is running)
- **Design System**: See `frontend/DESIGN_SYSTEM.md`
- **Architecture**: See `DESIGN.md`
- **Implementation Details**: See `IMPLEMENTATION.md`

---

## 🆘 Getting Help

1. Check the troubleshooting section above
2. Review error messages in:
   - Backend terminal
   - Frontend terminal  
   - Browser console (F12)
3. Check existing issues in the GitHub repository
4. Create a new issue with:
   - Steps to reproduce
   - Error messages
   - Environment details (OS, Python version, Node version)

---

## ✅ Verification Checklist

Before considering setup complete, verify:

- [ ] Backend server starts without errors at http://localhost:8000
- [ ] Backend API docs load at http://localhost:8000/docs
- [ ] Frontend starts without errors at http://localhost:3000
- [ ] Can log in with test credentials
- [ ] Can view placement drives on dashboard
- [ ] Can view drive details
- [ ] Can check eligibility for a drive
- [ ] Eligibility check returns results (eligible/ineligible/unknown)

---

## 🎉 You're All Set!

PlaceGuard is now running locally. You can:
- Browse placement drives
- Check eligibility with formatted, human-readable criteria
- See timeline of requirement updates
- Experience the professionally designed RIT-branded interface

Happy coding! 🚀
