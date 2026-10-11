import io
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas


class IdeasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(self.tmp.name) / "test.sqlite3"
        server.limiter.clear()
        self.client = TestClient(server.app)
        self.client.__enter__()
        self.other = TestClient(server.app)

    def tearDown(self):
        self.other.close()
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def demo(self, client, role="candidate", reset=False):
        r = client.post(
            "/api/auth/demo",
            json={"role": role, "reset": reset},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        user = r.json()
        client.headers["X-CSRF-Token"] = user["csrf"]
        return user

    def pdf(self, text="Python FastAPI PostgreSQL SQL Docker", pages=1):
        stream = io.BytesIO()
        canvas = Canvas(stream)
        for _ in range(pages):
            canvas.drawString(30, 800, text)
            canvas.showPage()
        canvas.save()
        return stream.getvalue()

    def preview(self, content):
        return self.client.post(
            "/api/candidate/resume/preview",
            content=content,
            headers={"Content-Type": "application/pdf"},
        )

    def test_browser_roles_contacts_reset_and_isolation(self):
        a = self.demo(self.client)
        b = self.demo(self.other)
        self.assertNotEqual(a["id"], b["id"])
        cookie = self.client.cookies.get("fsp_demo_pair")
        invitation = self.client.get("/api/invitations").json()[0]["id"]
        self.assertEqual(
            self.client.patch(
                f"/api/invitations/{invitation}",
                json={"status": "accepted", "share_contacts": True},
            ).status_code,
            200,
        )
        hr = self.demo(self.client, "employer")
        other_hr = self.demo(self.other, "employer")
        self.assertEqual(self.client.cookies.get("fsp_demo_pair"), cookie)
        self.assertTrue(
            self.client.get(f"/api/employer/candidates/{a['id']}").json()["contacts_open"]
        )
        self.assertEqual(self.other.get(f"/api/employer/candidates/{a['id']}").status_code, 404)
        self.assertEqual(
            [p["id"] for p in self.other.get("/api/employer/candidates").json()["candidates"]],
            [b["id"]],
        )
        self.assertEqual(
            self.other.patch(
                f"/api/invitations/{invitation}", json={"status": "withdrawn"}
            ).status_code,
            404,
        )
        self.assertNotEqual(self.client.get("/api/jobs").json()[0]["employer"], other_hr["id"])
        new = self.demo(self.client, "candidate", True)
        self.assertNotEqual(new["id"], a["id"])
        self.assertEqual(self.client.get("/api/invitations").json()[0]["status"], "sent")
        self.assertEqual(self.demo(self.other, "candidate")["id"], b["id"])
        with server.db() as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM users WHERE id=?", (a["id"],)).fetchone())
            self.assertFalse(
                conn.execute("SELECT 1 FROM sessions WHERE user_id=?", (hr["id"],)).fetchone()
            )

    def test_demo_tasks_jobs_and_cross_scope_writes(self):
        a = self.demo(self.client)
        self.demo(self.other)
        own_tasks = self.client.get("/api/tasks").json()
        self.assertEqual(len(own_tasks), 1)
        self.assertEqual(
            self.client.post(
                f"/api/tasks/{own_tasks[0]['id']}/answer",
                json={
                    "answer": "Ключ идемпотентности хранится в транзакции; повтор возвращает результат."
                },
            ).status_code,
            200,
        )
        own_job = self.client.get("/api/jobs").json()[0]
        self.assertEqual(
            self.other.post(
                f"/api/jobs/{own_job['id']}/apply", json={"share_contacts": True}
            ).status_code,
            404,
        )
        hr = self.demo(self.client, "employer")
        self.assertEqual(len(self.client.get("/api/tasks").json()[0]["submissions"]), 1)
        other_hr = self.demo(self.other, "employer")
        self.assertEqual(self.other.get("/api/tasks").json()[0]["submissions"], [])
        body = {
            "candidate_id": a["id"],
            "title": "Python Developer",
            "description": "Работа в продуктовой команде над API",
            "salary_from": 100000,
            "salary_to": 200000,
            "contact": "hr@example.org",
            "work_format": "remote",
        }
        self.assertEqual(self.other.post("/api/employer/invitations", json=body).status_code, 404)
        self.assertNotEqual(hr["id"], other_hr["id"])

    def test_demo_guards_expiry_and_new_candidate(self):
        self.assertEqual(
            self.client.post("/api/auth/demo", json={"role": "candidate"}).status_code, 403
        )
        with patch.object(server, "DEMO", False):
            self.assertEqual(
                self.client.post("/api/auth/demo", json={"role": "candidate"}).status_code, 404
            )
        user = self.demo(self.client, "fresh")
        self.assertEqual(self.client.get("/api/candidate/profile").json()["categories"], [])
        self.client.headers.pop("X-CSRF-Token")
        self.assertEqual(
            self.client.post(
                "/api/auth/demo", json={"role": "employer"}, headers={"Origin": "http://testserver"}
            ).status_code,
            403,
        )
        self.client.headers["X-CSRF-Token"] = user["csrf"]
        with server.db() as conn:
            conn.execute("UPDATE demo_pairs SET expires=?", (time.time() - 1,))
        new = self.demo(self.client, "fresh")
        self.assertNotEqual(new["id"], user["id"])
        self.assertTrue(new["browser_demo"])

    def test_demo_sessions_cannot_outlive_the_scenario(self):
        self.demo(self.client)
        expires = time.time() + 20
        with server.db() as conn:
            conn.execute("UPDATE demo_pairs SET expires=?", (expires,))
        self.demo(self.client, "employer")
        with server.db() as conn:
            session = conn.execute(
                "SELECT expires FROM sessions WHERE token=?",
                (server.digest(self.client.cookies.get("fsp_session")),),
            ).fetchone()
            self.assertLessEqual(session["expires"], expires)
            conn.execute("UPDATE demo_pairs SET expires=?", (time.time() - 1,))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.demo(self.client)

    def test_stale_session_cookie_does_not_block_demo_reentry(self):
        user = self.demo(self.client)
        with server.db() as conn:
            conn.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
        new = self.demo(self.client)
        self.assertEqual(new["id"], user["id"])

    def test_expired_test_attempt_keeps_the_retake_limit(self):
        self.demo(self.client, "fresh")
        choice = {"specialization": "backend", "grade": "Middle"}
        started = self.client.post("/api/candidate/tests", json=choice).json()
        with patch.object(server.time, "time", return_value=started["deadline"] + 1):
            self.assertEqual(self.client.post("/api/candidate/tests", json=choice).status_code, 409)

    def test_preview_fields_without_saving_or_assigning_category(self):
        self.demo(self.client, "fresh")
        before = self.client.get("/api/candidate/profile").json()
        response = self.preview(
            self.pdf("Python SQL PostgreSQL +7 900 123 45 67 Telegram: @sample_user")
        )
        self.assertEqual(response.status_code, 200, response.text)
        fields = response.json()["suggestions"]
        self.assertEqual(fields["skills"], ["Python", "SQL", "PostgreSQL"])
        self.assertEqual(fields["phone"], "+7 900 123 45 67")
        self.assertEqual(fields["telegram"], "@sample_user")
        self.assertEqual(self.client.get("/api/candidate/profile").json(), before)
        self.assertNotIn("published", fields)
        self.assertNotIn("categories", fields)

    def test_preview_bad_pdf_and_limits(self):
        self.demo(self.client)
        for content in [b"not pdf", b"%PDF-1.7 invalid", self.pdf("", 1), self.pdf("Python", 11)]:
            self.assertEqual(self.preview(content).status_code, 422)
        self.assertEqual(self.preview(b"%PDF-" + b"x" * (2 * 1024 * 1024)).status_code, 413)
        self.assertEqual(
            self.client.post("/api/candidate/resume/preview", content=b"file").status_code, 415
        )
        server.limiter.clear()
        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(self.pdf())))
        writer.encrypt("private")
        encrypted = io.BytesIO()
        writer.write(encrypted)
        self.assertEqual(self.preview(encrypted.getvalue()).status_code, 422)

    def test_preview_roles_and_csrf(self):
        self.demo(self.client, "employer")
        self.assertEqual(self.preview(self.pdf()).status_code, 403)
        self.demo(self.client)
        self.client.headers.pop("X-CSRF-Token")
        self.assertEqual(self.preview(self.pdf()).status_code, 403)

    def test_multiword_search_without_private_names_or_contacts(self):
        self.demo(self.client, "employer")
        for q in ["Python SQL", "SQL, Python", "pYtHoN; FASTAPI", "   "]:
            self.assertEqual(
                len(
                    self.client.get("/api/employer/candidates", params={"q": q}).json()[
                        "candidates"
                    ]
                ),
                1,
            )
        for q in ["SQL unknown", "Александр", "@demo_talent"]:
            self.assertEqual(
                self.client.get("/api/employer/candidates", params={"q": q}).json()["candidates"],
                [],
            )
        self.assertEqual(
            self.client.get("/api/employer/candidates", params={"q": "x" * 201}).status_code, 422
        )

    def test_password_check_runs_for_unknown_login_and_resend(self):
        for path in ["/api/auth/login", "/api/auth/resend"]:
            with patch.object(server, "check_password", return_value=False) as check:
                response = self.client.post(
                    path, json={"email": "unknown@example.org", "password": "Wrong2026!"}
                )
                self.assertEqual(response.status_code, 401)
                check.assert_called_once_with("Wrong2026!", server.ERASURE_DUMMY_PASSWORD)

    def test_active_attempt_can_only_resume_the_same_choice(self):
        self.demo(self.client, "fresh")
        choice = {"specialization": "backend", "grade": "Middle"}
        first = self.client.post("/api/candidate/tests", json=choice).json()
        resumed = self.client.post("/api/candidate/tests", json=choice).json()
        self.assertEqual(first["id"], resumed["id"])
        response = self.client.post(
            "/api/candidate/tests", json={"specialization": "frontend", "grade": "Junior"}
        )
        self.assertEqual(response.status_code, 409)

    def test_openapi_describes_pdf_upload(self):
        operation = self.client.get("/openapi.json").json()["paths"][
            "/api/candidate/resume/preview"
        ]["post"]
        self.assertEqual(
            operation["requestBody"]["content"]["application/pdf"]["schema"]["format"], "binary"
        )


if __name__ == "__main__":
    unittest.main()
