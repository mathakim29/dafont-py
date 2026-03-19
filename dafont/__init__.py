from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# CP437 → Unicode mapping
# ---------------------------------------------------------------------------

_CP437_MAP: Dict[int, int] = {
    128: 199,  129: 252,  130: 233,  131: 226,  132: 228,  133: 224,
    134: 229,  135: 231,  136: 234,  137: 235,  138: 232,  139: 239,
    140: 238,  141: 236,  142: 196,  143: 197,  144: 201,  145: 230,
    146: 198,  147: 244,  148: 246,  149: 242,  150: 251,  151: 249,
    152: 255,  153: 214,  154: 220,  155: 162,  156: 163,  157: 165,
    158: 8359, 159: 402,  160: 225,  161: 237,  162: 243,  163: 250,
    164: 241,  165: 209,  166: 170,  167: 186,  168: 191,  169: 8976,
    170: 172,  171: 189,  172: 188,  173: 161,  174: 171,  175: 187,
    176: 9617, 177: 9618, 178: 9619, 179: 9474, 180: 9508, 181: 9569,
    182: 9570, 183: 9558, 184: 9557, 185: 9571, 186: 9553, 187: 9559,
    188: 9565, 189: 9564, 190: 9563, 191: 9488, 192: 9492, 193: 9524,
    194: 9516, 195: 9500, 196: 9472, 197: 9532, 198: 9566, 199: 9567,
    200: 9562, 201: 9556, 202: 9577, 203: 9574, 204: 9568, 205: 9552,
    206: 9580, 207: 9575, 208: 9576, 209: 9572, 210: 9573, 211: 9561,
    212: 9560, 213: 9554, 214: 9555, 215: 9579, 216: 9578, 217: 9496,
    218: 9484, 219: 9608, 220: 9604, 221: 9612, 222: 9616, 223: 9600,
    224: 945,  225: 223,  226: 915,  227: 960,  228: 931,  229: 963,
    230: 181,  231: 964,  232: 934,  233: 920,  234: 937,  235: 948,
    236: 8734, 237: 966,  238: 949,  239: 8745, 240: 8801, 241: 177,
    242: 8805, 243: 8804, 244: 8992, 245: 8993, 246: 247,  247: 8776,
    248: 176,  249: 8729, 250: 183,  251: 8730, 252: 8319, 253: 178,
    254: 9632,
}

# CGA/DOS 16-colour palette
_FT_CSS = [
    "#000000", "#0000AA", "#00AA00", "#00AAAA",
    "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
    "#555555", "#5555FF", "#55FF55", "#55FFFF",
    "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
]
_BG_CSS = _FT_CSS  # same palette for backgrounds

# ANSI escape colour codes
_FT_ANSI: Dict[int, int] = {
     0: 30,  1: 34,  2: 32,  3: 36,
     4: 31,  5: 35,  6: 33,  7: 37,
     8: 90,  9: 94, 10: 92, 11: 96,
    12: 91, 13: 95, 14: 93, 15: 97,
}
_BG_ANSI: Dict[int, int] = {
    0: 40, 1: 44, 2: 42, 3: 46,
    4: 41, 5: 45, 6: 43, 7: 47,
}


def _cp437(char: str) -> str:
    """Translate a single latin-1 character through the CP437 table."""
    return chr(_CP437_MAP.get(ord(char), ord(char)))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class FontType:
    OUTLINE = "oUTLINE"
    BLOCK   = "bLOCK"
    COLOR   = "cOLOR"


@dataclass
class TDFFontHeader:
    """Parsed header for one font variant inside a .TDF file."""
    fontname: str
    fonttype: str
    letterspacing: int
    blocksize: int
    lettersoffsets: List[int] = field(default_factory=list)


@dataclass
class TDFFont:
    """All variants parsed from a single .TDF file."""
    path: str
    headers: List[TDFFontHeader] = field(default_factory=list)
    data: List[bytes] = field(default_factory=list)

    @property
    def variant_count(self) -> int:
        return len(self.headers)

    def variant_names(self) -> List[str]:
        return [h.fontname for h in self.headers]


@dataclass
class RenderMatrix:
    """
    The raw cell grid produced by text_renderer.

    Each of the 12 rows is a dict mapping column-index → character.
    Parallel dicts hold the foreground / background colour indices (0-15).
    """
    font_type: str
    rows:      List[Dict[int, str]] = field(default_factory=lambda: [{} for _ in range(12)])
    fg:        List[Dict[int, int]] = field(default_factory=lambda: [{} for _ in range(12)])
    bg:        List[Dict[int, int]] = field(default_factory=lambda: [{} for _ in range(12)])
    max_col:   int = 0
    max_row:   int = 0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CodefError(Exception):
    """Base exception for all codef errors."""


class FontNotFoundError(CodefError):
    """Raised when a requested font file does not exist."""


class FontVariantError(CodefError):
    """Raised when a requested variant index is out of range."""


class UnsupportedFontTypeError(CodefError):
    """Raised for font types not yet supported (e.g. oUTLINE)."""


# ---------------------------------------------------------------------------
# TDFRenderer
# ---------------------------------------------------------------------------

class TDFRenderer:
    """
    High-level interface for rendering text with TheDraw Fonts.

    Parameters
    ----------
    fonts_dir : str | Path | None
        Directory that contains .TDF font files.  Defaults to a ``FONTS/``
        folder located next to this library file.  Pass an explicit path to
        override.
    default_spacing : int
        Columns of blank space inserted between rendered characters.
    default_space_size : int
        Width (in columns) of the ASCII space character.
    """

    #: Default FONTS/ folder sits next to this file, not the caller's cwd
    _DEFAULT_FONTS_DIR = Path(__file__).parent / "FONTS"

    def __init__(
        self,
        fonts_dir: str | Path | None = None,
        default_spacing: int = 2,
        default_space_size: int = 5,
    ) -> None:
        self.fonts_dir = Path(fonts_dir) if fonts_dir is not None else self._DEFAULT_FONTS_DIR
        self.default_spacing = default_spacing
        self.default_space_size = default_space_size
        self._cache: Dict[str, TDFFont] = {}

    # ------------------------------------------------------------------
    # Font discovery
    # ------------------------------------------------------------------

    def list_fonts(self) -> List[Path]:
        """Return sorted list of .TDF paths found in *fonts_dir*."""
        return sorted(self.fonts_dir.glob("*.TDF"))

    def font_path(self, index: int) -> Path:
        """Resolve a font by numeric index from :meth:`list_fonts`."""
        paths = self.list_fonts()
        if not paths:
            raise FontNotFoundError(f"No .TDF files found in {self.fonts_dir}")
        if index < 0 or index >= len(paths):
            raise FontNotFoundError(
                f"Font index {index} out of range (0–{len(paths) - 1}). "
                f"Found: {[p.name for p in paths]}"
            )
        return paths[index]

    # ------------------------------------------------------------------
    # TDF parsing
    # ------------------------------------------------------------------

    def load_tdf(self, path: str | Path) -> TDFFont:
        """
        Parse a .TDF file and return a :class:`TDFFont`.

        Results are cached; subsequent calls with the same path are free.
        """
        path = Path(path)
        key = str(path.resolve())
        if key in self._cache:
            return self._cache[key]

        if not path.exists():
            raise FontNotFoundError(f"TDF file not found: {path}")

        raw = path.read_bytes()
        font = self._parse_tdf(str(path), raw)
        self._cache[key] = font
        return font

    @staticmethod
    def _parse_tdf(path: str, raw: bytes) -> TDFFont:
        font = TDFFont(path=path)
        size = len(raw)
        offset = 0

        while offset + 20 < size:
            hdr = TDFFontHeader(
                fontname="",
                fonttype="",
                letterspacing=0,
                blocksize=0,
            )

            hdr.fontname = (
                raw[offset + 25 : offset + 37]
                .decode("latin-1", errors="replace")
                .rstrip("\x00")
            )

            ftype = raw[offset + 41]
            hdr.fonttype = {0: FontType.OUTLINE, 1: FontType.BLOCK, 2: FontType.COLOR}.get(
                ftype, FontType.BLOCK
            )

            hdr.letterspacing = raw[offset + 42]
            lo = raw[offset + 43]
            hi = raw[offset + 44]
            hdr.blocksize = (hi << 8) | lo

            n = 0
            for _ in range(94):
                lo = raw[offset + 45 + n]
                hi = raw[offset + 45 + n + 1]
                hdr.lettersoffsets.append((hi << 8) | lo)
                n += 2

            data_bytes = raw[offset + 233 : offset + 233 + hdr.blocksize]

            font.headers.append(hdr)
            font.data.append(data_bytes)

            offset += 212 + hdr.blocksize + 1

        return font

    # ------------------------------------------------------------------
    # Matrix builder
    # ------------------------------------------------------------------

    def build_matrix(
        self,
        text: str,
        tdf: TDFFont,
        variant: int = 0,
        spacing: Optional[int] = None,
        space_size: Optional[int] = None,
    ) -> RenderMatrix:
        """
        Render *text* into a :class:`RenderMatrix` using *tdf*.

        Parameters
        ----------
        text :
            The string to render.
        tdf :
            Parsed :class:`TDFFont` (from :meth:`load_tdf`).
        variant :
            Which font variant inside the TDF file to use (default 0).
        spacing :
            Column gap between characters.  Falls back to *default_spacing*.
        space_size :
            Width of the space character.  Falls back to *default_space_size*.
        """
        if variant >= tdf.variant_count:
            raise FontVariantError(
                f"Variant {variant} not found. Available: 0–{tdf.variant_count - 1}"
            )

        hdr = tdf.headers[variant]
        if hdr.fonttype == FontType.OUTLINE:
            raise UnsupportedFontTypeError("oUTLINE font type is not supported.")

        spacing    = spacing    if spacing    is not None else self.default_spacing
        space_size = space_size if space_size is not None else self.default_space_size

        mat = RenderMatrix(font_type=hdr.fonttype)

        pos_x    = 1
        pos_y    = 1
        char_pos_x = 1
        ft_col   = 15
        bg_col   = 0

        def put(ch: str, col: int, row: int, fg: int, bg: int) -> None:
            mat.rows[row][col] = ch
            mat.fg[row][col]   = fg
            mat.bg[row][col]   = bg

        if hdr.fonttype == FontType.COLOR:
            for ch in text:
                code = ord(ch)
                if 33 <= code < 126:
                    letter_idx = code - 33
                    off = hdr.lettersoffsets[letter_idx]
                    if off == 65535:
                        continue
                    data = tdf.data[variant]
                    max_char_width = data[off]
                    n = 2
                    old_pos_x = pos_x

                    while True:
                        cb = data[off + n]
                        c  = bytes([cb]).decode("latin-1")

                        if c == "\r":
                            n -= 1
                            put(c, pos_x - 1, pos_y - 1, ft_col, bg_col)
                            pos_x = char_pos_x
                            pos_y += 1
                        elif cb == 0:
                            break
                        else:
                            col_byte = data[off + n + 1]
                            bg_col   = col_byte // 16
                            ft_col   = col_byte % 16
                            put(c, pos_x - 1, pos_y - 1, ft_col, bg_col)
                            pos_x += 1

                        n += 2

                    mat.max_row = max(mat.max_row, pos_y - 1)
                    pos_y = 1
                    pos_x = old_pos_x + max_char_width + spacing
                    mat.max_col = max(mat.max_col, pos_x - 1)
                    char_pos_x = pos_x

                elif code == 32:
                    pos_x += space_size
                    char_pos_x = pos_x

        elif hdr.fonttype == FontType.BLOCK:
            ft_col = 15
            bg_col = 0

            for ch in text:
                code = ord(ch)
                if 33 <= code < 126:
                    letter_idx = code - 33
                    off = hdr.lettersoffsets[letter_idx]
                    if off == 65535:
                        continue
                    data = tdf.data[variant]
                    max_char_width = data[off]
                    n = 2
                    old_pos_x = pos_x

                    while True:
                        cb = data[off + n]
                        c  = bytes([cb]).decode("latin-1")
                        if cb == 0:
                            break

                        if c == "\r":
                            put(c, pos_x - 1, pos_y - 1, ft_col, bg_col)
                            pos_x = char_pos_x
                            pos_y += 1
                        else:
                            put(c, pos_x - 1, pos_y - 1, ft_col, bg_col)
                            pos_x += 1

                        n += 1

                    mat.max_row = max(mat.max_row, pos_y - 1)
                    pos_y = 1
                    pos_x = old_pos_x + max_char_width + spacing
                    mat.max_col = max(mat.max_col, pos_x - 1)
                    char_pos_x = pos_x

                elif code == 32:
                    pos_x += space_size
                    char_pos_x = pos_x

        return mat

    # ------------------------------------------------------------------
    # Matrix → string converters
    # ------------------------------------------------------------------

    @staticmethod
    def matrix_to_ansi(mat: RenderMatrix) -> str:
        """
        Convert a :class:`RenderMatrix` to a string of ANSI escape codes.

        The returned string contains ANSI colour sequences and ends with a
        reset code.  Write it to stdout or embed it in a file such as
        ``/etc/motd``.
        """
        out   = []
        old_esc = ""

        for i in range(12):
            row = mat.rows[i]
            if not row:
                continue

            max_col = max(row.keys())

            for n in range(max_col + 1):
                if n not in row:
                    out.append("\x1b[0m ")
                    old_esc = "\x1b[0m"

                elif row[n] == "\r":
                    if mat.font_type == FontType.COLOR and old_esc != "\x1b[0m":
                        out.append("\x1b[0m")
                        old_esc = "\x1b[0m"
                    out.append(" ")

                else:
                    if mat.font_type == FontType.COLOR:
                        ft = _FT_ANSI.get(mat.fg[i][n], 37)
                        bg = _BG_ANSI.get(mat.bg[i][n], 40)
                        new_esc = f"\x1b[{bg};{ft}m"
                        if new_esc != old_esc:
                            out.append(new_esc)
                            old_esc = new_esc

                    out.append(_cp437(row[n]))

            out.append("\x1b[0m\n")
            old_esc = "\x1b[0m"

        return "".join(out)

    @staticmethod
    def matrix_to_html(mat: RenderMatrix, title: str = "CODEF") -> str:
        """
        Convert a :class:`RenderMatrix` to a self-contained HTML page string.

        The page uses the CGA/DOS colour palette and a monospace font stack.
        Drop ``Perfect DOS VGA 437 Win.woff`` next to the HTML file to get
        the authentic 8×16 DOS look.
        """
        rows_html: List[str] = []

        for i in range(12):
            row = mat.rows[i]
            if not row:
                continue

            max_col = max(row.keys())
            parts: List[str] = []
            cur_fg: Optional[str] = None
            cur_bg: Optional[str] = None
            buf: List[str] = []

            def flush() -> None:
                if not buf:
                    return
                text = (
                    "".join(buf)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                if mat.font_type == FontType.COLOR:
                    style = f"color:{cur_fg};background:{cur_bg}"
                else:
                    style = "color:#FFFFFF;background:#000000"
                parts.append(f'<span style="{style}">{text}</span>')
                buf.clear()

            for n in range(max_col + 1):
                if n not in row or row[n] == "\r":
                    if mat.font_type == FontType.COLOR:
                        fg = cur_fg or "#FFFFFF"
                        bg = cur_bg or "#000000"
                        if fg != cur_fg or bg != cur_bg:
                            flush()
                            cur_fg, cur_bg = fg, bg
                    buf.append("\u00a0")
                else:
                    char = row[n]
                    if mat.font_type == FontType.COLOR:
                        fg = _FT_CSS[mat.fg[i].get(n, 15) % len(_FT_CSS)]
                        bg = _BG_CSS[mat.bg[i].get(n,  0) % len(_BG_CSS)]
                    else:
                        fg = "#FFFFFF"
                        bg = "#000000"

                    if fg != cur_fg or bg != cur_bg:
                        flush()
                        cur_fg, cur_bg = fg, bg

                    buf.append(_cp437(char))

            flush()
            rows_html.append("".join(parts))

        inner = "\n".join(
            f'<div class="ansi-row">{r}</div>' for r in rows_html
        )

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CODEF ANSI Logo — {title}</title>
<style>
  @font-face {{
    font-family: 'PerfectDOS';
    src: url('CSS/Perfect DOS VGA 437 Win.woff') format('woff');
  }}
  html, body {{ margin:0; padding:0; background:#000; color:#fff; }}
  .ansi-output {{
    display: inline-block;
    font-family: 'PerfectDOS', 'Courier New', monospace;
    font-size: 16px;
    line-height: 2px;
    letter-spacing: 0;
    white-space: pre;
    padding: 1em;
    background: #000;
  }}
  .ansi-row {{ display:block; height:16px; line-height:16px; overflow:hidden; }}
  span {{ display:inline; white-space:pre; line-height:16px; }}
</style>
</head>
<body>
<div class="ansi-output">
{inner}
</div>
</body>
</html>
"""

    # ------------------------------------------------------------------
    # Convenience one-shot render methods
    # ------------------------------------------------------------------

    def render_ansi(
        self,
        text: str,
        *,
        font_index: Optional[int] = None,
        font_path: Optional[str | Path] = None,
        variant: int = 0,
        spacing: Optional[int] = None,
        space_size: Optional[int] = None,
    ) -> str:
        """
        Render *text* and return an ANSI escape-code string.

        Provide either *font_index* (picks from ``fonts_dir``) or an explicit
        *font_path*.  Defaults to font index 0 when neither is given.
        """
        tdf = self._resolve_font(font_index, font_path)
        mat = self.build_matrix(text, tdf, variant=variant,
                                spacing=spacing, space_size=space_size)
        return self.matrix_to_ansi(mat)

    def render_html(
        self,
        text: str,
        *,
        font_index: Optional[int] = None,
        font_path: Optional[str | Path] = None,
        variant: int = 0,
        spacing: Optional[int] = None,
        space_size: Optional[int] = None,
    ) -> str:
        """
        Render *text* and return a self-contained HTML page string.

        Same font-selection parameters as :meth:`render_ansi`.
        """
        tdf = self._resolve_font(font_index, font_path)
        mat = self.build_matrix(text, tdf, variant=variant,
                                spacing=spacing, space_size=space_size)
        return self.matrix_to_html(mat, title=text)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_font(
        self,
        font_index: Optional[int],
        font_path: Optional[str | Path],
    ) -> TDFFont:
        if font_path is not None:
            return self.load_tdf(font_path)
        idx = 0 if font_index is None else font_index
        return self.load_tdf(self.font_path(idx))