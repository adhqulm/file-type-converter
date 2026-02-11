# flake8: noqa

from pathlib import Path
from PIL import Image
import fitz
import zipfile
import uuid
import subprocess
import shutil

TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)

# =====================================================================
#  Supported extensions
# =====================================================================

# --- Images (Pillow) ---
IMAGE_INPUT_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
    ".gif", ".ico", ".tga", ".ppm", ".pgm", ".pbm", ".pcx",
    ".dds", ".sgi", ".eps",
}
IMAGE_OUTPUT_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff",
    ".gif", ".ico", ".tga", ".ppm",
}

# --- PDF ---
PDF_EXT = ".pdf"

# --- Office docs (LibreOffice) ---
DOC_INPUT_EXTS = {
    ".doc", ".docx", ".odt", ".rtf",
    ".ppt", ".pptx", ".odp",
    ".xls", ".xlsx", ".ods", ".csv",
}
DOC_OUTPUT_EXTS = {".pdf", ".docx", ".html", ".txt"}

# --- Text / markup (Pandoc) ---
TEXT_INPUT_EXTS = {
    ".txt", ".md", ".markdown", ".html", ".htm",
    ".rst", ".tex", ".latex", ".json", ".xml",
    ".yaml", ".yml", ".csv", ".rtf", ".epub",
    ".org", ".adoc", ".asciidoc",
}
TEXT_OUTPUT_EXTS = {
    ".txt", ".md", ".html", ".pdf",
    ".rst", ".tex", ".epub", ".docx",
    ".json", ".xml",
}

# --- Audio (FFmpeg) ---
AUDIO_INPUT_EXTS = {
    ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac",
    ".wma", ".aiff", ".aif", ".ac3", ".amr", ".opus",
    ".ape", ".wv", ".alac",
}
AUDIO_OUTPUT_EXTS = {
    ".mp3", ".wav", ".ogg", ".flac",
    ".aac", ".m4a", ".wma", ".aiff", ".opus", ".ac3",
}

# --- Video (FFmpeg) ---
VIDEO_INPUT_EXTS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".flv", ".ts", ".3gp", ".wmv", ".m4v", ".ogv",
    ".vob", ".mts", ".m2ts",
}
VIDEO_OUTPUT_EXTS = {
    ".mp4", ".webm", ".gif", ".mov", ".mkv",
    ".avi", ".flv", ".ts", ".3gp",
}


# =====================================================================
#  Helpers
# =====================================================================

def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    return "".join(c for c in stem if c.isalnum() or c in ("-", "_")) or "file"


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="ignore") or "Command failed")


def _which_or_raise(bin_name: str, display: str):
    from shutil import which
    if which(bin_name) is None:
        raise RuntimeError(f"{display} is required but not found on PATH.")


async def save_telegram_file_to_tmp(tg_file, suffix: str = "") -> Path:
    out = TMP_DIR / f"{uuid.uuid4().hex}{suffix}"
    await tg_file.download_to_drive(out)
    return out


# =====================================================================
#  Image conversions (Pillow)
# =====================================================================

def convert_image_to_image(src_path: Path, target_ext: str) -> Path:
    im = Image.open(src_path)
    target_ext = target_ext.lower()
    if target_ext not in IMAGE_OUTPUT_EXTS:
        raise ValueError("Unsupported image target format.")
    out_path = TMP_DIR / f"{_safe_stem(src_path.name)}{target_ext}"
    if target_ext == ".ico":
        # ICO needs specific sizes
        im = im.convert("RGBA")
        sizes = [(256, 256)]
        im.save(out_path, format="ICO", sizes=sizes)
    elif target_ext in (".jpg", ".jpeg"):
        im.convert("RGB").save(out_path, "JPEG", quality=95)
    elif target_ext == ".png":
        im.save(out_path, "PNG")
    elif target_ext == ".webp":
        im.save(out_path, "WEBP", quality=95)
    elif target_ext == ".bmp":
        im.convert("RGB").save(out_path, "BMP")
    elif target_ext in (".tiff", ".tif"):
        im.save(out_path, "TIFF")
    elif target_ext == ".gif":
        im.convert("RGBA").save(out_path, "GIF")
    elif target_ext == ".tga":
        im.save(out_path, "TGA")
    elif target_ext == ".ppm":
        im.convert("RGB").save(out_path, "PPM")
    else:
        im.convert("RGB").save(out_path)
    return out_path


def convert_image_to_pdf(src_path: Path) -> Path:
    im = Image.open(src_path)
    out_path = TMP_DIR / f"{_safe_stem(src_path.name)}.pdf"
    im_converted = im.convert("RGB")
    im_converted.save(out_path, "PDF", resolution=100.0)
    return out_path


# =====================================================================
#  PDF conversions (PyMuPDF)
# =====================================================================

def convert_pdf_to_images_zip(src_path: Path, target_img_ext: str) -> Path:
    target_img_ext = target_img_ext.lower()
    if target_img_ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Only .png, .jpg, or .webp are supported for PDF pages.")
    doc = fitz.open(src_path)
    tmp_dir = TMP_DIR / uuid.uuid4().hex
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=200)
        if target_img_ext == ".webp":
            # Save as PNG first, then convert with Pillow
            png_path = tmp_dir / f"page_{i+1:03d}.png"
            pix.save(png_path)
            im = Image.open(png_path)
            out_img = tmp_dir / f"page_{i+1:03d}.webp"
            im.save(out_img, "WEBP", quality=90)
            png_path.unlink()
        else:
            out_img = tmp_dir / f"page_{i+1:03d}{target_img_ext}"
            pix.save(out_img)
    zip_out = TMP_DIR / f"{_safe_stem(src_path.name)}_pages.zip"
    with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(tmp_dir.iterdir()):
            z.write(p, arcname=p.name)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return zip_out


def convert_pdf_to_text(src_path: Path) -> Path:
    doc = fitz.open(src_path)
    text = ""
    for page in doc:
        text += page.get_text()
        text += "\n"
    out = TMP_DIR / f"{_safe_stem(src_path.name)}.txt"
    out.write_text(text, encoding="utf-8")
    return out


def convert_pdf_to_html(src_path: Path) -> Path:
    doc = fitz.open(src_path)
    html_parts = ["<html><body>"]
    for i, page in enumerate(doc):
        html_parts.append(f"<h2>Page {i+1}</h2>")
        html_parts.append(f"<pre>{page.get_text()}</pre>")
    html_parts.append("</body></html>")
    out = TMP_DIR / f"{_safe_stem(src_path.name)}.html"
    out.write_text("\n".join(html_parts), encoding="utf-8")
    return out


# =====================================================================
#  Office docs (LibreOffice headless)
# =====================================================================

def convert_doc_to_format(src_path: Path, target_ext: str) -> Path:
    _which_or_raise("libreoffice", "LibreOffice")
    target_ext = target_ext.lower().lstrip(".")
    out = TMP_DIR / f"{_safe_stem(src_path.name)}.{target_ext}"
    cmd = [
        "libreoffice", "--headless", "--convert-to", target_ext,
        "--outdir", str(TMP_DIR), str(src_path)
    ]
    _run(cmd)
    if out.exists():
        return out
    produced = list(TMP_DIR.glob(f"{Path(src_path).stem}.{target_ext}"))
    if not produced:
        raise RuntimeError(f"Failed to locate converted .{target_ext} file.")
    return produced[0]


# Keep old name as alias
def convert_doc_to_pdf(src_path: Path) -> Path:
    return convert_doc_to_format(src_path, "pdf")


# =====================================================================
#  Text / markup (Pandoc)
# =====================================================================

def convert_text_with_pandoc(src_path: Path, target_ext: str) -> Path:
    _which_or_raise("pandoc", "Pandoc")
    target_ext = target_ext.lower()
    if target_ext not in TEXT_OUTPUT_EXTS:
        raise ValueError("Unsupported text target format.")
    out = TMP_DIR / f"{_safe_stem(src_path.name)}{target_ext}"
    cmd = ["pandoc", str(src_path), "-o", str(out), "--standalone"]
    _run(cmd)
    return out


# =====================================================================
#  Audio (FFmpeg)
# =====================================================================

def convert_audio_ffmpeg(src_path: Path, target_ext: str) -> Path:
    _which_or_raise("ffmpeg", "FFmpeg")
    target_ext = target_ext.lower()
    if target_ext not in AUDIO_OUTPUT_EXTS:
        raise ValueError("Unsupported audio target format.")
    out_path = TMP_DIR / f"{_safe_stem(src_path.name)}{target_ext}"
    cmd = ["ffmpeg", "-y", "-i", str(src_path)]
    if target_ext == ".mp3":
        cmd += ["-codec:a", "libmp3lame", "-q:a", "2"]
    elif target_ext == ".aac":
        cmd += ["-codec:a", "aac", "-b:a", "192k"]
    elif target_ext == ".m4a":
        cmd += ["-codec:a", "aac", "-b:a", "192k"]
    elif target_ext == ".opus":
        cmd += ["-codec:a", "libopus", "-b:a", "128k"]
    elif target_ext == ".wma":
        cmd += ["-codec:a", "wmav2", "-b:a", "192k"]
    elif target_ext == ".ac3":
        cmd += ["-codec:a", "ac3", "-b:a", "192k"]
    cmd.append(str(out_path))
    _run(cmd)
    return out_path


# =====================================================================
#  Video (FFmpeg)
# =====================================================================

def convert_video_ffmpeg(src_path: Path, target_ext: str) -> Path:
    _which_or_raise("ffmpeg", "FFmpeg")
    target_ext = target_ext.lower()
    # Audio extraction
    if target_ext in AUDIO_OUTPUT_EXTS:
        out_path = TMP_DIR / f"{_safe_stem(src_path.name)}{target_ext}"
        cmd = ["ffmpeg", "-y", "-i", str(src_path), "-vn"]
        if target_ext == ".mp3":
            cmd += ["-codec:a", "libmp3lame", "-q:a", "2"]
        elif target_ext in (".aac", ".m4a"):
            cmd += ["-codec:a", "aac", "-b:a", "192k"]
        elif target_ext == ".opus":
            cmd += ["-codec:a", "libopus", "-b:a", "128k"]
        cmd.append(str(out_path))
        _run(cmd)
        return out_path
    # GIF
    if target_ext == ".gif":
        out_path = TMP_DIR / f"{_safe_stem(src_path.name)}.gif"
        cmd = [
            "ffmpeg", "-y", "-i", str(src_path),
            "-vf", "fps=15,scale=480:-1:flags=lanczos",
            "-loop", "0", str(out_path),
        ]
        _run(cmd)
        return out_path
    # Standard video transcode
    if target_ext not in VIDEO_OUTPUT_EXTS:
        raise ValueError("Unsupported video target format.")
    out_path = TMP_DIR / f"{_safe_stem(src_path.name)}{target_ext}"
    cmd = ["ffmpeg", "-y", "-i", str(src_path)]
    if target_ext == ".webm":
        cmd += ["-codec:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
                "-codec:a", "libopus"]
    elif target_ext == ".3gp":
        cmd += ["-codec:v", "h263", "-s", "352x288", "-codec:a", "amr_nb",
                "-ar", "8000", "-ac", "1"]
    cmd.append(str(out_path))
    _run(cmd)
    return out_path


# =====================================================================
#  Type inference
# =====================================================================

def infer_type_from_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_INPUT_EXTS:
        return "image"
    if ext == PDF_EXT:
        return "pdf"
    if ext in DOC_INPUT_EXTS:
        return "doc"
    if ext in TEXT_INPUT_EXTS:
        return "text"
    if ext in AUDIO_INPUT_EXTS:
        return "audio"
    if ext in VIDEO_INPUT_EXTS:
        return "video"
    return "unknown"
