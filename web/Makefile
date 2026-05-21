.PHONY: help build up down restart logs clean test

help:
	@echo "ST3215 Robot Control - Make commands"
	@echo ""
	@echo "  make build     - Build Docker images"
	@echo "  make up       - Start services"
	@echo "  make down    - Stop services"
	@echo "  make restart - Restart services"
	@echo "  make logs    - View logs"
	@echo "  make clean   - Remove containers and volumes"
	@echo ""
	@echo "  make dev     - Run backend locally"
	@echo "  make dev-web - Run frontend locally"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

clean:
	docker-compose down -v

dev:
	python main.py --no-auth --mock

dev-web:
	cd frontend && npm run dev -- --port 5173