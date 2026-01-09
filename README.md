# Binance Futures Long/Short Daily Reporter

Python-скрипт, который раз в день получает с Binance Futures (USDT-margined) три метрики по заданным парам и отправляет отчёт в Telegram:
- Top Trader Long/Short Ratio (Accounts) 1d
- Top Trader Long/Short Ratio (Positions) 1d
- Global Long/Short Ratio 1d

Запуск по расписанию настроен через GitHub Actions (cron `0 6 * * *`, что соответствует 09:00 Europe/Moscow).

## Требования
- Python 3.11+
- `TELEGRAM_BOT_TOKEN` в окружении (не храните его в репозитории)

## Настройка конфигурации
1) Скопируйте шаблон:
```bash
cp config/settings.example.json config/settings.json
```
2) Укажите пары и `telegram_chat_id` (числовой ID получателя или группового чата).

Альтернатива: можно не создавать `settings.json`, а задать переменные окружения:
- `PAIRS` — список пар через запятую, например `BTCUSDT,ETHUSDT`
- `TELEGRAM_CHAT_ID` — ID чата

Всегда требуется `TELEGRAM_BOT_TOKEN` в окружении.

## Запуск локально
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

## Запуск по расписанию (GitHub Actions)
1) В репозитории создайте Secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2) (Опционально) создайте Repository Variable `PAIRS`, например `BTCUSDT,ETHUSDT`.
3) Workflow лежит в `.github/workflows/daily.yml` и по умолчанию срабатывает в 06:00 UTC (09:00 Europe/Moscow). Можно запустить вручную через `workflow_dispatch`.

## Как получить Bot Token и Chat ID
- Создайте бота у [@BotFather](https://t.me/BotFather) и возьмите `TELEGRAM_BOT_TOKEN`.
- Добавьте бота в нужный чат/группу и отправьте любое сообщение.
- Узнайте `TELEGRAM_CHAT_ID`: переслать сообщение боту `@userinfobot` или вызвать Telegram Bot API `getUpdates`.

## Что делает скрипт
- Берёт список пар и chat id из `config/settings.json` или env (`PAIRS`, `TELEGRAM_CHAT_ID`).
- Запрашивает у Binance публичные endpoints c периодом `1d`:
  - `/futures/data/topLongShortAccountRatio`
  - `/futures/data/topLongShortPositionRatio`
  - `/futures/data/globalLongShortAccountRatio`
- Формирует сообщение с % long/short и отношением `longShortRatio`.
- Отправляет текст через Telegram Bot API (`sendMessage`).

Примечание: в GitHub Actions некоторые регионы могут получать 451 без `User-Agent`, он уже добавлен в код. При необходимости можно задать зеркальный `BINANCE_BASE_URL` через переменные окружения.

## Переменные окружения
- `TELEGRAM_BOT_TOKEN` (обязательная)
- `TELEGRAM_CHAT_ID` (обязательная, если не указана в config)
- `PAIRS` (опционально, переопределяет пары из config)

## Отладка
- Если запрос к Binance вернул пустой ответ, скрипт завершится с ошибкой.
- Убедитесь, что пара торгуется на USDT Perpetual Futures и введена в верхнем регистре (например, `BTCUSDT`).
