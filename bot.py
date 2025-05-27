import os
import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pydub import AudioSegment
from pydub.silence import split_on_silence
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)

# إعداد Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']
creds_dict = json.loads(os.environ['GOOGLE_CREDS_JSON'])
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل لي مقطع صوتي وسأقسّمه تلقائيًا حسب أول pause.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    file = await (message.voice or message.audio).get_file()
    await file.download_to_drive("input.ogg")

    sound = AudioSegment.from_file("input.ogg")
    
    # اكتشاف أول pause
    chunks = split_on_silence(sound, min_silence_len=700, silence_thresh=sound.dBFS-16, keep_silence=300)
    if not chunks:
        await update.message.reply_text("مفيش pause كفاية للتقسيم. حاول بمقطع أطول أو أوضح.")
        return

    # حدد طول أول مقطع كمرجع
    first_chunk = chunks[0]
    chunk_duration = len(first_chunk)

    parts = []
    for i in range(0, len(sound), chunk_duration):
        part = sound[i:i+chunk_duration]
        part_path = f"chunk_{i//chunk_duration}.mp3"
        part.export(part_path, format="mp3")
        parts.append(part_path)

    # رفع كل مقطع على Google Drive
    links = []
    for path in parts:
        metadata = {'name': os.path.basename(path)}
        media = MediaFileUpload(path, mimetype='audio/mpeg')
        uploaded = drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
        file_id = uploaded.get('id')
        link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        links.append(link)

    reply = "\n".join(f"📥 Part {i+1}: {link}" for i, link in enumerate(links))
    await update.message.reply_text(f"تم التقسيم والرفع:\n\n{reply}")

def main():
    app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.run_polling()

if __name__ == "__main__":
    main()
