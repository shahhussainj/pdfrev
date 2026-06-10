import os
import asyncio
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename
import uvicorn

# ── Config from environment variables ──────────────────────────────────────────
API_ID       = int(os.environ["TELEGRAM_API_ID"])
API_HASH     = os.environ["TELEGRAM_API_HASH"]
BOT_USERNAME = os.environ["TELEGRAM_BOT_USERNAME"]
SESSION_STR  = os.environ["TELEGRAM_SESSION_STRING"]

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client: TelegramClient = None

@app.on_event("startup")
async def startup():
    global client
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()
    print("✅ Telegram client connected")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

# ── Request model ──────────────────────────────────────────────────────────────
class PDFRequest(BaseModel):
    url: str

# ── Main endpoint ──────────────────────────────────────────────────────────────
@app.post("/get-pdf")
async def get_pdf(req: PDFRequest):
    url = req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Please provide a valid URL starting with http:// or https://")

    try:
        # Step 1: Send /download command to the bot
        await client.send_message(BOT_USERNAME, "/download")

        # Step 2: Wait for bot to ask for the URL and capture its message
        prompt_message = None
        for _ in range(15):
            await asyncio.sleep(1)
            messages = await client.get_messages(BOT_USERNAME, limit=5)
            for msg in messages:
                if msg.text and "url" in msg.text.lower():
                    prompt_message = msg
                    break
            if prompt_message:
                break

        if not prompt_message:
            raise HTTPException(status_code=504, detail="Bot did not ask for a URL. Try again.")

        # Step 3: Send the URL as a REPLY to the bot's prompt message
        await client.send_message(BOT_USERNAME, url, reply_to=prompt_message.id)

        # Step 4: Wait for the bot to send back a PDF (up to 60 seconds)
        pdf_message = None
        for _ in range(60):
            await asyncio.sleep(1)
            messages = await client.get_messages(BOT_USERNAME, limit=5)
            for msg in messages:
                if msg.document:
                    for attr in msg.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            if attr.file_name.endswith(".pdf"):
                                pdf_message = msg
                                break
                if pdf_message:
                    break
            if pdf_message:
                break

        if not pdf_message:
            raise HTTPException(status_code=504, detail="Timed out waiting for PDF from Telegram bot. Try again.")

        # Step 5: Download the PDF to a temp file and serve it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name

        await client.download_media(pdf_message, file=tmp_path)

        # Get a clean filename
        filename = "page.pdf"
        for attr in pdf_message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name
                break

        return FileResponse(
            path=tmp_path,
            media_type="application/pdf",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=8000)
