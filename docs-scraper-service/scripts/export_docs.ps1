# PowerShell скрипт для экспорта документации из Docker контейнера на локальный диск

$CONTAINER_NAME = "docs-scraper-service"
$LOCAL_EXPORT_DIR = ".\exported_docs"
$CONTAINER_DOCS_DIR = "/app/docs"
$VOLUME_NAME = "docs-scraper-service_docs_data"

Write-Host "📦 Экспорт документации из контейнера..." -ForegroundColor Cyan

# Проверяем, запущен ли контейнер
$containerRunning = docker ps --format '{{.Names}}' | Select-String -Pattern "^${CONTAINER_NAME}$"

if (-not $containerRunning) {
    Write-Host "⚠️  Контейнер ${CONTAINER_NAME} не запущен. Попытка экспорта из volume..." -ForegroundColor Yellow
    
    # Проверяем наличие volume
    $volumeExists = docker volume ls --format '{{.Name}}' | Select-String -Pattern "^${VOLUME_NAME}$"
    
    if ($volumeExists) {
        Write-Host "📂 Найден volume: ${VOLUME_NAME}" -ForegroundColor Green
        Write-Host "🔄 Создание временного контейнера для экспорта..." -ForegroundColor Cyan
        
        # Создаем директорию для экспорта
        New-Item -ItemType Directory -Force -Path $LOCAL_EXPORT_DIR | Out-Null
        
        # Создаем временный контейнер для доступа к volume
        $currentDir = (Get-Location).Path
        docker run --rm `
            -v "${VOLUME_NAME}:/source" `
            -v "${currentDir}:/destination" `
            alpine sh -c "cp -r /source/* /destination/exported_docs/ 2>/dev/null || echo 'Volume пуст или недоступен'"
        
        if (Test-Path $LOCAL_EXPORT_DIR -PathType Container) {
            $files = Get-ChildItem -Path $LOCAL_EXPORT_DIR -ErrorAction SilentlyContinue
            if ($files) {
                Write-Host "✅ Данные экспортированы в ${LOCAL_EXPORT_DIR}" -ForegroundColor Green
                Write-Host "📊 Содержимое:" -ForegroundColor Cyan
                Get-ChildItem -Path $LOCAL_EXPORT_DIR -Recurse | Select-Object Name, Length, LastWriteTime
            } else {
                Write-Host "❌ Директория пуста" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "❌ Не удалось создать директорию экспорта" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "❌ Volume ${VOLUME_NAME} не найден" -ForegroundColor Red
        exit 1
    }
} else {
    # Контейнер запущен, копируем из него
    Write-Host "📋 Копирование файлов из контейнера..." -ForegroundColor Cyan
    
    # Создаем директорию для экспорта
    New-Item -ItemType Directory -Force -Path $LOCAL_EXPORT_DIR | Out-Null
    
    # Копируем все файлы из контейнера
    docker cp "${CONTAINER_NAME}:${CONTAINER_DOCS_DIR}/." "${LOCAL_EXPORT_DIR}/"
    
    if (Test-Path $LOCAL_EXPORT_DIR -PathType Container) {
        $files = Get-ChildItem -Path $LOCAL_EXPORT_DIR -ErrorAction SilentlyContinue
        if ($files) {
            Write-Host "✅ Данные экспортированы в ${LOCAL_EXPORT_DIR}" -ForegroundColor Green
            Write-Host "📊 Содержимое:" -ForegroundColor Cyan
            Get-ChildItem -Path $LOCAL_EXPORT_DIR -Recurse | Select-Object Name, Length, LastWriteTime
        } else {
            Write-Host "❌ Директория пуста" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "❌ Не удалось экспортировать данные" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "✨ Экспорт завершен!" -ForegroundColor Green
Write-Host "📁 Локальная директория: $(Resolve-Path $LOCAL_EXPORT_DIR)" -ForegroundColor Cyan
