#!/usr/bin/env sh
set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH= cd -- "$script_directory/.." && pwd)

cd "$project_root"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker bulunamadı. Docker Desktop veya Docker Engine kurup yeniden deneyin." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker çalışmıyor. Docker'ı başlatıp yeniden deneyin." >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "[setup] .env.example dosyasından .env oluşturuldu."
else
    echo "[setup] Mevcut .env korundu."
fi

echo "[setup] Compose yapılandırması doğrulanıyor..."
docker compose --env-file .env config --quiet

echo "[setup] Servisler build edilip başlatılıyor..."
docker compose --env-file .env up --detach --build --wait --wait-timeout 300

echo "[setup] Veritabanı migration'ları uygulanıyor..."
docker compose --env-file .env exec --no-TTY api alembic upgrade head

echo "[setup] Web ekranından kullanıcı hesabı oluşturabilirsiniz."
echo "[setup] Admin için: docker compose exec api python -m intihal_api.db.manage_user EMAIL --name NAME --role admin"

echo "[setup] Sentetik örnek kaynak havuzu hazırlanıyor..."
docker compose --env-file .env exec --no-TTY api python -m intihal_api.corpus.sample_seed

docker compose --env-file .env ps

printf '\nKurulum tamamlandı.\n'
printf 'Web:           http://localhost:3000\n'
printf 'API health:    http://localhost:8000/health\n'
printf 'MinIO paneli:  http://localhost:9001\n'
