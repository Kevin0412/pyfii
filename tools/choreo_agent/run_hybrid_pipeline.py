#!/usr/bin/env python3
"""Deprecated compatibility wrapper.

The old hybrid pipeline spliced hand-written fallback segments into design.py.
That is not a valid agent stability test. Use run_pipeline.py, which never
edits generated segments by hand and never force-locks failed segments.
"""

from run_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
