# Короткие команды для Linux/macOS. На Windows используйте те же команды Python из README.
PYTHON ?= python

.PHONY: build reports test

build:
	$(PYTHON) -m pipeline build

reports:
	$(PYTHON) scripts/build_reports.py

test:
	$(PYTHON) -m pytest
