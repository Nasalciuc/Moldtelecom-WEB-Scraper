# Moldtelecom AI Scraping Agent

> **Instrument de security assessment** pentru site-ul moldtelecom.md.  
> Анализирует защиту от скрапинга, перехватывает API и извлекает данные о тарифах.

---

## 📋 Ce face acest proiect / Что делает этот проект

**RO:** Agentul navighează site-ul Moldtelecom ca un browser real (stealth mode, fără flag `webdriver`),  
interceptează toate request-urile de rețea, identifică API endpoints interne și extrage datele despre  
abonamentele de telefonie mobilă. Generează un raport de securitate anti-scraping în Markdown.

**RU:** Агент открывает сайт Moldtelecom как настоящий браузер (stealth-режим, без флага `webdriver`),  
перехватывает все сетевые запросы, находит внутренние API endpoints и извлекает данные о тарифных планах.  
Генерирует security-отчёт в формате Markdown.

---

## 🚀 Quick Start

```bash
# 1. Клонировать / clonați
git clone <repo-url>
cd moldtelecom-agent

# 2. Установить зависимости / instalați dependințele
pip install -r requirements.txt

# 3. Установить Claude Code CLI (один раз)
npm install -g @anthropic-ai/claude-code
claude login   # откроется браузер → скопируйте Authentication Code → вставьте в терминал

# 4. Запустить / rulați
python src/agent.py
```

> **Note:** Claude CLI uses your Pro/Max plan — no API key needed, $0 extra cost.  
> Without Claude CLI the project still runs, but AI extraction degrades to regex fallback.

---

## 🐳 Docker (рекомендуется для команды)

Не нужно устанавливать Python, Chrome, Node.js — всё внутри контейнера.

### Первый запуск

```bash
# Собрать контейнер (один раз)
make build

# Авторизовать Claude CLI (один раз)
make login
# → откроется ссылка, скопируй Authentication Code, вставь в терминал

# Запустить полный pipeline
make run
```

### Команды

```bash
make run        # Полный pipeline (5 фаз)
make recon      # Только разведка + network interception
make extract    # Только extraction (нужны данные от recon)
make report     # Только генерация отчёта
make shell      # Открыть bash внутри контейнера для дебага
make clean      # Очистить output/
```

### Результаты

После `make run` все файлы появляются в `output/` на хосте:
- `anti_scraping_report.md` — отчёт
- `subscriptions_validated.json` — данные
- `recon_report.json` — найденные API
- `recon_*.html` — сохранённый HTML

### Заметки для команды

- Claude CLI авторизация хранится в Docker volume `moldtelecom-claude-auth` — переживает пересборку контейнера
- Output монтируется напрямую — файлы видны сразу на хосте
- Для работы вдвоём: один собирает `make build`, второй делает `git pull && make build` и всё работает

---

## 🏗️ Arhitectura / Архитектура

Pipline-ul are **5 faze** / Пайплайн состоит из **5 фаз**:

```
┌─────────────────────────────────────────────────────────┐
│  Phase 1: Sitemap Analysis                              │
│  sitemap_analyzer.py → output/sitemap_analysis.json    │
├─────────────────────────────────────────────────────────┤
│  Phase 2: Stealth Recon (Pydoll CDP browser)            │
│  recon.py → output/recon_*.html + recon_report.json    │
├─────────────────────────────────────────────────────────┤
│  Phase 3a: Direct API Extraction (aiohttp)              │
│  api_extractor.py → output/api_extraction.json         │
├─────────────────────────────────────────────────────────┤
│  Phase 3b: AI Extraction (Claude API, fallback)         │
│  ai_extractor.py → output/ai_extraction.json           │
├─────────────────────────────────────────────────────────┤
│  Phase 4: Cross-Validation                              │
│  validator.py → output/subscriptions_validated.json    │
├─────────────────────────────────────────────────────────┤
│  Phase 5: Report Generation                             │
│  report_generator.py → output/anti_scraping_report.md │
└─────────────────────────────────────────────────────────┘
```

---

## ▶️ Exemple de rulare / Примеры запуска

```bash
# Full pipeline (toate fazele / все фазы)
python src/agent.py

# Doar recon (faza 1+2) / только разведка
python src/agent.py --recon

# Doar extracție (faza 3) / только извлечение
python src/agent.py --extract

# Doar raport (faza 5) / только отчёт
python src/agent.py --report

# Bash wrapper (Linux/macOS)
bash run.sh --recon
```

---

## 📂 Fișierele output / Выходные файлы

| Fișier | Conținut |
|--------|----------|
| `output/recon_report.json` | Endpoints descoperite, semnale anti-bot |
| `output/recon_*.html` | HTML complet randat al fiecărei pagini |
| `output/sitemap_analysis.json` | Toate URL-urile din sitemap, categorizate |
| `output/api_extraction.json` | Date brute extrase din API endpoints |
| `output/ai_extraction.json` | Date extrase de Claude AI din HTML |
| `output/subscriptions_validated.json` | Date validate din ambele surse |
| `output/anti_scraping_report.md` | Raport final de securitate în Markdown |
| `output/agent_*.log` | Log-uri de execuție |

---

## 🛠️ Tech Stack

| Componentă | Tehnologie |
|------------|-----------|
| Stealth browser | [Pydoll](https://github.com/thalissonvs/pydoll) (CDP, fără webdriver flag) |
| AI extraction | [Claude Code CLI](https://github.com/anthropics/claude-code) (Pro/Max plan, no API key) |
| HTTP requests | [aiohttp](https://docs.aiohttp.org/) |
| Async runtime | Python `asyncio` |
| Data models | Python `dataclasses` |

---

## ⚙️ Configurare / Конфигурация

Toate setările sunt în `src/config.py`:

| Variabilă | Default | Descriere |
|-----------|---------|-----------|
| `REQUEST_DELAY_MIN` | 1.5s | Delay minim între requests |
| `REQUEST_DELAY_MAX` | 3.0s | Delay maxim între requests |
| `PAGE_LOAD_WAIT` | 4.0s | Extra wait după networkidle |
| `SCROLL_STEPS` | 5 | Pași de scroll pentru lazy loading |

---

## ⚠️ Disclaimer

Acest instrument este destinat exclusiv **security assessment intern**.  
Данный инструмент предназначен исключительно для **внутреннего security-аудита**.  
Utilizați responsabil și numai cu autorizație / Используйте ответственно и только с разрешением.
