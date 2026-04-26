# Makefile for robotics stack

.PHONY: help build test validate clean logs restart deploy

help:
	@echo "Robotics Stack Commands:"
	@echo "  make build          - Build all Docker containers"
	@echo "  make test           - Run validation tests"
	@echo "  make validate       - Run validation checks"
	@echo "  make clean          - Remove Docker containers and volumes"
	@echo "  make logs           - Show container logs"
	@echo "  make restart        - Restart all containers"
	@echo "  make deploy         - Deploy to production"

build:
	docker compose build --no-cache

test:
	docker compose run --rm shared python -c "import sys; print('Shared: OK')"
	docker compose run --rm ros2_sim python -c "import sys; print('ROS2: OK')"
	docker compose run --rm mujoco_sim python -c "import sys; print('MuJoCo: OK')"
	docker compose run --rm backend python -c "import sys; print('Backend: OK')"

validate:
	docker compose config
	docker compose run --rm shared python -m py_compile -v /app/shared
	docker compose run --rm ros2_sim python -m py_compile -v /root/src
	docker compose run --rm mujoco_sim python -m py_compile -v /root/src/mujoco_sim
	docker compose run --rm backend python -m py_compile -v /app
	docker compose run --rm backend python -c "import sys; print('Backend compile: OK')"

clean:
	docker compose down -v

logs:
	docker compose logs -f

restart:
	docker compose restart

deploy:
	docker compose up -d --build
