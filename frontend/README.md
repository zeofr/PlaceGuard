# PlaceGuard — Frontend

Next.js 14 + Tailwind CSS student portal.

## Setup

```bash
cd frontend
npm install
npm run dev        # starts on http://localhost:3000
```

The API backend must be running on port 8000:
```bash
# from project root
pip install -r requirements.txt
python data/load_synthetic_data.py   # seed the database
uvicorn api.main:app --reload --port 8000
```

## Pages

| Route | Description |
|---|---|
| `/` | Redirects to `/login` or `/dashboard` |
| `/login` | USN + date of birth login |
| `/dashboard` | List of all placement drives |
| `/drive/[driveId]` | Drive detail — timeline + eligibility check |

## Test credentials

After running `load_synthetic_data.py`:

| USN | Date of Birth | Name |
|---|---|---|
| 1MS22CS042 | 2003-04-15 | Arjun Mehta |
| 1MS22IS017 | 2003-08-22 | Priya Sharma |
| 1MS22CS008 | 2003-02-28 | Sneha Patel |
