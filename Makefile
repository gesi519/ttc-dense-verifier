PYTHON ?= python3
PYTHONPATH ?= src
REMOTE_PROJECT_DIR ?= /srv/ttc-dense-verifier
REMOTE_RUNBOOK_DIR ?= scripts/remote_deploy/generated
VERIFY_REMOTE_RUNBOOK_DIR ?= /tmp/ttc-dense-verifier-remote-runbook
SMOKE_OUTPUT_DIR ?= /tmp/ttc-dense-verifier-local-smoke

.PHONY: help test compile smoke remote-runbook remote-runbook-check verify clean-smoke

help:
	@echo "Targets:"
	@echo "  test            Run unit tests"
	@echo "  compile         Compile src and tests"
	@echo "  smoke           Run local no-model smoke workflow"
	@echo "  remote-runbook  Export remote deployment runbook"
	@echo "  remote-runbook-check Export runbook to /tmp for verification"
	@echo "  verify          Run test, compile, smoke, and remote-runbook"
	@echo "  clean-smoke     Remove local smoke outputs"

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

compile:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall -q src tests

smoke:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m ttc_dense_verifier.cli run-local-smoke --output-dir $(SMOKE_OUTPUT_DIR) --limit 12

remote-runbook:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m ttc_dense_verifier.cli export-remote-runbook --output-dir $(REMOTE_RUNBOOK_DIR) --remote-project-dir $(REMOTE_PROJECT_DIR)

remote-runbook-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m ttc_dense_verifier.cli export-remote-runbook --output-dir $(VERIFY_REMOTE_RUNBOOK_DIR) --remote-project-dir $(REMOTE_PROJECT_DIR)

verify: test compile smoke remote-runbook-check

clean-smoke:
	rm -rf $(SMOKE_OUTPUT_DIR)
