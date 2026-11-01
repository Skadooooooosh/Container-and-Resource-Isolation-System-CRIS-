.PHONY: native test-native test-backend test frontend run-api run-ui doctor clean
native:        ; $(MAKE) -C native all
test-native:   ; $(MAKE) -C native test
test-backend:  native ; cd backend && python3 -m pytest -q tests
test:          test-native test-backend
frontend:      ; cd frontend && npm install && npm run build
run-api:       native ; cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
run-ui:        ; cd frontend && npm run dev
doctor:        native ; cd backend && python3 -m app.cli doctor
clean:         ; $(MAKE) -C native clean; rm -rf data frontend/dist
