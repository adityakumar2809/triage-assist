# Local setup and run steps (executed in B10)

1. `python3 -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. `flask --app app.web.app:create_app run --host 127.0.0.1 --port 5010`
5. Open `http://127.0.0.1:5010` and exercise intake -> confirmation -> result.
6. `pytest -q` for full conventional suite.
