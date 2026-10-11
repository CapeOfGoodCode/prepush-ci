"""`python -m prepush_ci`: how hooks and integration tests start the CLI (coverage follows it)."""

from prepush_ci.cli import main

raise SystemExit(main())
