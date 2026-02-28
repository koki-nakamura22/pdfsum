"""python -m pdfsum でCLIを起動するためのエントリポイント"""

import sys

from pdfsum.cli.app import main

sys.exit(main())
