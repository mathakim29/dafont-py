### TDFont Renderer in Python (Remake)
[Based on this repository](https://github.com/N0NameN0/CODEF_Ansi_Logo_Maker)

```
usage: dafont [-h] [--font INDEX] [--spacing N] [--space-size N] [--variant INDEX] [--list-fonts] text

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