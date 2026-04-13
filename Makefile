.PHONY: build run level1 level2 level3 validate report login shell clean

# Build container
build:
	docker compose build

# Full 4-level cascade
run:
	docker compose run --rm agent

# Run specific levels
level1:
	docker compose run --rm agent --level 1

level2:
	docker compose run --rm agent --level 2

level3:
	docker compose run --rm agent --level 3

# Only validation
validate:
	docker compose run --rm agent --validate

# Only report
report:
	docker compose run --rm agent --report

# Claude CLI login (one-time)
login:
	docker compose run --rm agent bash -c "claude login"

# Debug shell
shell:
	docker compose run --rm --entrypoint bash agent

# Clean output
clean:
	rm -f output/*.json output/*.html output/*.log output/*.md
