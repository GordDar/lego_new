Этот README описывает, как собрать Docker-образ, загрузить его в Google Artifact Registry

---

## Шаг 1. Авторизация и настройка Docker для Google Cloud

```bash
gcloud auth login
gcloud auth configure-docker europe-central2-docker.pkg.dev
```
Эти команды авторизуют вас в Google Cloud и настраивают Docker для работы с Artifact Registry.

## Шаг 2. Сборка Docker-образа
```bash
docker buildx build --platform linux/amd64 -t europe-central2-docker.pkg.dev/lego-bricks-app/backend-app/lego-bricks:latest .
```
--platform linux/amd64 — гарантирует совместимость образа с архитектурой Cloud Run.

-t — тег образа с указанием пути в Artifact Registry.

## Шаг 3. Публикация Docker-образа в Artifact Registry
```bash
docker push europe-central2-docker.pkg.dev/lego-bricks-app/backend-app/lego-bricks:latest
```
Образ загрузится в указанный репозиторий Google Artifact Registry.

## Шаг 4. Развернуть образ в Google cloud