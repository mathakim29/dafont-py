from . import TDFRender
import argparse
import os 
import sys

def _parse_args():
    parser = argparse.ArgumentParser(
        prog="render",
        description="Render text using TheDraw Font (.TDF) files",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
examples:
  python -m dafont.render "HELLO"
  python -m dafont.render "HELLO" --output ansi
  python -m dafont.render "HELLO" --output html > logo.html
  python -m dafont.render "HELLO WORLD" --font 2 --output ansi
  python -m dafont.render "HI" --font 1 --spacing 3 --space-size 6 --variant 0
  python -m dafont.render --list-fonts
  python -m dafont.render "HELLO" --fontdir /path/to/my/fonts
        """
    )
    parser.add_argument("text", type=str, nargs="?", default=None,
                        help="Text to render as ANSI art")
    parser.add_argument("--output", "-o", choices=["ansi", "html"], default="ansi",
                        metavar="MODE",
                        help="Output mode (default: ansi)\n"
                             "  ansi  — ANSI escape codes\n"
                             "  html  — Self-contained HTML page")
    parser.add_argument("--font", "-f", type=int, default=0, metavar="INDEX",
                        help="Index of the .TDF font file (default: 0)")
    parser.add_argument("--spacing", "-s", type=int, default=2, metavar="N",
                        help="Columns of space between characters (default: 2)")
    parser.add_argument("--space-size", "-ss", type=int, default=5, metavar="N",
                        help="Width of a space character in columns (default: 5)")
    parser.add_argument("--variant", "-v", type=int, default=0, metavar="INDEX",
                        help="Font variant index within the .TDF file (default: 0)")
    parser.add_argument("--fontdir", "-d", type=str, default=None, metavar="DIR",
                        help="Directory containing .TDF font files\n"
                             "(default: FONTS/ next to this script)")
    parser.add_argument("--list-fonts", "-l", action="store_true",
                        help="List all available .TDF font files and exit")
    return parser.parse_args()


def main():
    args = _parse_args()

    # Validate --fontdir if provided
    if args.fontdir is not None and not os.path.isdir(args.fontdir):
        print(f"Error: --fontdir {args.fontdir!r} is not a valid directory")
        sys.exit(1)

    renderer = TDFRender(
        spacing=args.spacing,
        space_size=args.space_size,
        fonts_dir=args.fontdir,
    )

    if args.list_fonts:
        files = renderer.list_fonts()
        if not files:
            print(f"No .TDF font files found in {renderer.fonts_dir!r}")
        else:
            print(f"Available fonts ({len(files)} found in {renderer.fonts_dir!r}):")
            for i, f in enumerate(files):
                print(f"  [{i}] {os.path.basename(f)}")
        sys.exit(0)

    if args.text is None:
        print('Error: please provide text to render, e.g.: python -m dafont.render "HELLO"')
        sys.exit(1)

    try:
        result = renderer.render(
            args.text,
            font_index=args.font,
            variant=args.variant,
            output_mode=args.output,
        )
        sys.stdout.write(result)
    except (FileNotFoundError, IndexError, NotImplementedError) as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()