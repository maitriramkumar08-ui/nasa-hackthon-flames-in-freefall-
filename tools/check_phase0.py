"""
Is Phase 0 finished? Run from the project folder:

    python tools/check_phase0.py

Done means: every source has a url, access date and verifier, every decision
has a name in confirmed_by, and the ranking weights add up to 1.
The actual checks live in tools/phase0/.
"""

import sys

from phase0.cli import main

if __name__ == "__main__":
    sys.exit(main())
