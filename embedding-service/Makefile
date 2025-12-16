.PHONY: help build up down logs restart clean init-model test health

help: ## Показати цю довідку
	@echo "Доступні команди:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Збудувати Docker образи
	docker-compose build

up: ## Запустити сервіси в фоні
	docker-compose up -d

down: ## Зупинити сервіси
	docker-compose down

logs: ## Переглянути логи
	docker-compose logs -f embedding-service

restart: ## Перезапустити сервіси
	docker-compose restart

clean: ## Видалити контейнери та volumes
	docker-compose down -v

init-model: ## Завантажити EmbeddingGemma модель в Ollama
	docker exec embedding-ollama ollama pull embeddinggemma:latest
	@echo "Модель завантажена! Перевірка:"
	docker exec embedding-ollama ollama list

test: ## Перевірити health check
	curl -f http://localhost:8000/api/v1/health || echo "Сервіс не доступний"

health: ## Перевірити статус всіх сервісів
	docker-compose ps

dev: ## Запустити в development режимі з hot reload
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

shell: ## Відкрити shell в контейнері сервісу
	docker-compose exec embedding-service bash

ollama-shell: ## Відкрити shell в контейнері Ollama
	docker-compose exec ollama bash

