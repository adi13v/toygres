.PHONY: hard-reboot

hard-reboot:
	docker compose down -v
	docker compose up -d
	echo "Hard reboot complete. Run 'start' to start toygres."

start:
	uv run -m toygres.main
