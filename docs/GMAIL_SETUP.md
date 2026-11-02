# Gmail API Setup Guide for PlaceGuard

This guide walks you through setting up Gmail API access for PlaceGuard's automatic placement email processing feature.

## Overview

PlaceGuard uses the Gmail API to:
- Monitor your placement officer's inbox for new placement emails
- Automatically classify and process placement notices
- Extract eligibility criteria using LLM
- Track processed emails to avoid duplicates

## Prerequisites

- A Google account with access to the placement officer's Gmail
- Python 3.9+ with required packages (see `requirements.txt`)
- PlaceGuard backend running

## Setup Steps

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Enter project details:
   - **Project name**: `PlaceGuard` (or any name you prefer)
   - **Organization**: Leave as default or select your organization
4. Click **"Create"**
5. Wait for project creation (usually takes a few seconds)
6. Select your newly created project from the project selector

### 2. Enable Gmail API

1. In the Google Cloud Console, navigate to **"APIs & Services"** → **"Library"**
   - Or use this direct link: https://console.cloud.google.com/apis/library
2. Search for **"Gmail API"**
3. Click on **"Gmail API"** in the search results
4. Click **"Enable"**
5. Wait for the API to be enabled (usually instant)

### 3. Configure OAuth Consent Screen

1. Navigate to **"APIs & Services"** → **"OAuth consent screen"**
   - Direct link: https://console.cloud.google.com/apis/credentials/consent
2. Choose user type:
   - **Internal**: If you're using a Google Workspace account (college domain)
   - **External**: If using personal Gmail account
3. Click **"Create"**

#### Fill in App Information:
- **App name**: `PlaceGuard Email Integration`
- **User support email**: Your email address
- **App logo**: (Optional) Upload PlaceGuard logo
- **Developer contact information**: Your email address

4. Click **"Save and Continue"**

#### Add Scopes:
5. Click **"Add or Remove Scopes"**
6. Filter or search for these scopes and add them:
   - `https://www.googleapis.com/auth/gmail.readonly` - Read email messages
   - `https://www.googleapis.com/auth/gmail.modify` - Add labels to messages
7. Click **"Update"** then **"Save and Continue"**

#### Add Test Users (for External apps):
8. If you selected "External" user type:
   - Click **"Add Users"**
   - Add the Gmail address you'll use for monitoring placement emails
   - Click **"Add"** then **"Save and Continue"**
9. Click **"Back to Dashboard"**

### 4. Create OAuth 2.0 Credentials

1. Navigate to **"APIs & Services"** → **"Credentials"**
   - Direct link: https://console.cloud.google.com/apis/credentials
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. Configure the OAuth client:
   - **Application type**: Select **"Desktop app"**
   - **Name**: `PlaceGuard Desktop Client`
4. Click **"Create"**
5. A dialog will appear with your client ID and client secret
6. Click **"Download JSON"**
7. Save the downloaded file

### 5. Set Up Credentials in PlaceGuard

1. **Rename the downloaded file** to `credentials.json`
2. **Move it to your PlaceGuard project root directory**:
   ```
   PlaceGuard/
   ├── credentials.json  ← Place the file here
   ├── .env
   ├── api/
   ├── database/
   └── ...
   ```

3. **Update your `.env` file** with Gmail configuration:
   ```bash
   # Gmail API Integration
   GMAIL_CREDENTIALS_PATH=credentials.json
   GMAIL_TOKEN_PATH=token.json
   PLACEMENT_OFFICER_EMAIL=tpo@yourcollege.edu
   GMAIL_POLLING_ENABLED=true
   GMAIL_POLLING_INTERVAL_MINUTES=60
   GMAIL_PROCESSED_LABEL=PlaceGuard/Processed
   ```

4. **Important**: Replace `tpo@yourcollege.edu` with the actual email address of your placement officer

### 6. First-Time Authentication

The first time PlaceGuard accesses Gmail, you'll need to complete an OAuth authorization flow:

1. **Start the PlaceGuard backend**:
   ```bash
   cd PlaceGuard
   uvicorn api.main:app --reload
   ```

2. **Trigger the authentication** by making a request to sync Gmail:
   ```bash
   curl -X POST http://localhost:8000/ingest/sync-gmail
   ```

3. **Complete OAuth flow**:
   - Your default browser will open automatically
   - You may see a warning: **"Google hasn't verified this app"**
     - Click **"Advanced"** → **"Go to PlaceGuard Email Integration (unsafe)"**
     - This warning appears because your app is in testing mode — it's safe to proceed
   - Select the Google account you want to use
   - Review the permissions:
     - Read your email messages
     - Manage labels on your email
   - Click **"Allow"**

4. **Success!** 
   - The browser will show: "The authentication flow has completed."
   - A `token.json` file will be created in your project root
   - PlaceGuard can now access Gmail automatically

### 7. Verify Setup

Test that Gmail integration is working:

```bash
# Check if authentication worked
curl -X POST http://localhost:8000/ingest/sync-gmail
```

Expected response:
```json
{
  "success": true,
  "emails_fetched": 5,
  "emails_classified": 5,
  "emails_processed": 2,
  "facts_extracted": 8,
  "drives_affected": ["DRIVE_TECHM", "DRIVE_WIPRO"]
}
```

## File Structure After Setup

```
PlaceGuard/
├── credentials.json       ← OAuth client credentials (from Google Cloud)
├── token.json            ← OAuth access/refresh tokens (auto-generated)
├── .env                  ← Contains PLACEMENT_OFFICER_EMAIL and other config
└── ...
```

## Security Notes

### Important Files to Protect:

1. **`credentials.json`**: Contains your OAuth client ID and secret
   - ✅ Already in `.gitignore`
   - ⚠️ Never commit to version control
   - ⚠️ Never share publicly

2. **`token.json`**: Contains access and refresh tokens for your Gmail account
   - ✅ Already in `.gitignore`
   - ⚠️ Never commit to version control
   - ⚠️ Anyone with this file can access your Gmail

3. **`.env`**: Contains sensitive configuration
   - ✅ Already in `.gitignore`
   - ⚠️ Never commit to version control

### Best Practices:

- **Use a dedicated Gmail account** for placement email monitoring (recommended)
- **Restrict access** to `credentials.json` and `token.json` files
- **Regularly review** OAuth access in [Google Account Security](https://myaccount.google.com/permissions)
- **Revoke access** if compromised: Delete `token.json` and revoke from Google Account settings

## Troubleshooting

### "invalid_grant" Error

**Problem**: Token has expired or been revoked

**Solution**: Delete `token.json` and re-authenticate:
```bash
rm token.json
curl -X POST http://localhost:8000/ingest/sync-gmail
# Follow the browser authentication flow again
```

### "Credentials file not found"

**Problem**: `credentials.json` is missing or in wrong location

**Solution**: 
1. Verify `credentials.json` is in the project root
2. Check that `GMAIL_CREDENTIALS_PATH` in `.env` matches the file location
3. Re-download from Google Cloud Console if lost

### "API has not been used in project"

**Problem**: Gmail API is not enabled

**Solution**: Go to [Google Cloud Console](https://console.cloud.google.com/apis/library) and enable Gmail API

### "Access blocked: This app's request is invalid"

**Problem**: OAuth consent screen is not properly configured

**Solution**: 
1. Go to OAuth consent screen in Google Cloud Console
2. Ensure required scopes are added
3. Add your email as a test user (for External apps)

### "No emails found"

**Problem**: No emails from placement officer in inbox

**Solution**:
1. Verify `PLACEMENT_OFFICER_EMAIL` in `.env` is correct
2. Check that placement officer has sent emails
3. Verify you're using the correct Gmail account
4. Check the account has unread emails from the placement officer

### Rate Limit Exceeded

**Problem**: Too many API calls to Gmail

**Solution**:
- Free tier: 1 billion quota units/day (very generous)
- Reading emails = 5 units each
- If exceeded, wait until quota resets (daily)
- Consider increasing `GMAIL_POLLING_INTERVAL_MINUTES`

## Gmail API Quotas

Gmail API has generous free tier limits:

| Operation | Cost (units) | Daily Limit |
|-----------|-------------|-------------|
| Read message | 5 units | ~200 million emails/day |
| List messages | 5 units | ~200 million calls/day |
| Modify labels | 5 units | ~200 million calls/day |
| **Total** | - | **1 billion units/day** |

With hourly polling (24 times/day) and ~50 emails per poll:
- Daily usage: 24 × 50 × 15 = **18,000 units** (~0.002% of quota)
- You're well within free tier limits! 🎉

## Optional: Publishing the App

If you want to remove the "unverified app" warning:

1. Complete [OAuth verification process](https://support.google.com/cloud/answer/9110914)
2. This requires:
   - Privacy policy URL
   - Terms of service URL
   - App homepage
   - Security assessment (for sensitive scopes)
3. Review time: 4-6 weeks

**Note**: Verification is NOT required for personal use or Internal (Workspace) apps.

## Next Steps

Once Gmail integration is working:

1. ✅ Emails will be polled automatically every hour (configurable)
2. ✅ Relevant emails will be classified using LLM
3. ✅ Eligibility criteria will be extracted and stored
4. ✅ Processed emails will be labeled "PlaceGuard/Processed"
5. ✅ Students will see updated eligibility in the dashboard

## Support

If you encounter issues not covered here:

1. Check application logs: `tail -f placeguard.log`
2. Review [Gmail API documentation](https://developers.google.com/gmail/api)
3. Test with a simple Gmail API script to isolate issues
4. Verify OAuth scopes in Google Cloud Console match requirements

## References

- [Gmail API Overview](https://developers.google.com/gmail/api/guides)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Gmail API Quotas](https://developers.google.com/gmail/api/reference/quota)
- [Google Cloud Console](https://console.cloud.google.com/)
