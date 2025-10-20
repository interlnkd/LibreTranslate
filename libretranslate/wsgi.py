import sys
from libretranslate.app import create_app
from libretranslate.main import parse_arguments

# Parse arguments using the main function's parser, but with no arguments
# This forces the creation of the default 'args' object needed by create_app
try:
    args = parse_arguments([])
    app = create_app(args)
except Exception as e:
    print(f"Error initializing LibreTranslate application: {e}", file=sys.stderr)
    sys.exit(1)