#!/usr/bin/env python3


import sys
import os
import glob
import argparse

# Resolve FONTS directory relative to this module file
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_FONTS_DIR = os.path.join(_MODULE_DIR, "FONTS")


class TDFRender:
    def __init__(self, spacing=2, space_size=5, fonts_dir=None):
        self.curspacing = spacing
        self.curspacesize = space_size
        self.fonts_dir = fonts_dir or _DEFAULT_FONTS_DIR
        self._reset_state()

    def _reset_state(self):
        self.workvar = None
        self.matrix = []
        self.BGmatrix = []
        self.FTmatrix = []
        self.fnum = 0
        self.mytxt = ""
        self.POSX = 1
        self.POSY = 1
        self.BGCOL = 0
        self.FTCOL = 15
        self.CHARPOSX = 1
        self.maxPOSX = 0
        self.maxPOSY = 0

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def list_fonts(self):
        """Return a sorted list of available font names (without path or extension)."""
        return [
            os.path.splitext(os.path.basename(p))[0]
            for p in self._list_font_paths()
        ]

    def _list_font_paths(self):
        """Return a sorted list of full .TDF font file paths (internal use)."""
        return sorted(glob.glob(os.path.join(self.fonts_dir, "*.TDF")))

    def render(self, text, font_index=0, variant=0, output_mode="ansi"):
        """
        Render *text* using the specified font and return the result as a string.

        Parameters
        ----------
        text        : str   — text to render
        font_index  : int   — index into the sorted list of .TDF files
        variant     : int   — font variant within the .TDF file
        output_mode : str   — "ansi" or "html"
        """
        self._reset_state()
        self.mytxt = text
        self.fnum = variant

        files = self._list_font_paths()
        if not files:
            raise FileNotFoundError(f"No .TDF font files found in {self.fonts_dir!r}")
        if font_index < 0 or font_index >= len(files):
            raise IndexError(
                f"Font index {font_index} is out of range. "
                f"Available: 0–{len(files) - 1}"
            )

        return self._load_tdf(files[font_index], output_mode=output_mode)

    # -----------------------------------------------------------------------
    # TDF loading
    # -----------------------------------------------------------------------

    def _load_tdf(self, tdf_path, output_mode="ansi"):
        self.workvar = {
            "signature": "",
            "fontnum": 0,
            "size": 0,
            "headers": [],
            "data": [],
        }

        with open(tdf_path, "rb") as f:
            bin_data = f.read()

        self._file_parser(bin_data)
        self._font_parser(bin_data)
        self._text_renderer()

        if output_mode == "html":
            return self._render_html()
        else:
            return self._render_ansi()

    def _file_parser(self, bin_data):
        self.workvar["signature"] = bin_data[1:19]
        self.workvar["size"] = len(bin_data)

    def _font_parser(self, bin_data):
        start_offset = 0

        while start_offset + 20 < self.workvar["size"]:
            header = {
                "fontname": "",
                "fonttype": "",
                "letterspacing": 0,
                "blocksize": 0,
                "lettersoffsets": [],
            }

            header["fontname"] = bin_data[
                start_offset + 25 : start_offset + 37
            ].decode("latin-1", errors="replace").rstrip("\x00")

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

            self.workvar["headers"].append(header)
            self.workvar["data"].append(data_bytes)

            start_offset += 212 + header["blocksize"] + 1
            self.workvar["fontnum"] += 1

    # -----------------------------------------------------------------------
    # Text rendering into matrix
    # -----------------------------------------------------------------------

    def _text_renderer(self):
        self.matrix   = [{} for _ in range(12)]
        self.FTmatrix = [{} for _ in range(12)]
        self.BGmatrix = [{} for _ in range(12)]

        self.POSX = 1
        self.POSY = 1
        self.CHARPOSX = 1
        self.maxPOSX = 0
        self.maxPOSY = 0

        if self.fnum >= len(self.workvar["headers"]):
            raise IndexError(
                f"Font variant {self.fnum} not found in this .TDF file. "
                f"Available variants: 0–{len(self.workvar['headers']) - 1}"
            )

        font_type = self.workvar["headers"][self.fnum]["fonttype"]

        if font_type == "oUTLINE":
            raise NotImplementedError("oUTLINE font type is not supported yet")

        elif font_type == "cOLOR":
            for ch in self.mytxt:
                code = ord(ch)
                if 33 <= code < 126:
                    offset = self.workvar["headers"][self.fnum]["lettersoffsets"][code - 33]
                    if offset != 65535:
                        data = self.workvar["data"][self.fnum]
                        max_char_width = data[offset]
                        n = 2
                        old_posx = self.POSX

                        while True:
                            char_byte = data[offset + n]
                            char = bytes([char_byte]).decode("latin-1")

                            if char == "\r":
                                n -= 1
                                self._printchar(char)
                            elif char_byte == 0:
                                break
                            else:
                                col = data[offset + n + 1]
                                self.BGCOL = col // 16
                                self.FTCOL = col % 16
                                self._printchar(char)

                            n += 2

                        if self.maxPOSY < self.POSY:
                            self.maxPOSY = self.POSY
                        self.POSY = 1
                        self.POSX = old_posx + max_char_width + self.curspacing
                        if self.maxPOSX < self.POSX:
                            self.maxPOSX = self.POSX
                        self.CHARPOSX = self.POSX

                elif code == 32:
                    self.POSX += self.curspacesize
                    self.CHARPOSX = self.POSX

        elif font_type == "bLOCK":
            self.FTCOL = 15
            self.BGCOL = 0

            for ch in self.mytxt:
                code = ord(ch)
                if 33 <= code < 126:
                    offset = self.workvar["headers"][self.fnum]["lettersoffsets"][code - 33]
                    if offset != 65535:
                        data = self.workvar["data"][self.fnum]
                        max_char_width = data[offset]
                        n = 2
                        old_posx = self.POSX

                        while True:
                            char_byte = data[offset + n]
                            char = bytes([char_byte]).decode("latin-1")

                            if char_byte == 0:
                                break
                            else:
                                self._printchar(char)

                            n += 1

                        if self.maxPOSY < self.POSY:
                            self.maxPOSY = self.POSY
                        self.POSY = 1
                        self.POSX = old_posx + max_char_width + self.curspacing
                        if self.maxPOSX < self.POSX:
                            self.maxPOSX = self.POSX
                        self.CHARPOSX = self.POSX

                elif code == 32:
                    self.POSX += self.curspacesize
                    self.CHARPOSX = self.POSX

    def _printchar(self, char):
        self.matrix[self.POSY - 1][self.POSX - 1]   = char
        self.BGmatrix[self.POSY - 1][self.POSX - 1] = self.BGCOL
        self.FTmatrix[self.POSY - 1][self.POSX - 1] = self.FTCOL

        if ord(char[0]) == 13:  # \r — carriage return means new row in TDF
            self.POSX = self.CHARPOSX
            self.POSY += 1
        else:
            self.POSX += 1

    # -----------------------------------------------------------------------
    # CP437 → Unicode
    # -----------------------------------------------------------------------

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

    def _cp437_to_unicode(self, char):
        code = ord(char)
        return chr(self.CP437_MAP.get(code, code))

    # -----------------------------------------------------------------------
    # ANSI colour helpers
    # -----------------------------------------------------------------------

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

    FT_CSS = [
        "#000000", "#0000AA", "#00AA00", "#00AAAA",
        "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
        "#555555", "#5555FF", "#55FF55", "#55FFFF",
        "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
    ]

    BG_CSS = [
        "#000000", "#0000AA", "#00AA00", "#00AAAA",
        "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
        "#555555", "#5555FF", "#55FF55", "#55FFFF",
        "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
    ]

    def _colconv_ansi(self, row, col):
        ft = self.FT_ANSI.get(self.FTmatrix[row][col], 37)
        bg = self.BG_ANSI.get(self.BGmatrix[row][col], 40)
        return f"\x1b[{bg};{ft}m"

    # -----------------------------------------------------------------------
    # Output: ANSI
    # -----------------------------------------------------------------------

    def _render_ansi(self):
        font_type = self.workvar["headers"][self.fnum]["fonttype"]
        old_esc = ""
        out = []

        for i in range(12):
            if not self.matrix[i]:
                continue

            max_col = max(self.matrix[i].keys())

            for n in range(max_col + 1):
                if n not in self.matrix[i]:
                    out.append("\x1b[0m ")
                    old_esc = "\x1b[0m"

                elif self.matrix[i][n] == "\r":
                    if font_type == "cOLOR" and old_esc != "\x1b[0m":
                        out.append("\x1b[0m")
                        old_esc = "\x1b[0m"
                    out.append(" ")

                else:
                    if font_type == "cOLOR":
                        new_esc = self._colconv_ansi(i, n)
                        if new_esc != old_esc:
                            out.append(new_esc)
                            old_esc = new_esc

                    out.append(self._cp437_to_unicode(self.matrix[i][n]))

            out.append("\x1b[0m\n")
            old_esc = "\x1b[0m"

        return "".join(out)

    # -----------------------------------------------------------------------
    # Output: HTML
    # -----------------------------------------------------------------------

    def _render_html(self):
        font_type = self.workvar["headers"][self.fnum]["fonttype"]
        rows_html = []

        for i in range(12):
            if not self.matrix[i]:
                continue

            max_col = max(self.matrix[i].keys())
            row_parts = []
            current_fg = None
            current_bg = None
            current_chars = []

            def flush_span():
                if not current_chars:
                    return
                text = "".join(current_chars)
                text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if font_type == "cOLOR":
                    style = f"color:{current_fg};background:{current_bg}"
                else:
                    style = "color:#FFFFFF;background:#000000"
                row_parts.append(f'<span style="{style}">{text}</span>')
                current_chars.clear()

            for n in range(max_col + 1):
                if n not in self.matrix[i] or self.matrix[i][n] == "\r":
                    fg = self.FT_CSS[current_fg_idx] if current_fg is not None else "#FFFFFF"
                    bg = self.BG_CSS[current_bg_idx] if current_bg is not None else "#000000"
                    if font_type == "cOLOR" and (fg != current_fg or bg != current_bg):
                        flush_span()
                        current_fg = fg
                        current_bg = bg
                    current_chars.append("\u00a0")
                else:
                    char = self.matrix[i][n]
                    if font_type == "cOLOR":
                        current_fg_idx = self.FTmatrix[i][n]
                        current_bg_idx = self.BGmatrix[i][n]
                        fg = self.FT_CSS[current_fg_idx % len(self.FT_CSS)]
                        bg = self.BG_CSS[current_bg_idx % len(self.BG_CSS)]
                    else:
                        current_fg_idx = 15
                        current_bg_idx = 0
                        fg = "#FFFFFF"
                        bg = "#000000"

                    if fg != current_fg or bg != current_bg:
                        flush_span()
                        current_fg = fg
                        current_bg = bg

                    current_chars.append(self._cp437_to_unicode(char))

            flush_span()
            rows_html.append("".join(row_parts))

        inner = "\n".join(f'<div class="ansi-row">{r}</div>' for r in rows_html)

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TDFRender ANSI Logo — {self.mytxt}</title>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: #000;
    color: #fff;
  }}

  .ansi-output {{
    display: inline-block;
    font-family: 'Courier New', 'Lucida Console', monospace;
    font-size: 16px;
    line-height: 0px;
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