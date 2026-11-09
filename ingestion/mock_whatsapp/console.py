"""Mock WhatsApp Console (README.md 9.1).

A small FastAPI app that lets you play Placement Cell / coordinator / student and post
timestamped messages, so the reconciliation and rule engine can be exercised end-to-end
without touching a real WhatsApp group.

Run with:
    uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001
"""

from __future__ import annotations

import sys
from pathlib import Path

# Windows consoles often default to a legacy codepage that can't encode the
# emoji used in this module's print()s below; force UTF-8 so this runs anywhere.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
from fastapi import FastAPI, Form, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from core.schemas import SenderRole
from ingestion.mock_whatsapp import store

app = FastAPI(title="Mock WhatsApp Console")

# Configuration for automatic processing
AUTO_PROCESS_ENABLED = True
API_URL = "http://localhost:8000"


def _render_page() -> str:
    rows = "".join(
        f"<tr>"
        f"<td>{m.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>"
        f"<td>{m.sender_role.value}</td>"
        f"<td>{m.sender_id}</td>"
        f"<td>{'yes' if m.is_forwarded else 'no'}</td>"
        f"<td>{m.body}</td>"
        f"<td>{f'<img src=\"/media/{m.image_id}\" style=\"max-height:80px;max-width:140px\">' if m.image_id else ''}</td>"
        f"</tr>"
        for m in reversed(store.get_all())
    )

    return f"""
    <html>
    <head>
      <title>Mock WhatsApp Console</title>
      <style>
        body {{ font-family: sans-serif; max-width: 900px; margin: 2rem auto; }}
        .success {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 12px; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #f5f5f5; text-align: left; padding: 8px; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
      </style>
    </head>
    <body>
      <h2>📱 Mock WhatsApp Console</h2>
      <p>Post a message as Placement Cell, Coordinator, or Student. Messages are automatically 
         processed and added to timelines in the background.</p>

      <div class="success">
        <strong>✅ Automatic Processing Enabled</strong><br>
        Messages are automatically processed when posted. Timeline updates happen in the background!<br>
        View timelines at <a href="http://localhost:3000" target="_blank">http://localhost:3000</a>
      </div>

      <form action="/post" method="post" enctype="multipart/form-data" style="margin: 2rem 0;">
        <div style="margin-bottom: 1rem;">
          <label><strong>Sender role:</strong>
            <select name="sender_role" style="margin-left: 10px; padding: 5px;">
              <option value="placement_cell">Placement Cell</option>
              <option value="coordinator">Coordinator</option>
              <option value="student">Student</option>
            </select>
          </label>
        </div>

        <div style="margin-bottom: 1rem;">
          <label><strong>Sender id:</strong>
            <input type="text" name="sender_id" value="demo_sender" required style="margin-left: 10px; padding: 5px; width: 200px;">
          </label>
        </div>

        <div style="margin-bottom: 1rem;">
          <label>
            <input type="checkbox" name="is_forwarded" value="true">
            Forwarded message
          </label>
        </div>

        <div style="margin-bottom: 1rem;">
          <label><strong>Message body (optional if attaching an image):</strong><br>
            <textarea name="body" rows="4" cols="60"
              placeholder="Example: Tech Mahindra minimum CGPA changed to 6.5"
              style="margin-top: 5px; padding: 8px; font-family: sans-serif;"></textarea>
          </label>
        </div>

        <div style="margin-bottom: 1rem;">
          <label><strong>Attach image (e.g. a screenshot of an email/message):</strong><br>
            <input type="file" name="image" accept="image/*" style="margin-top: 5px;">
          </label>
        </div>

        <button type="submit" style="background: #4caf50; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">
          📤 Post Message
        </button>
      </form>

      <h3>📋 Message History (newest first)</h3>
      <table border="1" cellpadding="8" cellspacing="0">
        <tr>
          <th>Timestamp</th>
          <th>Role</th>
          <th>Sender</th>
          <th>Forwarded</th>
          <th>Body</th>
          <th>Image</th>
        </tr>
        {rows}
      </table>
      
      <div style="margin-top: 20px; padding: 12px; background: #f5f5f5; border-radius: 4px;">
        <small>
          💡 <strong>Tip:</strong> Messages are automatically processed using LLM (takes 2-5 seconds). 
          Criteria are extracted and timelines are updated in the background.
        </small>
      </div>
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
def view_console() -> str:
    return _render_page()


async def trigger_processing_in_background():
    """Trigger message processing in the background after a message is posted."""
    if not AUTO_PROCESS_ENABLED:
        return
    
    print("🔄 Starting automatic processing...")
    
    try:
        # Use async HTTP client
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{API_URL}/ingest/process-whatsapp")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Auto-processing complete: {result['messages_processed']} messages, {result['total_facts_extracted']} facts extracted")
                if result['drives_updated']:
                    print(f"   Drives updated: {', '.join(result['drives_updated'])}")
            else:
                print(f"⚠️  Auto-processing failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
    
    except httpx.ConnectError:
        print(f"⚠️  Could not connect to API at {API_URL} for auto-processing")
        print(f"   Make sure the API server is running!")
    except Exception as e:
        print(f"⚠️  Auto-processing error: {type(e).__name__}: {e}")


@app.post("/post")
async def post_message(
    background_tasks: BackgroundTasks,
    sender_role: str = Form(...),
    sender_id: str = Form(...),
    body: str = Form(""),
    is_forwarded: str | None = Form(None),
    image: UploadFile | None = File(None),
) -> RedirectResponse:
    image_bytes: bytes | None = None
    image_ext = ".png"
    if image is not None and image.filename:
        image_bytes = await image.read()
        if image_bytes:
            image_ext = Path(image.filename).suffix or ".png"

    if not body.strip() and not image_bytes:
        raise HTTPException(status_code=400, detail="Provide a message body, an image, or both.")

    # Store the message
    message = store.add_message(
        sender_id=sender_id,
        sender_role=SenderRole(sender_role),
        body=body,
        is_forwarded=is_forwarded is not None,
        image_bytes=image_bytes,
        image_ext=image_ext,
    )

    print(f"📱 New message posted: {body[:60]}...{' [+image]' if image_bytes else ''}")

    # Trigger automatic processing in the background
    if AUTO_PROCESS_ENABLED:
        background_tasks.add_task(trigger_processing_in_background)
        print(f"   🔄 Auto-processing queued for message {message.message_id[:8]}")

    return RedirectResponse(url="/", status_code=303)


@app.get("/messages")
def list_messages() -> list[dict]:
    """JSON view of the current message log — useful for the extraction stage to poll later."""
    return [m.model_dump(mode="json") for m in store.get_all()]


@app.get("/media/{image_id}")
def get_media(image_id: str) -> FileResponse:
    """Serve an uploaded image by id — polled by the main API to run OCR on it."""
    if "/" in image_id or "\\" in image_id or ".." in image_id:
        raise HTTPException(status_code=400, detail="Invalid image id")
    path = store.get_image_path(image_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)
