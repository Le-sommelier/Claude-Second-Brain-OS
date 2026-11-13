.PHONY: sync check test scan validate

sync:      ## vendor lib/brainos into every plugin
	python3 scripts/sync_lib.py

check:     ## fail if a plugin's lib copy drifted
	python3 scripts/sync_lib.py --check

test:      ## run every module's tests
	@set -e; for d in tests/*/; do echo "== $$d"; python3 -m unittest discover -s "$$d" -t "$$d"; done

scan:      ## leak scan (needs a local .local/denylist.txt)
	python3 scripts/leak_scan.py

validate:  ## validate the marketplace and every plugin
	claude plugin validate .
