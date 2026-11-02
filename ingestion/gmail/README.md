# Gmail Integration Module

Automated placement email processing for PlaceGuard using Gmail API.

## Overview

This module enables PlaceGuard to automatically monitor a Gmail inbox, classify placement-related emails, and extract eligibility criteria without manual intervention.

## Features

- **OAuth 2.0 Authentication**: Secure authentication with automatic token refresh
- **Smart Email Classification**: LLM-powered classification (new_offer, offer_update, shortlist, other)
- **Automatic Criteria Extraction**: Extracts eligibility requirements from email text
- **Duplicate Prevention**: Tracks processed emails to avoid reprocessing
- **Gmail Label Management**: Automatically labels processed emails
- **Background Polling**: Configurable automatic email checking
- **Manual Sync**: On-demand email synchronization via API

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Gmail Inbox (Placement Officer)                             │
└────────────────┬────────────────────────────────────────────┘
                 │ OAuth 2.0
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ GmailAdapter                                                 │
│ - Fetch emails from placement officer                       │
│ - Parse HTML/plain text                                     │
│ - Convert to RawMessage                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ EmailClassifier (LLM)                                        │
│ - new_offer: New placement opportunity                      │
│ - offer_update: Changes to existing placement               │
│ - shortlist: Not relevant (ignore)                          │
│ - other: Not relevant (ignore)                              │
└────────────────┬────────────────────────────────────────────┘
                 │ Only process relevant emails
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Extraction Pipeline                                          │
│ - Extract company/drive information                         │
│ - Extract eligibility criteria                              │
│ - Store facts in database                                   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Post-Processing                                              │
│ - Add "PlaceGuard/Processed" label                          │
│ - Record in processed_emails table                          │
│ - Run reconciliation                                        │
└─────────────────────────────────────────────────────────────┘
```

## Module Structure

```
ingestion/gmail/
├── __init__.py              # Module exports
├── README.md                # This file
├── adapter.py               # Gmail API integration (SourceAdapter impl)
├── auth.py                  # OAuth 2.0 authentication
├── classifier.py            # LLM email classification
├── errors.py                # Custom exception classes
├── polling_service.py       # Background polling service
└── utils.py                 # Email parsing utilities
```

## Quick Start

### 1. Setup Gmail API

Follow the detailed guide: [docs/GMAIL_SETUP.md](../../docs/GMAIL_SETUP.md)

Summary:
1. Create Google Cloud Project
2. Enable Gmail API
3. Configure OAuth consent screen
4. Create OAuth credentials
5. Download `credentials.json`

### 2. Configure Environment

Edit `.env`:
```bash
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
PLACEMENT_OFFICER_EMAIL=tpo@yourcollege.edu
GMAIL_POLLING_ENABLED=true
GMAIL_POLLING_INTERVAL_MINUTES=60
```

### 3. Start PlaceGuard

```bash
uvicorn api.main:app --reload
```

### 4. First-Time Authentication

```bash
# Trigger OAuth flow
curl -X POST http://localhost:8000/ingest/sync-gmail

# Browser will open for authentication
# Complete OAuth consent
# token.json will be created automatically
```

### 5. Verify

```bash
# Check polling status
curl http://localhost:8000/ingest/gmail-polling-status

# Should show:
# {
#   "enabled": true,
#   "running": true,
#   "last_poll_time": "2024-11-02T10:30:00",
#   ...
# }
```

## Usage

### Automatic Mode (Recommended)

Background polling runs automatically when enabled:
- Polls Gmail every hour (configurable)
- Processes new emails automatically
- No manual intervention required

**Configuration:**
```bash
GMAIL_POLLING_ENABLED=true
GMAIL_POLLING_INTERVAL_MINUTES=60  # Check every hour
```

**Monitoring:**
```bash
# Check status
curl http://localhost:8000/ingest/gmail-polling-status

# View recent processed emails
sqlite3 placeguard_dev.db "SELECT * FROM processed_emails ORDER BY processed_at DESC LIMIT 5;"
```

### Manual Mode

Trigger email sync on-demand:

```bash
# Sync only unread emails
curl -X POST http://localhost:8000/ingest/sync-gmail

# Sync all emails (including read)
curl -X POST "http://localhost:8000/ingest/sync-gmail?only_unread=false"

# Response:
# {
#   "success": true,
#   "emails_fetched": 10,
#   "emails_processed": 3,
#   "emails_skipped": 7,
#   "facts_extracted": 12,
#   "drives_affected": ["DRIVE_AMAZON", "DRIVE_GOOGLE"],
#   ...
# }
```

### Python API

Use the module programmatically:

```python
from ingestion.gmail.adapter import GmailAdapter
from ingestion.gmail.classifier import EmailClassifier
from extraction.llm_client import get_llm_client

# Fetch emails
adapter = GmailAdapter()
messages = adapter.fetch(only_unread=True)

# Classify emails
llm = get_llm_client()
classifier = EmailClassifier(llm)

for msg in messages:
    classification = classifier.classify(msg)
    print(f"{msg.message_id}: {classification.category}")
    
    if classifier.is_relevant(classification):
        print(f"  Drive: {classification.drive_id}")
        print(f"  Company: {classification.company_name}")
```

## API Endpoints

### POST /ingest/sync-gmail

Manually sync Gmail emails.

**Parameters:**
- `only_unread` (bool, optional): Only fetch unread emails (default: true)

**Response:**
```json
{
  "success": true,
  "emails_fetched": 10,
  "emails_classified": 10,
  "emails_processed": 3,
  "emails_skipped": 7,
  "facts_extracted": 12,
  "drives_affected": ["DRIVE_AMAZON"],
  "details": [...],
  "errors": []
}
```

### GET /ingest/gmail-polling-status

Get polling service status.

**Response:**
```json
{
  "enabled": true,
  "running": true,
  "polling_interval_minutes": 60,
  "last_poll_time": "2024-11-02T10:30:00",
  "last_poll_status": "success",
  "total_polls": 120,
  "successful_polls": 118,
  "failed_polls": 2,
  "last_error": null
}
```

### POST /ingest/trigger-gmail-poll

Manually trigger a poll (doesn't affect schedule).

**Response:**
```json
{
  "success": true,
  "message": "Manual poll completed successfully",
  "timestamp": "2024-11-02T10:35:00"
}
```

## Email Classification

The LLM classifies emails into 4 categories:

### new_offer
New placement opportunity announcement.

**Examples:**
- "Amazon is hiring for SDE role"
- "Google placement drive - Apply now"
- "Microsoft campus recruitment 2024"

**Processing:** Extracts criteria and creates new drive

### offer_update
Update to existing placement.

**Examples:**
- "Updated CGPA requirement for TCS: 7.5 → 7.0"
- "Deadline extended for Wipro till 6PM"
- "Correction: No prior offer restriction removed"

**Processing:** Extracts updated criteria, marks as correction

### shortlist
Shortlist announcement (not eligibility-related).

**Examples:**
- "Shortlisted students for Infosys interview"
- "Selected candidates for Cognizant"

**Processing:** Marked as processed, but ignored

### other
Irrelevant emails.

**Examples:**
- "Reminder: Update your resume"
- "Workshop on interview skills"
- "General announcement"

**Processing:** Marked as processed, but ignored

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GMAIL_CREDENTIALS_PATH` | `credentials.json` | Path to OAuth credentials |
| `GMAIL_TOKEN_PATH` | `token.json` | Path to store access tokens |
| `PLACEMENT_OFFICER_EMAIL` | Required | Email to filter by |
| `GMAIL_POLLING_ENABLED` | `true` | Enable background polling |
| `GMAIL_POLLING_INTERVAL_MINUTES` | `60` | Polling frequency |
| `GMAIL_PROCESSED_LABEL` | `PlaceGuard/Processed` | Label for processed emails |

### Adapter Configuration

```python
adapter = GmailAdapter(
    placement_officer_email="tpo@college.edu",  # Filter by sender
    max_results=100,                            # Max emails per fetch
    days_back=7,                                # How far back to search
)
```

### Classifier Configuration

```python
classifier = EmailClassifier(
    llm_client=llm,
    confidence_threshold=0.7,  # Min confidence to process (0.0-1.0)
)
```

## Troubleshooting

See detailed troubleshooting guide: [docs/GMAIL_TROUBLESHOOTING.md](../../docs/GMAIL_TROUBLESHOOTING.md)

### Common Issues

**Authentication Failed:**
```bash
rm token.json
curl -X POST http://localhost:8000/ingest/sync-gmail
```

**No Emails Fetched:**
- Check `PLACEMENT_OFFICER_EMAIL` is correct
- Verify using correct Gmail account
- Try `only_unread=false`

**Polling Not Running:**
- Check `GMAIL_POLLING_ENABLED=true`
- Verify API server started successfully
- Check logs for errors

## Security

### OAuth Scopes Required

- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/gmail.modify` - Add labels

### Protected Files

Never commit these files to version control:
- `credentials.json` - OAuth client credentials
- `token.json` - Access/refresh tokens
- `.env` - Configuration with email address

They are already in `.gitignore`.

### Best Practices

1. **Use dedicated Gmail account** for placement monitoring
2. **Restrict OAuth permissions** to only required scopes
3. **Regularly review** Google Account permissions
4. **Monitor API quota** usage
5. **Enable 2FA** on Gmail account
6. **Backup credentials** securely

## Performance

### API Quota Usage

Gmail API free tier: **1 billion units/day**

Operations:
- Read message: 5 units
- List messages: 5 units
- Modify labels: 5 units

Example usage (hourly polling, 50 emails):
- 24 polls/day × 50 emails × 15 units = **18,000 units/day**
- **0.002% of quota** ✅

### Optimization Tips

1. **Increase polling interval** if processing many emails
2. **Reduce `max_results`** to fetch fewer emails per sync
3. **Use `only_unread=true`** to skip already processed emails
4. **Enable `ProcessedEmail` tracking** (already implemented)

## Testing

### Manual Testing

```bash
# Test authentication
python -c "from ingestion.gmail.auth import GmailAuthenticator; GmailAuthenticator().get_gmail_service(); print('OK')"

# Test email fetching
python -c "from ingestion.gmail.adapter import GmailAdapter; print(f'{len(GmailAdapter().fetch())} emails')"

# Test classification
python -c "from ingestion.gmail.classifier import EmailClassifier; from extraction.llm_client import get_llm_client; print('OK')"
```

### Integration Testing

```bash
# Trigger manual sync with verbose output
curl -X POST http://localhost:8000/ingest/sync-gmail | python -m json.tool

# Check processed emails in database
sqlite3 placeguard_dev.db "SELECT COUNT(*) FROM processed_emails;"
```

## Development

### Adding New Classification Categories

Edit `classifier.py`:
```python
# Add new category to classification prompt
# Update EmailClassification validation
# Update is_relevant() logic
```

### Custom Email Parsing

Edit `utils.py`:
```python
def parse_email_body(payload: dict) -> str:
    # Add custom parsing logic
    # Handle special email formats
    pass
```

### Error Handling

Use custom exceptions from `errors.py`:
```python
from ingestion.gmail.errors import GmailAPIError, handle_gmail_api_error

try:
    # Gmail API call
except Exception as e:
    raise handle_gmail_api_error(e)
```

## Support

- **Setup Issues**: See [GMAIL_SETUP.md](../../docs/GMAIL_SETUP.md)
- **Runtime Issues**: See [GMAIL_TROUBLESHOOTING.md](../../docs/GMAIL_TROUBLESHOOTING.md)
- **API Documentation**: [Gmail API Docs](https://developers.google.com/gmail/api)

## License

Part of PlaceGuard placement eligibility management system.
