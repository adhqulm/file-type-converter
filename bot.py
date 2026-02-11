# flake8: noqa

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from converter import (
    TMP_DIR,
    infer_type_from_path,
    IMAGE_INPUT_EXTS, IMAGE_OUTPUT_EXTS,
    PDF_EXT,
    DOC_INPUT_EXTS,
    TEXT_INPUT_EXTS,
    AUDIO_INPUT_EXTS, AUDIO_OUTPUT_EXTS,
    VIDEO_INPUT_EXTS, VIDEO_OUTPUT_EXTS,
    save_telegram_file_to_tmp,
    convert_image_to_image,
    convert_image_to_pdf,
    convert_pdf_to_images_zip,
    convert_pdf_to_text,
    convert_pdf_to_html,
    convert_doc_to_format,
    convert_text_with_pandoc,
    convert_audio_ffmpeg,
    convert_video_ffmpeg,
)

if getattr(sys, "frozen", False):
    _base_dir = Path(sys.executable).parent
else:
    _base_dir = Path(__file__).parent
load_dotenv(_base_dir / ".env")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

USER_LAST_FILE: dict[int, dict] = {}


def build_keyboard_for_kind(kind: str) -> InlineKeyboardMarkup | None:
    if kind == "image":
        buttons = [
            [InlineKeyboardButton("JPG", callback_data="to:.jpg"),
             InlineKeyboardButton("PNG", callback_data="to:.png"),
             InlineKeyboardButton("WEBP", callback_data="to:.webp")],
            [InlineKeyboardButton("BMP", callback_data="to:.bmp"),
             InlineKeyboardButton("TIFF", callback_data="to:.tiff"),
             InlineKeyboardButton("GIF", callback_data="to:.gif")],
            [InlineKeyboardButton("ICO", callback_data="to:.ico"),
             InlineKeyboardButton("TGA", callback_data="to:.tga"),
             InlineKeyboardButton("PPM", callback_data="to:.ppm")],
            [InlineKeyboardButton("PDF", callback_data="to:.pdf")],
        ]
    elif kind == "pdf":
        buttons = [
            [InlineKeyboardButton("PNG (ZIP)", callback_data="to:.png"),
             InlineKeyboardButton("JPG (ZIP)", callback_data="to:.jpg")],
            [InlineKeyboardButton("WEBP (ZIP)", callback_data="to:.webp")],
            [InlineKeyboardButton("TXT", callback_data="to:.txt"),
             InlineKeyboardButton("HTML", callback_data="to:.html")],
        ]
    elif kind == "doc":
        buttons = [
            [InlineKeyboardButton("PDF", callback_data="to:.pdf"),
             InlineKeyboardButton("DOCX", callback_data="to:.docx")],
            [InlineKeyboardButton("HTML", callback_data="to:.html"),
             InlineKeyboardButton("TXT", callback_data="to:.txt")],
        ]
    elif kind == "text":
        buttons = [
            [InlineKeyboardButton("TXT", callback_data="to:.txt"),
             InlineKeyboardButton("MD", callback_data="to:.md"),
             InlineKeyboardButton("HTML", callback_data="to:.html")],
            [InlineKeyboardButton("PDF", callback_data="to:.pdf"),
             InlineKeyboardButton("DOCX", callback_data="to:.docx"),
             InlineKeyboardButton("EPUB", callback_data="to:.epub")],
            [InlineKeyboardButton("RST", callback_data="to:.rst"),
             InlineKeyboardButton("LaTeX", callback_data="to:.tex"),
             InlineKeyboardButton("JSON", callback_data="to:.json")],
            [InlineKeyboardButton("XML", callback_data="to:.xml")],
        ]
    elif kind == "audio":
        buttons = [
            [InlineKeyboardButton("MP3", callback_data="to:.mp3"),
             InlineKeyboardButton("WAV", callback_data="to:.wav"),
             InlineKeyboardButton("OGG", callback_data="to:.ogg")],
            [InlineKeyboardButton("FLAC", callback_data="to:.flac"),
             InlineKeyboardButton("AAC", callback_data="to:.aac"),
             InlineKeyboardButton("M4A", callback_data="to:.m4a")],
            [InlineKeyboardButton("OPUS", callback_data="to:.opus"),
             InlineKeyboardButton("WMA", callback_data="to:.wma"),
             InlineKeyboardButton("AC3", callback_data="to:.ac3")],
            [InlineKeyboardButton("AIFF", callback_data="to:.aiff")],
        ]
    elif kind == "video":
        buttons = [
            [InlineKeyboardButton("MP4", callback_data="to:.mp4"),
             InlineKeyboardButton("WEBM", callback_data="to:.webm"),
             InlineKeyboardButton("MOV", callback_data="to:.mov")],
            [InlineKeyboardButton("MKV", callback_data="to:.mkv"),
             InlineKeyboardButton("AVI", callback_data="to:.avi"),
             InlineKeyboardButton("FLV", callback_data="to:.flv")],
            [InlineKeyboardButton("GIF", callback_data="to:.gif"),
             InlineKeyboardButton("TS", callback_data="to:.ts"),
             InlineKeyboardButton("3GP", callback_data="to:.3gp")],
            [InlineKeyboardButton("--- Extract Audio ---", callback_data="noop")],
            [InlineKeyboardButton("MP3", callback_data="to:.mp3"),
             InlineKeyboardButton("WAV", callback_data="to:.wav"),
             InlineKeyboardButton("FLAC", callback_data="to:.flac")],
            [InlineKeyboardButton("AAC", callback_data="to:.aac"),
             InlineKeyboardButton("OPUS", callback_data="to:.opus"),
             InlineKeyboardButton("OGG", callback_data="to:.ogg")],
        ]
    else:
        buttons = []
    return InlineKeyboardMarkup(buttons) if buttons else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*File Converter Bot*\n\n"
        "Send me any file and I'll convert it for you.\n\n"

        "*Images*\n"
        "JPG, PNG, WEBP, BMP, TIFF, GIF, ICO, TGA, PPM, "
        "PGM, PBM, PCX, DDS, SGI, EPS\n"
        "Convert to: JPG, PNG, WEBP, BMP, TIFF, GIF, ICO, TGA, PPM, PDF\n\n"

        "*PDFs*\n"
        "Convert to: PNG, JPG, WEBP (as ZIP), TXT, HTML\n\n"

        "*Documents*\n"
        "DOC, DOCX, ODT, RTF, PPT, PPTX, ODP, XLS, XLSX, ODS, CSV\n"
        "Convert to: PDF, DOCX, HTML, TXT\n\n"

        "*Text & Markup*\n"
        "TXT, MD, HTML, RST, TeX, JSON, XML, YAML, CSV, RTF, "
        "EPUB, ORG, AsciiDoc\n"
        "Convert to: TXT, MD, HTML, PDF, DOCX, EPUB, RST, TeX, JSON, XML\n\n"

        "*Audio*\n"
        "MP3, WAV, OGG, M4A, FLAC, AAC, WMA, AIFF, AC3, AMR, "
        "OPUS, APE, WV\n"
        "Convert to: MP3, WAV, OGG, FLAC, AAC, M4A, WMA, AIFF, OPUS, AC3\n\n"

        "*Video*\n"
        "MP4, MOV, MKV, AVI, WEBM, FLV, TS, 3GP, WMV, M4V, OGV, "
        "VOB, MTS\n"
        "Convert to: MP4, WEBM, GIF, MOV, MKV, AVI, FLV, TS, 3GP\n"
        "Extract audio: MP3, WAV, OGG, FLAC, AAC, OPUS"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        tg_file = await update.message.photo[-1].get_file()
        suffix = ".jpg"
    elif update.message.document:
        tg_file = await update.message.document.get_file()
        suffix = Path(update.message.document.file_name or "").suffix or ""
    else:
        return

    tmp_path = await save_telegram_file_to_tmp(tg_file, suffix=suffix)
    kind = infer_type_from_path(tmp_path)

    USER_LAST_FILE[update.message.from_user.id] = {
        "path": tmp_path,
        "kind": kind,
    }

    kb = build_keyboard_for_kind(kind)
    if not kb:
        await update.message.reply_text("Unsupported file type. Try another file.")
        return

    await update.message.reply_text(
        f"Received *{tmp_path.name}*.\nChoose a target format:",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def handle_conversion_choice(
        update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "noop":
        return

    user_id = query.from_user.id
    state = USER_LAST_FILE.get(user_id)
    if not state:
        await query.edit_message_text("I don't have a file from you yet. Send me one first.")
        return

    src_path: Path = state["path"]
    kind: str = state["kind"]
    target_ext = query.data.replace("to:", "").strip().lower()

    try:
        await context.bot.delete_message(chat_id=query.message.chat_id,
                                         message_id=query.message.message_id)
    except Exception:
        pass

    waiting_msg = await context.bot.send_message(
        chat_id=query.message.chat_id, text="Converting... please wait.")
    out_path = None

    try:
        if kind == "image":
            if target_ext == ".pdf":
                out_path = convert_image_to_pdf(src_path)
            else:
                out_path = convert_image_to_image(src_path, target_ext)
        elif kind == "pdf":
            if target_ext in (".png", ".jpg", ".jpeg", ".webp"):
                out_path = convert_pdf_to_images_zip(src_path, target_ext)
            elif target_ext == ".txt":
                out_path = convert_pdf_to_text(src_path)
            elif target_ext == ".html":
                out_path = convert_pdf_to_html(src_path)
            else:
                raise ValueError("Unsupported PDF conversion.")
        elif kind == "doc":
            out_path = convert_doc_to_format(src_path, target_ext)
        elif kind == "text":
            out_path = convert_text_with_pandoc(src_path, target_ext)
        elif kind == "audio":
            out_path = convert_audio_ffmpeg(src_path, target_ext)
        elif kind == "video":
            out_path = convert_video_ffmpeg(src_path, target_ext)
        else:
            raise ValueError("Unsupported source type.")

        await context.bot.delete_message(
            chat_id=waiting_msg.chat_id, message_id=waiting_msg.message_id)

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=InputFile(out_path.open("rb"), filename=out_path.name),
            caption="Conversion complete. You can send another file to convert now.",
        )

    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id,
                                       text=f"Conversion failed: {e}")

    finally:
        try:
            src_path.unlink(missing_ok=True)
            if out_path:
                out_path.unlink(missing_ok=True)
        except Exception:
            pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        raise context.error
    except Exception as e:
        print(f"Error: {e}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,
                                   handle_file))
    app.add_handler(CallbackQueryHandler(handle_conversion_choice))
    app.add_error_handler(error_handler)

    print("Bot is running... Press Ctrl+C to stop.")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
