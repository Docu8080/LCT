"""Privacy records are explicit and account removal is confined to the reauthenticated owner."""

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from fastapi.testclient import TestClient


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_database = server.DB_PATH
        self.previous_demo = server.DEMO
        server.DB_PATH = Path(self.tmp.name) / "privacy.sqlite3"
        server.DEMO = True
        server.limiter.clear()
        self.client = TestClient(server.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        server.DB_PATH = self.previous_database
        server.DEMO = self.previous_demo
        self.tmp.cleanup()

    def login(self, email="candidate@demo.ru"):
        self.client.cookies.clear()
        response = self.client.post(
            "/api/auth/login", json={"email": email, "password": "Demo2026!"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        user = response.json()
        self.client.headers["X-CSRF-Token"] = user["csrf"]
        return user

    def test_required_acceptances_are_independent_and_strict(self):
        body = {
            "email": "new-privacy@demo.ru",
            "password": "Asecure2026!",
            "name": "Новый участник",
            "role": "candidate",
            "consent": True,
            "terms_accepted": True,
            "age_confirmed": True,
        }
        for field in ["consent", "terms_accepted", "age_confirmed"]:
            for value in [False, "true", 1]:
                invalid = body | {field: value}
                self.assertEqual(
                    self.client.post("/api/auth/register", json=invalid).status_code,
                    422,
                    (field, value),
                )
            missing = body.copy()
            missing.pop(field)
            self.assertEqual(
                self.client.post("/api/auth/register", json=missing).status_code, 422, field
            )
        response = self.client.post("/api/auth/register", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        response = self.client.post(
            "/api/auth/verify", json={"email": body["email"], "code": response.json()["dev_code"]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        privacy = self.client.get("/api/account/privacy").json()
        self.assertTrue(privacy["consent"]["accepted"])
        self.assertEqual(privacy["consent"]["version"], server.CONSENT_VERSION)
        self.assertEqual(privacy["consent"]["record_source"], "registration")
        self.assertTrue(privacy["terms"]["accepted"])
        self.assertEqual(privacy["terms"]["version"], server.TERMS_VERSION)
        self.assertTrue(privacy["age"]["confirmed"])
        self.assertEqual(privacy["consent"]["accepted_at"], privacy["terms"]["accepted_at"])
        self.assertEqual(privacy["age"]["confirmed_at"], privacy["terms"]["accepted_at"])
        self.assertFalse(privacy["marketing"]["enabled"])
        profile = self.client.get("/api/candidate/profile").json()
        self.assertFalse(profile["published"])
        self.assertFalse(profile["show_fsp"])

    def test_demo_acceptances_not_fabricated_and_opt_out_for_both_roles(self):
        for email in ["candidate@demo.ru", "hr@demo.ru"]:
            self.login(email)
            privacy = self.client.get("/api/account/privacy").json()
            self.assertEqual(privacy["consent"]["record_source"], "synthetic_demo")
            self.assertIsNone(privacy["consent"]["accepted_at"])
            self.assertFalse(privacy["terms"]["accepted"])
            self.assertFalse(privacy["age"]["confirmed"])
            self.assertFalse(privacy["marketing"]["enabled"])
            self.client.headers.pop("X-CSRF-Token")
            self.assertEqual(self.client.post("/api/account/marketing/opt-out").status_code, 403)
            self.login(email)
            response = self.client.post("/api/account/marketing/opt-out")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()["marketing_enabled"])
            self.assertEqual(
                self.client.get("/api/account/privacy").json()["marketing"]["opted_out_at"],
                response.json()["opted_out_at"],
            )

    def test_contact_disclosure_needs_a_boolean_acceptance(self):
        self.login()
        invitation = self.client.get("/api/invitations").json()[0]["id"]
        need = self.client.get("/api/jobs").json()[0]["id"]
        for value in ["true", 1]:
            response = self.client.patch(
                f"/api/invitations/{invitation}",
                json={"status": "accepted", "share_contacts": value},
            )
            self.assertEqual(response.status_code, 422, response.text)
            response = self.client.post(f"/api/jobs/{need}/apply", json={"share_contacts": value})
            self.assertEqual(response.status_code, 422, response.text)
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0], 0)

    def test_profile_exposure_controls_are_strict_and_off_by_default(self):
        self.login()
        profile = self.client.get("/api/candidate/profile").json()
        self.assertTrue(profile["published"])
        self.assertTrue(profile["show_fsp"])
        body = profile | {
            "phone": profile["contacts"]["phone"],
            "telegram": profile["contacts"]["telegram"],
        }
        body.pop("published")
        body.pop("show_fsp")
        response = self.client.put("/api/candidate/profile", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["published"])
        self.assertFalse(response.json()["show_fsp"])
        for field in ["published", "show_fsp"]:
            for value in ["true", 1]:
                response = self.client.put("/api/candidate/profile", json=body | {field: value})
                self.assertEqual(response.status_code, 422, response.text)
        response = self.client.put(
            "/api/candidate/profile", json=body | {"published": True, "show_fsp": True}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["published"])
        self.assertTrue(response.json()["show_fsp"])

    def test_operator_config_exposes_only_declared_public_values(self):
        keys = ["NAME", "INN", "OGRN", "ADDRESS", "EMAIL"]
        with patch.dict(os.environ, {"FSP_OPERATOR_" + key: "" for key in keys}):
            response = self.client.get("/api/legal/config")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["operator_configured"])
            self.assertEqual(data["operator"], {key.lower(): None for key in keys})
        values = {
            "NAME": " Тестовая организация\n",
            "INN": "7700000000",
            "OGRN": "1027700000000",
            "ADDRESS": "Москва, тестовый адрес",
            "EMAIL": "privacy@example.org",
        }
        public = {"FSP_OPERATOR_" + key: value for key, value in values.items()}
        with patch.dict(os.environ, public | {"FSP_SMTP_PASSWORD": "never-expose-this"}):
            data = self.client.get("/api/legal/config").json()
            self.assertTrue(data["operator_configured"])
            self.assertEqual(data["operator"]["name"], "Тестовая организация")
            self.assertNotIn("never-expose-this", str(data))
        with patch.dict(
            os.environ, {"FSP_OPERATOR_INN": "not-an-inn", "FSP_OPERATOR_EMAIL": "invalid"}
        ):
            data = self.client.get("/api/legal/config").json()
            self.assertIsNone(data["operator"]["inn"])
            self.assertIsNone(data["operator"]["email"])
            self.assertFalse(data["operator_configured"])

    def test_existing_database_migration_does_not_invent_acceptance(self):
        legacy_path = Path(self.tmp.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy_path)
        conn.executescript(server.SCHEMA)
        now = time.time()
        conn.execute(
            "INSERT INTO users(email,role,name,password,verified,consent_version,created) VALUES(?,?,?,?,1,?,?)",
            (
                "legacy@example.org",
                "employer",
                "Legacy",
                server.hash_password("Legacy2026!"),
                "2026-10-10-v1",
                now,
            ),
        )
        conn.commit()
        conn.close()
        active_path = server.DB_PATH
        server.DB_PATH = legacy_path
        server.DEMO = False
        try:
            server.initialize()
            server.initialize()
            with server.db() as conn:
                user = dict(conn.execute("SELECT * FROM users").fetchone())
                self.assertEqual(user["email"], "legacy@example.org")
                self.assertEqual(user["consent_version"], "2026-10-10-v1")
                self.assertEqual(user["acceptance_source"], "legacy")
                self.assertIsNone(user["consent_accepted_at"])
                self.assertIsNone(user["terms_accepted_at"])
                self.assertEqual(user["age_confirmed"], 0)
                self.assertEqual(user["marketing_enabled"], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        finally:
            server.DB_PATH = active_path
            server.DEMO = True

    def create_related_and_unrelated_content(self):
        user = self.login()
        cid = user["id"]
        task = self.client.get("/api/tasks").json()[0]
        response = self.client.post(
            f"/api/tasks/{task['id']}/answer",
            json={
                "answer": "Ключ идемпотентности хранится в транзакции; повтор возвращает результат."
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        need = self.client.get("/api/jobs").json()[0]["id"]
        response = self.client.post(f"/api/jobs/{need}/apply", json={"share_contacts": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.post(
            "/api/candidate/tests", json={"specialization": "frontend", "grade": "Junior"}
        )
        now = time.time()
        with server.db() as conn:
            hr = conn.execute("SELECT id FROM users WHERE email='hr@demo.ru'").fetchone()["id"]
            other_hr = conn.execute("SELECT id FROM users WHERE email='team@demo.ru'").fetchone()[
                "id"
            ]
            other_candidate = conn.execute(
                "SELECT id FROM users WHERE email='talent02@demo.ru'"
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO email_codes(user_id,code,expires) VALUES(?,?,?)",
                (cid, "pending", now + 60),
            )
            conn.execute(
                "INSERT INTO sessions VALUES(?,?,?,?)", ("another-session", cid, "csrf", now + 60)
            )
            other_need = conn.execute(
                "INSERT INTO needs(employer,data,published,created) VALUES(?,?,1,?)",
                (other_hr, '{"title":"Unrelated"}', now),
            ).lastrowid
            other_task = conn.execute(
                "INSERT INTO tasks(employer,data,created) VALUES(?,?,?)",
                (other_hr, '{"title":"Unrelated"}', now),
            ).lastrowid
            other_assignment = conn.execute(
                "INSERT INTO assignments(task,candidate,created,deadline,status,reason) VALUES(?,?,?,?,'assigned','unrelated')",
                (other_task, other_candidate, now, now + 60),
            ).lastrowid
            other_answer = conn.execute(
                "INSERT INTO task_answers(assignment,candidate,employer,answer,created) VALUES(?,?,?,?,?)",
                (other_assignment, other_candidate, other_hr, "Unrelated answer", now),
            ).lastrowid
            other_application = conn.execute(
                "INSERT INTO applications(need_id,candidate,employer,status,created) VALUES(?,?,?,'sent',?)",
                (other_need, other_candidate, other_hr, now),
            ).lastrowid
            conn.execute(
                "INSERT INTO grants(employer,candidate,created) VALUES(?,?,?)",
                (other_hr, other_candidate, now),
            )
            other_invitation = conn.execute(
                "INSERT INTO invitations(employer,candidate,data,status,created,updated) VALUES(?,?,?,'sent',?,?)",
                (other_hr, other_candidate, "{}", now, now),
            ).lastrowid
            server.notify(
                conn, other_hr, "Unrelated notification", "Keep me", related_user=other_candidate
            )
            other_notification = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            server.audit(conn, other_hr, "invitation.sent", other_invitation)
            other_audit = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {
            "candidate": cid,
            "hr": hr,
            "other_hr": other_hr,
            "other_candidate": other_candidate,
            "needs": other_need,
            "tasks": other_task,
            "assignments": other_assignment,
            "task_answers": other_answer,
            "applications": other_application,
            "invitations": other_invitation,
            "notifications": other_notification,
            "audit": other_audit,
        }

    def assert_deletion_confined_to_owner(self, email, key):
        records = self.create_related_and_unrelated_content()
        user = self.login(email)
        uid = user["id"]
        self.assertEqual(uid, records[key])
        self.client.headers.pop("X-CSRF-Token")
        response = self.client.request("DELETE", "/api/account", json={"password": "Demo2026!"})
        self.assertEqual(response.status_code, 403, response.text)
        user = self.login(email)
        response = self.client.request("DELETE", "/api/account", json={"password": "Wrong2026!"})
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        response = self.client.request(
            "DELETE", "/api/account", json={"password": "Demo2026!", "user_id": records["other_hr"]}
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        response = self.client.request("DELETE", "/api/account", json={"password": "Demo2026!"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"ok": True})
        self.assertNotIn("fsp_session", self.client.cookies)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/auth/login", json={"email": email, "password": "Demo2026!"}
            ).status_code,
            401,
        )
        with server.db() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone())
            self.assertEqual(list(conn.execute("PRAGMA foreign_key_check")), [])
            for table in [
                "profiles",
                "companies",
                "categories",
                "sessions",
                "email_codes",
                "attempts",
            ]:
                self.assertEqual(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (uid,)
                    ).fetchone()[0],
                    0,
                    table,
                )
            for table in ["applications", "invitations", "grants"]:
                self.assertEqual(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE candidate=? OR employer=?", (uid, uid)
                    ).fetchone()[0],
                    0,
                    table,
                )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM notifications WHERE user_id=? OR related_user=?",
                    (uid, uid),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM audit WHERE actor=?", (uid,)).fetchone()[0], 0
            )
            for table in [
                "needs",
                "tasks",
                "assignments",
                "task_answers",
                "applications",
                "invitations",
                "notifications",
                "audit",
            ]:
                self.assertIsNotNone(
                    conn.execute(
                        f"SELECT id FROM {table} WHERE id=?", (records[table],)
                    ).fetchone(),
                    table,
                )
            for preserved in ["other_hr", "other_candidate"]:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT id FROM users WHERE id=?", (records[preserved],)
                    ).fetchone()
                )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT user_id FROM companies WHERE user_id=?", (records["other_hr"],)
                ).fetchone()
            )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT user_id FROM profiles WHERE user_id=?", (records["other_candidate"],)
                ).fetchone()
            )
        self.login("team@demo.ru")
        self.assertEqual(self.client.get("/api/account/privacy").status_code, 200)

    def test_candidate_deletion_preserves_other_accounts_and_content(self):
        self.assert_deletion_confined_to_owner("candidate@demo.ru", "candidate")

    def test_employer_deletion_preserves_other_accounts_and_content(self):
        self.assert_deletion_confined_to_owner("hr@demo.ru", "hr")

    def test_revoked_accounts_can_reauthenticate_for_erasure_only(self):
        for email in ["candidate@demo.ru", "hr@demo.ru"]:
            user = self.login(email)
            response = self.client.post("/api/account/consent/revoke")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("fsp_session", self.client.cookies)
            self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
            self.assertEqual(
                self.client.post(
                    "/api/auth/login", json={"email": email, "password": "Demo2026!"}
                ).status_code,
                403,
            )
            body = {"email": email, "password": "Demo2026!"}
            self.assertEqual(self.client.post("/api/account/erasure", json=body).status_code, 403)
            self.assertEqual(
                self.client.post(
                    "/api/account/erasure", json=body, headers={"Origin": "https://foreign.example"}
                ).status_code,
                403,
            )
            wrong = self.client.post(
                "/api/account/erasure",
                json=body | {"password": "Wrong2026!"},
                headers={"Origin": "http://testserver"},
            )
            self.assertEqual(wrong.status_code, 401, wrong.text)
            with server.db() as conn:
                self.assertIsNotNone(
                    conn.execute("SELECT id FROM users WHERE id=?", (user["id"],)).fetchone()
                )
                if user["role"] == "employer":
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM needs WHERE employer=? AND published=1",
                            (user["id"],),
                        ).fetchone()[0],
                        0,
                    )
            response = self.client.post(
                "/api/account/erasure", json=body, headers={"Origin": "http://testserver"}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {"ok": True})
            with server.db() as conn:
                self.assertIsNone(
                    conn.execute("SELECT id FROM users WHERE id=?", (user["id"],)).fetchone()
                )
                self.assertEqual(list(conn.execute("PRAGMA foreign_key_check")), [])

    def test_public_erasure_cannot_delete_an_active_account_or_choose_id(self):
        user = self.login()
        self.client.cookies.clear()
        body = {"email": "candidate@demo.ru", "password": "Demo2026!"}
        active = self.client.post(
            "/api/account/erasure", json=body, headers={"Origin": "http://testserver"}
        )
        self.assertEqual(active.status_code, 401, active.text)
        unknown = self.client.post(
            "/api/account/erasure",
            json=body | {"email": "missing@example.org"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(unknown.status_code, 401, unknown.text)
        self.assertEqual(active.json(), unknown.json())
        self.assertEqual(
            self.client.post(
                "/api/account/erasure",
                json=body | {"user_id": user["id"]},
                headers={"Origin": "http://testserver"},
            ).status_code,
            422,
        )
        with server.db() as conn:
            self.assertIsNotNone(
                conn.execute("SELECT id FROM users WHERE id=?", (user["id"],)).fetchone()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
