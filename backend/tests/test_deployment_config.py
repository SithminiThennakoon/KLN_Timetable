import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.routing import APIRoute

TEST_DB_FILE = Path(tempfile.gettempdir()) / "kln_timetable_deployment_tests.sqlite"
TEST_ENV = {
    "DATABASE_URL": f"sqlite:///{TEST_DB_FILE}",
    "APP_ENV": "test",
}
for key, value in TEST_ENV.items():
    os.environ[key] = value


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import build_engine, engine  # noqa: E402
from app.main import create_app  # noqa: E402


class DeploymentConfigTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        engine.dispose()

    def test_build_engine_prepares_sqlite_parent_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "nested" / "app.db"
            engine = build_engine(f"sqlite:///{db_path}")

            self.assertEqual(engine.url.get_backend_name(), "sqlite")
            self.assertTrue(db_path.parent.exists())
            engine.dispose()

    def test_health_endpoint_returns_status_payload(self):
        app = create_app()
        route = next(
            route
            for route in app.router.routes
            if isinstance(route, APIRoute) and route.path == "/health"
        )
        response = route.endpoint()

        self.assertEqual(response["status"], "ok")
        self.assertIn("environment", response)

    def test_cors_middleware_uses_configured_allowlist(self):
        with patch.object(settings, "CORS_ALLOWED_ORIGINS", ["https://frontend.example.com"]):
            app = create_app()
            cors_middleware = next(
                middleware
                for middleware in app.user_middleware
                if middleware.cls.__name__ == "CORSMiddleware"
            )

            self.assertEqual(
                cors_middleware.kwargs.get("allow_origins"),
                ["https://frontend.example.com"],
            )
