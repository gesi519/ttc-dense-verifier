PYTHON ?= python3
PYTHONPATH ?= src
REMOTE_HOST ?= g3
REMOTE_PROJECT_DIR ?= /data/lry_machine_learning/ttc_dense_verifier
REMOTE_RUNBOOK_DIR ?= scripts/remote_deploy/generated
VERIFY_REMOTE_RUNBOOK_DIR ?= /tmp/ttc-dense-verifier-remote-runbook
SMOKE_OUTPUT_DIR ?= /tmp/ttc-dense-verifier-local-smoke

.PHONY: help test compile smoke remote-runbook remote-runbook-check remote-sync remote-status remote-env-check remote-health remote-jobs verify clean-smoke

help:
	@echo "Targets:"
	@echo "  test            Run unit tests"
	@echo "  compile         Compile src and tests"
	@echo "  smoke           Run local no-model smoke workflow"
	@echo "  remote-runbook  Export remote deployment runbook"
	@echo "  remote-runbook-check Export runbook to /tmp for verification"
	@echo "  remote-sync     Sync source tree to REMOTE_HOST:REMOTE_PROJECT_DIR"
	@echo "  remote-status   Check remote GPU, directory, and git state"
	@echo "  remote-env-check Check remote generated .env before health/jobs"
	@echo "  remote-health   Run generated remote health check"
	@echo "  remote-jobs     Run generated ordered remote jobs"
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

remote-sync:
	ssh $(REMOTE_HOST) 'mkdir -p "$(REMOTE_PROJECT_DIR)"'
	COPYFILE_DISABLE=1 tar --no-xattrs -czf - \
		--exclude ./.git \
		--exclude ./checkpoints \
		--exclude ./outputs/logs \
		--exclude ./scripts/remote_deploy/generated/.env \
		. | ssh $(REMOTE_HOST) 'tar -xzf - -C "$(REMOTE_PROJECT_DIR)"'

remote-status:
	ssh $(REMOTE_HOST) 'nvidia-smi && cd "$(REMOTE_PROJECT_DIR)" && pwd && if [ -d .git ]; then git status --short; else echo "[status] not a git checkout; synced artifact tree"; fi'

remote-env-check:
	ssh $(REMOTE_HOST) 'cd "$(REMOTE_PROJECT_DIR)" && bash scripts/remote_deploy/generated/env_check.sh'

remote-health: remote-env-check
	ssh $(REMOTE_HOST) 'cd "$(REMOTE_PROJECT_DIR)" && set -a && source scripts/remote_deploy/generated/.env && set +a && bash scripts/remote_deploy/generated/health_check.sh'

remote-jobs: remote-env-check
	ssh $(REMOTE_HOST) 'cd "$(REMOTE_PROJECT_DIR)" && set -a && source scripts/remote_deploy/generated/.env && set +a && bash scripts/remote_deploy/generated/run_remote_jobs.sh'

verify: test compile smoke remote-runbook-check

clean-smoke:
	rm -rf $(SMOKE_OUTPUT_DIR)
