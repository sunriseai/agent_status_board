.PHONY: dev test install-dev clear-events

dev:
	python3 server.py

test:
	python3 -m pytest

install-dev:
	python3 -m pip install -e ".[dev]"

clear-events:
	python3 clear_events.py
