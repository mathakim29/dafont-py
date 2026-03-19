# TDFont Renderer in Python (Remake)
[Original repository](https://github.com/N0NameN0/CODEF_Ansi_Logo_Maker)

## CLI Usage: 
```
usage: render_font [-h] [--font INDEX] [--spacing N] [--space-size N] [--variant INDEX] [--list-fonts] text

positional arguments:
  text                  Text to render as ANSI/HTML art

options:
  -h, --help            show this help message and exit
  --font,    -f INDEX   Index of the .TDF font file to use from FONTS/ (default: 0)
  --spacing, -s N       Columns of space between each character (default: 2)
  --space-size, -ss N   Width in columns of a space character ' ' (default: 5)
  --variant, -v INDEX   Font variant index within the .TDF file (default: 0)
  --list-fonts, -l      List all available fonts and exit
  --output, -o          set output type (html, ansi)
```

## Library Usage
```python
from codef import TDFRenderer

renderer = TDFRenderer("FONTS/")          # point at your TDF directory
print(renderer.render_ansi("HELLO"))        # ANSI escape-code string
print(renderer.render_html("HELLO"))        # self-contained HTML page
```

### Selecting fonts / variants
```python
fonts = renderer.list_fonts()               # list of available font paths
ansi  = renderer.render_ansi("HI", font_index=2)
ansi  = renderer.render_ansi("HI", font_path="FONTS/BLOCK.TDF")
ansi  = renderer.render_ansi("HI", font_index=0, variant=1)
```

### Tweaking spacing
```python
ansi = renderer.render_ansi(
    "HI",
    spacing=3,       # columns between characters (default 2)
    space_size=6,    # width of the space character (default 5)
)
```

### Lower-level access
```python
tdf  = renderer.load_tdf("FONTS/BLOCK.TDF")   # TDFFont object (get fonts directly from user-defined directory)
mat  = renderer.build_matrix("HI", tdf)        # RenderMatrix object
ansi = renderer.matrix_to_ansi(mat)
html = renderer.matrix_to_html(mat, title="HI")
```
