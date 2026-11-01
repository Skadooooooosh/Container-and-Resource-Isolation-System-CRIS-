
SHELL := /bin/bash

CRIS_ROOT := /home/inba/cris
PYTHON := .venv/bin/python
CRIS_NATIVE := $(CRIS_ROOT)/cris/native/build
PORT := 8000

.PHONY: help run test native frontend stop status

help:
	@echo "CRIS - Container and Resource Isolation System"
	@echo ""
	@echo "Available commands:"
	@echo "  make run       Start backend with cgroup delegation"
	@echo "  make stop      Stop backend"
	@echo "  make status    Check backend status"
	@echo "  make test      Run all backend tests"
	@echo "  make native    Build native C binaries"
	@echo "  make frontend  Start frontend development server"

run:
	@if ss -ltn | grep -q ':$(PORT) '; then \
		echo "CRIS backend is already running on port $(PORT)."; \
		echo "API docs: http://localhost:$(PORT)/docs"; \
	else \
		systemd-run --user --scope --expand-environment=no \
			-p Delegate=yes -- bash -c '\
				REL=$$(awk -F: '\''$$1=="0"{print $$3}'\'' /proc/self/cgroup); \
				export CRIS_CGROUP_BASE="/sys/fs/cgroup$$REL"; \
				export CRIS_NATIVE="$(CRIS_NATIVE)"; \
				exec $(CRIS_ROOT)/backend/$(PYTHON) \
				-m uvicorn app.main:app \
				--app-dir $(CRIS_ROOT)/backend \
				--host 0.0.0.0 --port $(PORT)'; \
	fi

stop:
	@if ! ss -ltn | grep -q ':$(PORT) '; then \
		echo "CRIS backend is not running."; \
	else \
		PID=$$(sudo lsof -ti tcp:$(PORT) -sTCP:LISTEN | head -n1); \
		if [ -n "$$PID" ]; then \
			echo "Stopping CRIS backend (PID $$PID)..."; \
			kill -TERM "$$PID"; \
		fi; \
	fi

status:
	@if ss -ltn | grep -q ':$(PORT) '; then \
		echo "CRIS backend is running."; \
		echo "API: http://localhost:$(PORT)"; \
		echo "Docs: http://localhost:$(PORT)/docs"; \
	else \
		echo "CRIS backend is stopped."; \
	fi

test:
	CRIS_NATIVE=$(CRIS_NATIVE) $(PYTHON) -m pytest -v

native:
	$(MAKE) -C $(CRIS_ROOT)/cris/native

frontend:
	cd $(CRIS_ROOT)/frontend && npm run dev -- --host 0.0.0.0

