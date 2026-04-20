"""character_gen.py — Generate character cutout PNGs for video overlay."""
from pathlib import Path

ASSETS_DIR = Path("assets") / "characters"

_NARRATOR = dict(body=(55, 115, 220, 215), skin=(255, 218, 185, 255), label="OP")
_OTHER    = dict(body=(210, 55,  55, 215), skin=(255, 218, 185, 255), label="THEM")


def ensure_characters() -> tuple[Path, Path]:
    """Return (narrator_png, other_png), generating them on first run."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    narrator_p = ASSETS_DIR / "narrator.png"
    other_p    = ASSETS_DIR / "other.png"
    if not narrator_p.exists():
        _generate(narrator_p, **_NARRATOR)
    if not other_p.exists():
        _generate(other_p, **_OTHER)
    return narrator_p, other_p


def _generate(output: Path, body: tuple, skin: tuple, label: str) -> None:
    try:
        _pil(output, body, skin, label)
    except Exception as e:
        print(f"  [Chars] PIL failed ({e}) — using rect fallback")
        _ffmpeg_rect(output, body)


def _pil(output: Path, body: tuple, skin: tuple, label: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    W, H = 150, 300
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    cx  = W // 2

    # Try to load a readable system font for the badge label
    font = None
    for fpath in [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        try:
            font = ImageFont.truetype(fpath, 17)
            break
        except Exception:
            continue

    # Badge at top
    d.rounded_rectangle([8, 2, W - 8, 28], radius=6, fill=(*body[:3], 200))
    try:
        bbox = d.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((W - tw) / 2, (26 - th) / 2), label, fill=(255, 255, 255, 255), font=font)
    except Exception:
        d.text((cx - len(label) * 4, 7), label, fill=(255, 255, 255, 255))

    # Head
    d.ellipse([cx - 26, 34, cx + 26, 86], fill=skin)

    # Body
    d.rounded_rectangle([cx - 34, 90, cx + 34, 190], radius=10, fill=body)

    # Arms
    d.rounded_rectangle([cx - 54, 95, cx - 36, 165], radius=8, fill=body)
    d.rounded_rectangle([cx + 36, 95, cx + 54, 165], radius=8, fill=body)

    # Legs
    d.rounded_rectangle([cx - 30, 194, cx - 6,  292], radius=8, fill=body)
    d.rounded_rectangle([cx + 6,  194, cx + 30, 292], radius=8, fill=body)

    img.save(str(output), "PNG")
    print(f"  [Chars] {output.name} generated")


def _ffmpeg_rect(output: Path, body: tuple) -> None:
    import subprocess
    r, g, b = body[:3]
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=0x{r:02x}{g:02x}{b:02x}:size=150x300:rate=1",
        "-frames:v", "1", str(output),
    ], capture_output=True)
    print(f"  [Chars] {output.name} (rect fallback)")
