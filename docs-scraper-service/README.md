# 📚 Docs Scraper Service

Универсальный сервис для парсинга документации с веб-сайтов в формат Markdown.

## 🎯 Возможности

- ✅ Парсинг документации с любого сайта
- ✅ Конвертация HTML в Markdown
- ✅ REST API для управления
- ✅ CLI интерфейс
- ✅ Хранение по проектам
- ✅ Автоматическое создание индексов
- ✅ Фильтрация URL
- ✅ Ограничение глубины обхода

## 🚀 Быстрый старт

### Docker (рекомендуется)

```bash
cd docs-scraper-service

# Запуск сервиса
docker-compose up -d

# Проверка
curl http://localhost:8002/api/v1/scraper/health
```

### Локально

```bash
cd docs-scraper-service

# Установка зависимостей
pip install -r requirements.txt

# Установка браузеров Playwright
playwright install chromium

# Запуск API
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

## 📖 Использование

### REST API

#### Запуск парсинга

```bash
curl -X POST http://localhost:8002/api/v1/scraper/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://cursor.com/docs",
    "project_name": "cursor-docs",
    "url_filter": "/docs",
    "max_depth": 10,
    "follow_external": false
  }'
```

#### Список проектов

```bash
curl http://localhost:8002/api/v1/scraper/projects
```

#### Список файлов проекта

```bash
curl http://localhost:8002/api/v1/scraper/projects/cursor-docs/files
```

### CLI

#### Парсинг документации

```bash
# Внутри контейнера
docker exec -it docs-scraper-service python cli.py scrape \
  https://cursor.com/docs \
  --project cursor-docs \
  --filter /docs \
  --depth 10

# Локально
python cli.py scrape https://cursor.com/docs \
  --project cursor-docs \
  --filter /docs \
  --depth 10
```

#### Список проектов

```bash
docker exec -it docs-scraper-service python cli.py list-projects
```

#### Список файлов

```bash
docker exec -it docs-scraper-service python cli.py list-files cursor-docs
```

## 📁 Структура хранения

Документация сохраняется **напрямую на локальный диск** в структуре по проектам:

```
docs-scraper-service/
└── docs/                    # Локальная директория на вашем диске
    ├── cursor-docs/
    │   ├── INDEX.md
    │   ├── overview.md
    │   ├── quickstart.md
    │   └── ...
    ├── other-project/
    │   ├── INDEX.md
    │   └── ...
```

> **Примечание:** Данные сохраняются в `./docs/` относительно директории `docs-scraper-service`. Все файлы доступны напрямую на вашем локальном диске без необходимости экспорта из контейнера.

## 🔧 Конфигурация

Настройки можно изменить через переменные окружения или `.env` файл:

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8002

# Storage Configuration
DOCS_ROOT=/app/docs

# Scraper Configuration
DEFAULT_TIMEOUT=30000
DEFAULT_WAIT_TIME=1000
MAX_CONCURRENT=3

# Playwright Configuration
HEADLESS=true
VIEWPORT_WIDTH=1920
VIEWPORT_HEIGHT=1080
```

## 📝 Примеры использования

### Парсинг документации Cursor

```bash
curl -X POST http://localhost:8002/api/v1/scraper/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://cursor.com/docs",
    "project_name": "cursor-docs",
    "url_filter": "/docs",
    "max_depth": 10
  }'
```

### Парсинг другой документации

```bash
curl -X POST http://localhost:8002/api/v1/scraper/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://example.com/docs",
    "project_name": "example-docs",
    "url_filter": "/docs",
    "max_depth": 5
  }'
```

## 🛠 Технологии

- **FastAPI** — REST API
- **Playwright** — веб-скрапинг
- **Markdownify** — HTML → Markdown
- **Docker** — контейнеризация

## 📄 API Документация

После запуска сервиса доступна Swagger документация:
- http://localhost:8002/docs
- http://localhost:8002/redoc
