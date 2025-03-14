# Решение тестового задания

---
### Соответствования требованиям

- Сервисы А и B написаны на фреймворке FastAPI
- В качестве брокера сообщений используется Redis(Redis Streams)
- Поддержка HTTPS за счёт самописных сертификатов, генерируемых в Dockerfile nginx
- Лишняя надёжность достигается засчёт хранения конфигураций и статусов в БД, а также удалением сообщений из потока брокера только после подтверждения consumer'а

### Навигация по репозиторию

- Репозиторий представляет из себя 4 ветки. Данная ветка - информативная, а каждая остальная ветка представляет собой исходный код каждого сервиса.

### Шаги сборки
1) Склонируйте проект
```
git clone --single-branch -b main https://github.com/sshumikhin/RTK-test.git
```

2) Создайте файл .env и заполните его по образцу .env.example
```
REDIS_HOST=redis #Оставить по умолчанию
REDIS_PORT=6379 #Оставить по умолчанию
SERVICE_A=service-a:7777 #Оставить по умолчанию
DB_USER=postgres
DB_PASS=Password1!
DB_NAME=service_b
DB_HOST=postgresql-db #Оставить по умолчанию
DB_PORT=5432 #Оставить по умолчанию
```

3) Соберите и запустите docker-compose
```
docker compose up --build
```
4) Выполните миграцию в сервисе B
```
docker exec -it service-b bash
alembic upgrade heads
exit
```
5) Сервис B доступен по адресу https://localhost:8000. Его документацию можно просмотреть на https://localhost:8000/docs

6) Сервис А доступен по адресу https://localhost:7777. Его документация доступна по адресу https://localhost:7777/docs


### Примечания
- Во время выполнения задачи многие моменты мне были не сразу понятны. 
Например, почему при 204 коде ответа в одном из API должен быть какой-то текст. Поэтому я допускаю, что мог ошибиться где-то и не понять, что от меня требовалось. Если будет представляться возможность уточнить детали и дать возможность исправить всё, то свяжитесь со [мной](https://t.me/username23465).
- Идей, касаемо улучшения проекта и безопасности очень много. Не хватает времени на реализацию.

### Из раздела "Будет плюсом"

1) [Схема взаимодействия сервисов](https://miro.com/app/board/uXjVLnXYpk4=/)
