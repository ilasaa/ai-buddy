# Временный доступ команды через Cloudflare Quick Tunnel

Туннель автоматически не создаётся. Выполняйте команды самостоятельно только когда готовы
открыть демо. Перед этим замените стандартные пароли существующих demo-аккаунтов, задайте
случайный JWT_SECRET, проверьте отсутствие секретов во frontend и Git. Изменение DEMO_PASSWORD
не сбрасывает пароли уже созданных аккаунтов. UI смены пароля в прототипе отсутствует.

1. Запустите приложение через Compose, убедитесь, что localhost:8080 работает.
2. При установленном cloudflared выполните:

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

3. Полученную точную HTTPS-ссылку внесите в `.env`:

```dotenv
ALLOWED_ORIGINS=["https://your-random-name.trycloudflare.com"]
COOKIE_SECURE=true
```

4. Пересоздайте backend:

```bash
sudo docker compose up -d --no-deps --force-recreate backend
```

5. Откройте HTTPS-ссылку заново, войдите и проверьте подготовку/подтверждение заявки.
Cookie HttpOnly, Secure, SameSite=Lax; frontend использует относительный `/api`.
Origin браузера сохраняется через Nginx и проверяется backend вместе с X-Requested-With.
API не использует X-Forwarded-Proto для проверки CSRF; Secure задаётся настройкой, поэтому
локальный HTTP между cloudflared и Nginx не требует отключения защиты.
Не добавляйте wildcard Origins. Не открывайте порт 5432: в Compose он привязан только к loopback,
backend также не опубликован напрямую. Туннелируйте только frontend.

Quick Tunnel меняет адрес при повторном запуске: обновите ALLOWED_ORIGINS и пересоздайте backend.
При ошибке 403 проверьте точное совпадение Origin и заголовок; при 401 — повторите вход по HTTPS.
Не отключайте CSRF. Для возврата к локальному HTTP задайте COOKIE_SECURE=false и локальные
ALLOWED_ORIGINS, пересоздайте backend. Остановка cloudflared закрывает временный доступ.

Внешний HTTPS и Cloudflare этой итерации не проверены. Quick Tunnel — временная демонстрация,
не production-развёртывание и не ограничение доступа приглашениями: ссылка публична.
