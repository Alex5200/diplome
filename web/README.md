# ST3215 Robot Control API

Веб-интерфейс управления 6-осевым манипулятором ST3215.

## Быстрый старт

### Docker (рекомендуется)

```bash
# Клонирование репозитория
git clone https://github.com/yourrepo/diplome.git
cd diplome/web

# Запуск с Docker Compose
cp .env.example .env
# Отредактируйте .env файл

docker-compose up -d
```

### Локальная разработка

```bash
# Установка зависимостей
pip install -e .
npm install --prefix frontend

# Запуск бэкенда
python main.py --no-auth --mock

# Запуск фронтенда (в другом терминале)
npm run dev --prefix frontend
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|--------------|
| `JWT_SECRET` | Секретный ключ для JWT | change-me-in-production |
| `JWT_ALGO` | Алгоритм HS256 | HS256 |
| `TOKEN_EXP_H` | Время жизни токена (часы) | 24 |
| `ADMIN_PASSWORD` | Пароль администратора | admin |
| `OPERATOR_PASSWORD` | Пароль оператора | operator |
| `AUTH_ENABLED` | Включить авторизацию | true |
| `MOCK_MODE` | Использовать мок-контроллер | false |
| `NO_AUTH_SECRET` | Секрет для ограниченного доступа | - |

## Запуск

### Режим разработки (без робота)
```bash
python main.py --no-auth --mock
```

### Продакшен
```bash
python main.py
```

### Docker
```bash
docker-compose up -d
```

## API Endpoints

### Публичные
- `GET /api/status` - Статус робота
- `POST /auth/login` - Авторизация

### Защищенные
- `POST /api/connect` - Подключение к роботу
- `POST /api/disconnect` - Отключение
- `POST /api/move` - Движение сустава
- `POST /api/move_all` - Движение всех суставов
- `POST /api/stop` - Аварийная остановка
- `POST /api/torque` - Управление моментом
- `POST /api/ik` - Инверсная кинематика

## Веб-интерфейс

Откройте http://localhost:3000 в браузере.

### Управление
- Логин: `admin`
- Пароль: `admin` (по умолчанию)

## WebSocket

Подключение к `/ws` для получения телеметрии в реальном времени.

## Безопасность

1. Всегда меняйте `JWT_SECRET` в продакшене
2. Используйте сложные пароли
3. Запускайте за файрволом
4. Используйте HTTPS в продакшене