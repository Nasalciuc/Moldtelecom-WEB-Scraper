.PHONY: build run recon extract report login shell clean

# Собрать контейнер
build:
	docker compose build

# Полный pipeline
run:
	docker compose run --rm agent

# Только разведка
recon:
	docker compose run --rm agent --recon

# Только extraction
extract:
	docker compose run --rm agent --extract

# Только отчёт
report:
	docker compose run --rm agent --report

# Авторизация Claude CLI внутри контейнера
# ВАЖНО: запустить один раз перед первым использованием
login:
	docker compose run --rm agent bash -c "claude login"

# Shell для дебага
shell:
	docker compose run --rm --entrypoint bash agent

# Очистить output
clean:
	rm -f output/*.json output/*.html output/*.log output/*.md
