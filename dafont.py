#!/usr/bin/env python3
"""
CODEF ANSI Logo Maker - Python port
Original PHP/JS by Antoine Santo (NoNameNo)
"""

import sys
import os
import glob
import argparse

# Global state
workvar = None
matrix = []
BGmatrix = []
FTmatrix = []
fnum = 0
mytxt = ""
POSX = 1
POSY = 1
BGCOL = 0
FTCOL = 15
CHARPOSX = 1
curspacesize = 5
curspacing = 2
maxPOSX = 0
maxPOSY = 0


def parse_args():
    parser = argparse.ArgumentParser(
        prog="codef",
        description="CODEF ANSI Logo Maker — render text using TheDraw Font (.TDF) files",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
examples:
  python codef.py "HELLO"
  python codef.py "HELLO" --output ansi
  python codef.py "HELLO" --output html > logo.html
  python codef.py "HELLO WORLD" --font 2 --output ansi
  python codef.py "HI" --font 1 --spacing 3 --space-size 6 --variant 0
  python codef.py --list-fonts
        """
    )

    parser.add_argument(
        "text",
        type=str,
        nargs="?",
        default=None,
        help="Text to render as ANSI art"
    )
    parser.add_argument(
        "--output", "-o",
        choices=["ansi", "html"],
        default="ansi",
        metavar="MODE",
        help=(
            "Output mode (default: ansi)\n"
            "  ansi  — ANSI escape codes for terminal display or saving to /etc/motd\n"
            "  html  — Self-contained HTML page with DOS font and colour rendering"
        )
    )
    parser.add_argument(
        "--font", "-f",
        type=int,
        default=0,
        metavar="INDEX",
        help="Index of the .TDF font file to use from the FONTS/ directory (default: 0)"
    )
    parser.add_argument(
        "--spacing", "-s",
        type=int,
        default=2,
        metavar="N",
        help="Number of columns of space between each character (default: 2)"
    )
    parser.add_argument(
        "--space-size", "-ss",
        type=int,
        default=5,
        metavar="N",
        help="Width in columns of a space character ' ' (default: 5)"
    )
    parser.add_argument(
        "--variant", "-v",
        type=int,
        default=0,
        metavar="INDEX",
        help="Font variant index within the .TDF file — some files contain multiple fonts (default: 0)"
    )
    parser.add_argument(
        "--list-fonts", "-l",
        action="store_true",
        help="List all available .TDF font files in the FONTS/ directory and exit"
    )

    return parser.parse_args()


def main():
    global mytxt, fnum, curspacing, curspacesize

    args = parse_args()

    files = sorted(glob.glob("FONTS/*.TDF"))

    if args.list_fonts:
        if not files:
            print("No .TDF font files found in FONTS/ directory.")
        else:
            print(f"Available fonts ({len(files)} found):")
            for i, f in enumerate(files):
                print(f"  [{i}] {os.path.basename(f)}")
        sys.exit(0)

    if args.text is None:
        print("Error: please provide text to render, e.g.: python codef.py \"HELLO\"")
        sys.exit(1)

    if not files:
        print("Error: No .TDF font files found in FONTS/ directory.")
        sys.exit(1)

    if args.font < 0 or args.font >= len(files):
        print(f"Error: Font index {args.font} is out of range. Available: 0–{len(files) - 1}")
        print("Run with --list-fonts to see all available fonts.")
        sys.exit(1)

    mytxt = args.text
    fnum = args.variant
    curspacing = args.spacing
    curspacesize = args.space_size

    load_tdf(files[args.font], output_mode=args.output)


# ---------------------------------------------------------------------------
# TDF loading
# ---------------------------------------------------------------------------

def load_tdf(tdf_path, output_mode="ansi"):
    global workvar

    workvar = {
        "signature": "",
        "fontnum": 0,
        "size": 0,
        "headers": [],
        "data": [],
    }

    with open(tdf_path, "rb") as f:
        bin_data = f.read()

    file_parser(bin_data)
    font_parser(bin_data)
    text_renderer()

    if output_mode == "html":
        render_html()
    else:
        render_ansi()


def file_parser(bin_data):
    global workvar
    workvar["signature"] = bin_data[1:19]
    workvar["size"] = len(bin_data)


def font_parser(bin_data):
    global workvar

    start_offset = 0

    while start_offset + 20 < workvar["size"]:
        header = {
            "fontname": "",
            "fonttype": "",
            "letterspacing": 0,
            "blocksize": 0,
            "lettersoffsets": [],
        }

        header["fontname"] = bin_data[start_offset + 25 : start_offset + 37].decode(
            "latin-1", errors="replace"
        ).rstrip("\x00")

        ftype = bin_data[start_offset + 41]
        if ftype == 0:
            header["fonttype"] = "oUTLINE"
        elif ftype == 1:
            header["fonttype"] = "bLOCK"
        elif ftype == 2:
            header["fonttype"] = "cOLOR"

        header["letterspacing"] = bin_data[start_offset + 42]

        lo = bin_data[start_offset + 43]
        hi = bin_data[start_offset + 44]
        header["blocksize"] = (hi << 8) | lo

        n = 0
        for i in range(94):
            lo = bin_data[start_offset + 45 + n]
            hi = bin_data[start_offset + 45 + n + 1]
            header["lettersoffsets"].append((hi << 8) | lo)
            n += 2

        data_bytes = bin_data[
            start_offset + 233 : start_offset + 233 + header["blocksize"]
        ]

        workvar["headers"].append(header)
        workvar["data"].append(data_bytes)

        start_offset += 212 + header["blocksize"] + 1
        workvar["fontnum"] += 1


# ---------------------------------------------------------------------------
# Text rendering into matrix
# ---------------------------------------------------------------------------

def text_renderer():
    global workvar, fnum, mytxt, matrix, BGmatrix, FTmatrix
    global POSX, POSY, CHARPOSX, curspacing, curspacesize, FTCOL, BGCOL
    global maxPOSX, maxPOSY

    matrix   = [{} for _ in range(12)]
    FTmatrix = [{} for _ in range(12)]
    BGmatrix = [{} for _ in range(12)]

    POSX = 1
    POSY = 1
    CHARPOSX = 1
    maxPOSX = 0
    maxPOSY = 0

    if fnum >= len(workvar["headers"]):
        print(f"Error: Font variant {fnum} not found in this .TDF file.")
        print(f"Available variants: 0–{len(workvar['headers']) - 1}")
        return

    font_type = workvar["headers"][fnum]["fonttype"]

    if font_type == "oUTLINE":
        print("oUTLINE FONT TYPE\nis NOT SUPPORTED YET")
        return

    elif font_type == "cOLOR":
        for ch in mytxt:
            code = ord(ch)
            if 33 <= code < 126:
                offset = workvar["headers"][fnum]["lettersoffsets"][code - 33]
                if offset != 65535:
                    data = workvar["data"][fnum]
                    max_char_width = data[offset]
                    n = 2
                    old_posx = POSX

                    while True:
                        char_byte = data[offset + n]
                        char = bytes([char_byte]).decode("latin-1")

                        if char == "\r":
                            n -= 1
                            _printchar(char)
                        elif char_byte == 0:
                            break
                        else:
                            col = data[offset + n + 1]
                            BGCOL = col // 16
                            FTCOL = col % 16
                            _printchar(char)

                        n += 2

                    if maxPOSY < POSY:
                        maxPOSY = POSY
                    POSY = 1
                    POSX = old_posx + max_char_width + curspacing
                    if maxPOSX < POSX:
                        maxPOSX = POSX
                    CHARPOSX = POSX

            elif code == 32:
                POSX += curspacesize
                CHARPOSX = POSX

    elif font_type == "bLOCK":
        FTCOL = 15
        BGCOL = 0

        for ch in mytxt:
            code = ord(ch)
            if 33 <= code < 126:
                offset = workvar["headers"][fnum]["lettersoffsets"][code - 33]
                if offset != 65535:
                    data = workvar["data"][fnum]
                    max_char_width = data[offset]
                    n = 2
                    old_posx = POSX

                    while True:
                        char_byte = data[offset + n]
                        char = bytes([char_byte]).decode("latin-1")

                        if char_byte == 0:
                            break
                        else:
                            _printchar(char)

                        n += 1

                    if maxPOSY < POSY:
                        maxPOSY = POSY
                    POSY = 1
                    POSX = old_posx + max_char_width + curspacing
                    if maxPOSX < POSX:
                        maxPOSX = POSX
                    CHARPOSX = POSX

            elif code == 32:
                POSX += curspacesize
                CHARPOSX = POSX


def _printchar(char):
    global POSX, POSY, BGCOL, FTCOL, CHARPOSX, matrix, BGmatrix, FTmatrix

    matrix[POSY - 1][POSX - 1]   = char
    BGmatrix[POSY - 1][POSX - 1] = BGCOL
    FTmatrix[POSY - 1][POSX - 1] = FTCOL

    if ord(char[0]) == 13:  # \r — carriage return means new row in TDF
        POSX = CHARPOSX
        POSY += 1
    else:
        POSX += 1


# ---------------------------------------------------------------------------
# CP437 → Unicode (mirrors the JS fuckUTF8 table exactly)
# ---------------------------------------------------------------------------

CP437_MAP = {
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


def cp437_to_unicode(char):
    """Convert a single latin-1 character through the CP437 mapping table."""
    code = ord(char)
    mapped = CP437_MAP.get(code, code)
    return chr(mapped)


# ---------------------------------------------------------------------------
# ANSI colour helpers  (same switch tables as PHP/JS originals)
# ---------------------------------------------------------------------------

FT_ANSI = {
     0: 30,  1: 34,  2: 32,  3: 36,
     4: 31,  5: 35,  6: 33,  7: 37,
     8: 90,  9: 94, 10: 92, 11: 96,
    12: 91, 13: 95, 14: 93, 15: 97,
}

BG_ANSI = {
    0: 40, 1: 44, 2: 42, 3: 46,
    4: 41, 5: 45, 6: 43, 7: 47,
}

# CSS colours matching the 16-colour CGA/DOS palette used by the HTML source
FT_CSS = [
    "#000000", "#0000AA", "#00AA00", "#00AAAA",
    "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
    "#555555", "#5555FF", "#55FF55", "#55FFFF",
    "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
]

BG_CSS = [
    "#000000", "#0000AA", "#00AA00", "#00AAAA",
    "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
    # high-intensity backgrounds (rarely used, mirror fg table)
    "#555555", "#5555FF", "#55FF55", "#55FFFF",
    "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
]


def colconv_ansi(row, col):
    ft = FT_ANSI.get(FTmatrix[row][col], 37)
    bg = BG_ANSI.get(BGmatrix[row][col], 40)
    return f"\x1b[{bg};{ft}m"


# ---------------------------------------------------------------------------
# Output: ANSI  (matches PHP eko() / JS dl_txt() behaviour)
# ---------------------------------------------------------------------------

def render_ansi():
    global matrix, BGmatrix, FTmatrix, fnum, workvar

    font_type = workvar["headers"][fnum]["fonttype"]
    old_esc = ""

    for i in range(12):
        if not matrix[i]:
            continue

        max_col = max(matrix[i].keys())

        for n in range(max_col + 1):
            if n not in matrix[i]:
                # Undefined cell — reset + space (matches JS `typeof … 'undefined'` branch)
                sys.stdout.write("\x1b[0m ")
                old_esc = "\x1b[0m"

            elif matrix[i][n] == "\r":
                # Carriage-return marker — output a plain space, maybe reset colour
                if font_type == "cOLOR" and old_esc != "\x1b[0m":
                    sys.stdout.write("\x1b[0m")
                    old_esc = "\x1b[0m"
                sys.stdout.write(" ")

            else:
                if font_type == "cOLOR":
                    new_esc = colconv_ansi(i, n)
                    if new_esc != old_esc:
                        sys.stdout.write(new_esc)
                        old_esc = new_esc

                sys.stdout.write(cp437_to_unicode(matrix[i][n]))

        sys.stdout.write("\x1b[0m\n")
        old_esc = "\x1b[0m"


# ---------------------------------------------------------------------------
# Output: HTML  (self-contained page; mirrors the JS canvas rendering intent
#               but produces plain HTML spans instead of a canvas element so
#               the result works anywhere without JS dependencies)
# ---------------------------------------------------------------------------

def render_html():
    global matrix, BGmatrix, FTmatrix, fnum, workvar

    font_type = workvar["headers"][fnum]["fonttype"]

    # Build the inner HTML row by row, grouping consecutive same-colour runs
    # into <span> elements — same colour model as the JS canvas drawTile calls.
    rows_html = []

    for i in range(12):
        if not matrix[i]:
            continue

        max_col = max(matrix[i].keys())
        row_parts = []

        current_fg = None
        current_bg = None
        current_chars = []

        def flush_span():
            if not current_chars:
                return
            text = "".join(current_chars)
            # Escape HTML entities
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if font_type == "cOLOR":
                style = f"color:{current_fg};background:{current_bg}"
            else:
                style = "color:#FFFFFF;background:#000000"
            row_parts.append(f'<span style="{style}">{text}</span>')
            current_chars.clear()

        for n in range(max_col + 1):
            if n not in matrix[i] or matrix[i][n] == "\r":
                # Treat missing / CR cells as a plain space in current bg colour
                fg = FT_CSS[current_fg_idx] if current_fg is not None else "#FFFFFF"
                bg = BG_CSS[current_bg_idx] if current_bg is not None else "#000000"
                if font_type == "cOLOR" and (fg != current_fg or bg != current_bg):
                    flush_span()
                    current_fg = fg
                    current_bg = bg
                current_chars.append("\u00a0")  # non-breaking space keeps cell width
            else:
                char = matrix[i][n]
                if font_type == "cOLOR":
                    current_fg_idx = FTmatrix[i][n]
                    current_bg_idx = BGmatrix[i][n]
                    fg = FT_CSS[current_fg_idx % len(FT_CSS)]
                    bg = BG_CSS[current_bg_idx % len(BG_CSS)]
                else:
                    current_fg_idx = 15
                    current_bg_idx = 0
                    fg = "#FFFFFF"
                    bg = "#000000"

                if fg != current_fg or bg != current_bg:
                    flush_span()
                    current_fg = fg
                    current_bg = bg

                current_chars.append(cp437_to_unicode(char))

        flush_span()
        rows_html.append("".join(row_parts))

    inner = "\n".join(f'<div class="ansi-row">{r}</div>' for r in rows_html)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CODEF ANSI Logo — {mytxt}</title>
<style>
  /* Embed a fallback monospace stack; users can drop in Perfect DOS VGA 437
     by placing the .woff file next to this HTML and adjusting the src below. */
  @font-face {{
    font-family: 'PerfectDOS';
    src: url('CSS/Perfect DOS VGA 437 Win.woff') format('woff');
  }}

  html, body {{
    margin: 0;
    padding: 0;
    background: #000;
    color: #fff;
  }}

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

  .ansi-row {{
    display: block;
    height: 16px;
    line-height: 16px;
    overflow: hidden;
  }}

  span {{
    display: inline;
    white-space: pre;
    line-height: 16px;
  }}
</style>
</head>
<body>
<div class="ansi-output">
{inner}
</div>
</body>
</html>
"""

    sys.stdout.write(html)


if __name__ == "__main__":
    main()