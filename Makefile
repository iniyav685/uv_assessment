.PHONY: up down logs build test test-backend test-frontend seed reseed migrate shell lint

up:            ## Build and start backend services (db, redis, s3, backend, worker, worker-notifications, beat)
	docker compose up --build

down:          ## Stop backend services
	docker compose down

logs:          ## Follow API + worker logs
	docker compose logs -f backend worker worker-notifications

migrate:
	docker compose exec backend python manage.py migrate

seed:          ## Load sample data (idempotent)
	docker compose exec backend python manage.py seed_data

reseed:        ## Regenerate all sample tickets
	docker compose exec backend python manage.py seed_data --reset

shell:
	docker compose exec backend python manage.py shell

test: test-backend test-frontend

test-backend:
	docker compose exec backend pytest

test-frontend:
	cd frontend && npm test

lint:
	docker compose exec backend ruff check .
	cd frontend && npm run lint
