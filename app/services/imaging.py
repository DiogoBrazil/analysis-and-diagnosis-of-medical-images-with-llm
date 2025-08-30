import os
import uuid
from PIL import Image
from typing import Tuple

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

def is_allowed_filename(filename: str) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTS

def unique_id() -> str:
    return uuid.uuid4().hex

def save_upload_to_disk(file_bytes: bytes, orig_filename: str) -> Tuple[str, str]:
    uid = unique_id()
    ext = os.path.splitext(orig_filename)[1].lower()
    if ext not in ALLOWED_EXTS:
        ext = ".jpg"
    folder = os.path.join(STORAGE_DIR, uid)
    os.makedirs(folder, exist_ok=True)
    original_path = os.path.join(folder, f"original{ext}")
    with open(original_path, "wb") as f:
        f.write(file_bytes)
    return uid, original_path

def preprocess_image(input_path: str, target_width: int = 600) -> str:
    img = Image.open(input_path)
    img = img.convert("RGB")
    w, h = img.size
    if w > target_width:
        new_h = int(h * (target_width / float(w)))
        img = img.resize((target_width, new_h), Image.LANCZOS)
    out_path = os.path.join(os.path.dirname(input_path), "processed.jpg")
    img.save(out_path, format="JPEG", quality=92, optimize=True)
    return out_path
