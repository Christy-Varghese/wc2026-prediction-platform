# WC2026 Prediction Platform — common development commands
# Usage: make <target>

BACKEND  = backend
FRONTEND = frontend
ML       = backend/ml
PYTHON   = python3

.PHONY: help dev-frontend dev-backend dev sim snapshots test validate \
        ingest-scores open-site install lint

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  make dev-frontend   Start Next.js dev server on :3000"
	@echo "  make dev-backend    Start FastAPI dev server on :8000"
	@echo "  make dev            Start both frontend + backend"
	@echo ""
	@echo "  make sim            Re-run Monte Carlo simulation (50k)"
	@echo "  make snapshots      Regenerate all frontend JSON snapshots"
	@echo "  make ingest-scores  sim + snapshots in one step (after adding scores)"
	@echo ""
	@echo "  make test           Run all backend + ML tests"
	@echo "  make validate       Validate live API (backend must be on :8000)"
	@echo "  make install        Install backend Python deps"
	@echo "  make open-site      Open the frontend in the browser"
	@echo ""

# ── Dev servers ───────────────────────────────────────────────────────────────
dev-frontend:
	cd $(FRONTEND) && npm run dev

dev-backend:
	cd $(BACKEND) && uvicorn app.main:app --reload --port 8000

dev:
	@echo "Starting backend on :8000 and frontend on :3000 …"
	@cd $(BACKEND) && uvicorn app.main:app --reload --port 8000 &
	@cd $(FRONTEND) && npm run dev

# ── Data pipeline ─────────────────────────────────────────────────────────────
sim:
	@echo "Running simulation …"
	cd $(ML) && $(PYTHON) simulate.py

snapshots:
	@echo "Regenerating snapshots …"
	cd $(BACKEND) && $(PYTHON) gen_snapshots.py

ingest-scores: sim snapshots
	@echo "Done — scores ingested, sim updated, snapshots regenerated."

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	@echo "Running backend API tests …"
	cd $(BACKEND) && $(PYTHON) -m pytest tests/ -q
	@echo "Running ML tests …"
	cd $(ML) && $(PYTHON) -m pytest tests/ -q

# ── Validation ────────────────────────────────────────────────────────────────
validate:
	cd $(BACKEND) && $(PYTHON) validate_api.py

# ── Install ───────────────────────────────────────────────────────────────────
install:
	cd $(FRONTEND) && npm install
	pip3 install -r $(BACKEND)/requirements.txt

# ── Utility ───────────────────────────────────────────────────────────────────
open-site:
	open http://localhost:3000

lint:
	cd $(FRONTEND) && npm run lint
