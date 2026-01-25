#!/bin/bash
# Скрипт для экспорта документации из Docker контейнера на локальный диск

set -e

CONTAINER_NAME="docs-scraper-service"
LOCAL_EXPORT_DIR="./exported_docs"
CONTAINER_DOCS_DIR="/app/docs"

echo "📦 Экспорт документации из контейнера..."

# Проверяем, запущен ли контейнер
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "⚠️  Контейнер ${CONTAINER_NAME} не запущен. Попытка экспорта из volume..."
    
    # Пытаемся экспортировать из volume напрямую
    VOLUME_NAME="docs-scraper-service_docs_data"
    if docker volume ls --format '{{.Name}}' | grep -q "^${VOLUME_NAME}$"; then
        echo "📂 Найден volume: ${VOLUME_NAME}"
        echo "🔄 Создание временного контейнера для экспорта..."
        
        # Создаем временный контейнер для доступа к volume
        docker run --rm \
            -v ${VOLUME_NAME}:/source \
            -v $(pwd):/destination \
            alpine sh -c "cp -r /source/* /destination/${LOCAL_EXPORT_DIR}/ 2>/dev/null || echo 'Volume пуст или недоступен'"
        
        if [ -d "${LOCAL_EXPORT_DIR}" ] && [ "$(ls -A ${LOCAL_EXPORT_DIR} 2>/dev/null)" ]; then
            echo "✅ Данные экспортированы в ${LOCAL_EXPORT_DIR}"
        else
            echo "❌ Не удалось экспортировать данные из volume"
            exit 1
        fi
    else
        echo "❌ Volume ${VOLUME_NAME} не найден"
        exit 1
    fi
else
    # Контейнер запущен, копируем из него
    echo "📋 Копирование файлов из контейнера..."
    mkdir -p "${LOCAL_EXPORT_DIR}"
    
    # Копируем все файлы из контейнера
    docker cp "${CONTAINER_NAME}:${CONTAINER_DOCS_DIR}/." "${LOCAL_EXPORT_DIR}/"
    
    if [ -d "${LOCAL_EXPORT_DIR}" ] && [ "$(ls -A ${LOCAL_EXPORT_DIR} 2>/dev/null)" ]; then
        echo "✅ Данные экспортированы в ${LOCAL_EXPORT_DIR}"
        echo "📊 Содержимое:"
        ls -lh "${LOCAL_EXPORT_DIR}"
    else
        echo "❌ Не удалось экспортировать данные"
        exit 1
    fi
fi

echo ""
echo "✨ Экспорт завершен!"
echo "📁 Локальная директория: $(pwd)/${LOCAL_EXPORT_DIR}"
