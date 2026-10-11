import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from assessment import GRADES, evaluate, generate, public_questions
from fastapi.testclient import TestClient
from matching import rank_candidate


class AssessmentTests(unittest.TestCase):
    def test_forms_balanced_randomized_and_private(self):
        for spec in ["backend", "frontend"]:
            for grade in GRADES:
                a = generate(spec, grade, 17)
                self.assertEqual(a, generate(spec, grade, 17))
                self.assertNotEqual(a, generate(spec, grade, 18))
                self.assertEqual(len(a), 15)
                self.assertEqual(len({q["id"] for q in a}), 15)
                self.assertEqual(
                    sorted(sum(q["topic"] == t for q in a) for t in {q["topic"] for q in a}),
                    [5, 5, 5],
                )
                self.assertTrue(
                    all(
                        not {"answer", "difficulty", "template"} & q.keys()
                        for q in public_questions(a)
                    )
                )

    def test_generated_python_sql_keys(self):
        for grade in GRADES:
            for seed in range(40):
                for q in generate("backend", grade, seed):
                    if q["skill"] == "Python":
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out):
                            exec(q["code"], {})
                        self.assertEqual(out.getvalue().strip(), q["answer"])
                    if q["skill"] == "SQL":
                        rows, sql = q["code"].split("\n\n")
                        conn = sqlite3.connect(":memory:")
                        conn.execute("CREATE TABLE orders(id,amount)")
                        conn.executemany(
                            "INSERT INTO orders VALUES(?,?)",
                            [tuple(map(int, r.split("|"))) for r in rows.splitlines()[1:]],
                        )
                        self.assertEqual(str(conn.execute(sql).fetchone()[0]), q["answer"])
                        conn.close()

    def test_scoring_monotonic_and_extremes(self):
        for spec in ["backend", "frontend"]:
            for grade in GRADES:
                q = generate(spec, grade, 18)
                answers = {}
                previous = -9
                for item in q:
                    answers[item["id"]] = item["answer"]
                    r = evaluate(q, answers, grade)
                    self.assertGreaterEqual(r["theta"], previous)
                    previous = r["theta"]
                self.assertTrue(r["passed"])
                self.assertEqual(r["score"], 100)
                self.assertFalse(evaluate(q, {}, grade)["passed"])

    def test_matching_neutral_fsp_missing_factors_and_ineligible(self):
        p = {"skills": ["Python"], "salary": 0, "work_format": "remote"}
        n = {"specialization": "backend", "grade": "Middle", "skills": ["Python"]}
        c = [
            {
                "specialization": "backend",
                "grade": "Middle",
                "score": 90,
                "verified_skills": ["Python"],
            }
        ]
        m = rank_candidate(p, n, c, [])
        self.assertEqual(
            next(x["value"] for x in m["breakdown"] if x["name"] == "Достижения ФСП"), 50
        )
        self.assertAlmostEqual(sum(x["points"] for x in m["breakdown"]), m["score"], delta=0.6)
        self.assertNotIn("Зарплатные ожидания", [x["name"] for x in m["breakdown"]])
        self.assertIsNone(rank_candidate(p, n, [], []))
        self.assertGreater(rank_candidate(p, n, c, [{"strength": 0.2}])["score"], m["score"])


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(self.tmp.name) / "test.sqlite3"
        server.limiter.clear()
        self.client = TestClient(server.app)
        self.client.__enter__()
        self.hr = self.login("hr@demo.ru")
        self.hr_token = self.client.cookies.get("fsp_session")
        self.candidate = self.login("candidate@demo.ru")
        self.candidate_token = self.client.cookies.get("fsp_session")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def login(self, email):
        self.client.cookies.clear()
        r = self.client.post("/api/auth/login", json={"email": email, "password": "Demo2026!"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def use(self, which):
        self.client.cookies.clear()
        self.client.cookies.set(
            "fsp_session", getattr(self, which + "_token"), domain="testserver.local", path="/"
        )
        self.client.headers["X-CSRF-Token"] = getattr(self, which)["csrf"]

    def status(self, r, status):
        self.assertEqual(r.status_code, status, r.text)

    def fresh(self):
        u = self.login("fresh@demo.ru")
        self.client.headers["X-CSRF-Token"] = u["csrf"]
        return u

    def test_roles_csrf_origin(self):
        self.use("candidate")
        self.status(self.client.get("/api/employer/needs"), 403)
        self.client.headers.pop("X-CSRF-Token")
        self.status(self.client.post("/api/auth/logout"), 403)
        self.use("candidate")
        self.status(
            self.client.post("/api/auth/logout", headers={"Origin": "https://foreign.example"}), 403
        )
        self.assertIn("default-src", self.client.get("/").headers["content-security-policy"])

    def test_contacts_accept_scope_revoke_and_no_regrant(self):
        self.use("hr")
        cid = self.candidate["id"]
        p = self.client.get(f"/api/employer/candidates/{cid}").json()
        self.assertNotIn("contacts", p)
        self.assertNotIn("fsp_id", p)
        self.assertNotEqual(p["name"], self.candidate["name"])
        self.status(self.client.get(f"/api/employer/candidates/{cid}/profile.pdf"), 200)
        self.use("candidate")
        inv = self.client.get("/api/invitations").json()[0]["id"]
        self.status(
            self.client.patch(
                f"/api/invitations/{inv}", json={"status": "accepted", "share_contacts": False}
            ),
            422,
        )
        self.status(
            self.client.patch(
                f"/api/invitations/{inv}", json={"status": "accepted", "share_contacts": True}
            ),
            200,
        )
        self.use("hr")
        self.assertEqual(
            self.client.get(f"/api/employer/candidates/{cid}").json()["contacts"]["email"],
            "candidate@demo.ru",
        )
        self.login("team@demo.ru")
        self.assertNotIn("contacts", self.client.get(f"/api/employer/candidates/{cid}").json())
        self.use("candidate")
        self.status(self.client.delete("/api/candidate/contacts/" + str(self.hr["id"])), 200)
        self.status(
            self.client.patch(
                f"/api/invitations/{inv}", json={"status": "accepted", "share_contacts": True}
            ),
            200,
        )
        self.use("hr")
        self.assertNotIn("contacts", self.client.get(f"/api/employer/candidates/{cid}").json())

    def test_ownership_need_invitation_attempt(self):
        self.use("hr")
        need = self.client.get("/api/employer/needs").json()[0]
        inv = self.client.get("/api/invitations").json()[0]
        u = self.login("team@demo.ru")
        self.client.headers["X-CSRF-Token"] = u["csrf"]
        self.status(self.client.get("/api/employer/candidates?need_id=" + str(need["id"])), 404)
        self.status(self.client.put("/api/employer/needs/" + str(need["id"]), json=need), 404)
        self.status(
            self.client.patch("/api/invitations/" + str(inv["id"]), json={"status": "withdrawn"}),
            404,
        )
        self.fresh()
        a = self.client.post(
            "/api/candidate/tests", json={"specialization": "backend", "grade": "Middle"}
        ).json()
        self.use("candidate")
        self.status(
            self.client.put(
                "/api/candidate/tests/" + a["id"] + "/answers", json={"version": 0, "answers": {}}
            ),
            404,
        )

    def test_autosave_conflict_resume_scoring_no_downgrade(self):
        self.fresh()
        a = self.client.post(
            "/api/candidate/tests", json={"specialization": "backend", "grade": "Middle"}
        ).json()
        with server.db() as conn:
            q = server.loads(
                conn.execute("SELECT questions FROM attempts WHERE id=?", (a["id"],)).fetchone()[
                    "questions"
                ]
            )
        answers = {x["id"]: x["answer"] for x in q}
        self.status(
            self.client.put(
                "/api/candidate/tests/" + a["id"] + "/answers",
                json={"version": 0, "answers": answers},
            ),
            200,
        )
        self.status(
            self.client.put(
                "/api/candidate/tests/" + a["id"] + "/answers",
                json={"version": 0, "answers": answers},
            ),
            409,
        )
        self.assertEqual(
            self.client.get("/api/candidate/tests").json()["active"]["answers"], answers
        )
        r = self.client.post("/api/candidate/tests/" + a["id"] + "/finish").json()
        self.assertTrue(r["passed"])
        self.assertTrue(r["strong"])
        self.assertEqual(self.client.post("/api/candidate/tests/" + a["id"] + "/finish").json(), r)
        b = self.client.post(
            "/api/candidate/tests", json={"specialization": "backend", "grade": "Senior"}
        )
        self.status(b, 200)
        self.assertFalse(
            self.client.post("/api/candidate/tests/" + b.json()["id"] + "/finish").json()["passed"]
        )
        self.assertEqual(
            self.client.get("/api/candidate/profile").json()["categories"][0]["grade"], "Middle"
        )
        self.status(
            self.client.post(
                "/api/candidate/tests", json={"specialization": "backend", "grade": "Middle"}
            ),
            409,
        )

    def test_visibility_consent_pdf(self):
        self.use("candidate")
        p = self.client.get("/api/candidate/profile").json()
        p.update(phone=p["contacts"]["phone"], telegram=p["contacts"]["telegram"], published=False)
        self.status(self.client.put("/api/candidate/profile", json=p), 200)
        self.use("hr")
        self.status(self.client.get("/api/employer/candidates/" + str(self.candidate["id"])), 404)
        self.status(
            self.client.get(
                "/api/employer/candidates/" + str(self.candidate["id"]) + "/profile.pdf"
            ),
            404,
        )
        self.use("candidate")
        self.assertEqual(self.client.get("/api/candidate/profile.pdf").content[:4], b"%PDF")
        self.status(self.client.post("/api/candidate/consent/revoke"), 200)
        self.status(self.client.get("/api/auth/me"), 401)
        self.status(
            self.client.post(
                "/api/auth/login", json={"email": "candidate@demo.ru", "password": "Demo2026!"}
            ),
            403,
        )

    def test_registration_email_verification_counter(self):
        self.client.cookies.clear()
        self.client.headers.pop("X-CSRF-Token", None)
        body = {
            "email": "new@demo.ru",
            "name": "Новый участник",
            "password": "Asecure2026!",
            "role": "candidate",
            "consent": False,
            "terms_accepted": True,
            "age_confirmed": True,
        }
        self.status(self.client.post("/api/auth/register", json=body), 422)
        body["consent"] = True
        r = self.client.post("/api/auth/register", json=body)
        self.status(r, 201)
        code = r.json()["dev_code"]
        self.status(
            self.client.post(
                "/api/auth/login", json={"email": body["email"], "password": body["password"]}
            ),
            403,
        )
        wrong = "111111" if code != "111111" else "222222"
        self.status(
            self.client.post("/api/auth/verify", json={"email": body["email"], "code": wrong}), 400
        )
        with server.db() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT failures FROM email_codes WHERE user_id=(SELECT id FROM users WHERE email='new@demo.ru')"
                ).fetchone()["failures"],
                1,
            )
        self.status(
            self.client.post(
                "/api/auth/resend", json={"email": body["email"], "password": "Wrong2026!"}
            ),
            401,
        )
        resend = self.client.post(
            "/api/auth/resend", json={"email": body["email"], "password": body["password"]}
        )
        self.status(resend, 200)
        code = resend.json()["dev_code"]
        with server.db() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT failures FROM email_codes WHERE user_id=(SELECT id FROM users WHERE email='new@demo.ru')"
                ).fetchone()["failures"],
                0,
            )
        self.status(
            self.client.post("/api/auth/verify", json={"email": body["email"], "code": code}), 200
        )
        self.assertFalse(self.client.get("/api/candidate/profile").json()["published"])

    def test_salary_duplicates_and_application_consent(self):
        self.use("hr")
        p = {
            "candidate_id": self.candidate["id"],
            "title": "Разработчик Python",
            "description": "Интересная работа в нашей команде",
            "salary_from": 200000,
            "salary_to": 100000,
            "contact": "hr@example.org",
            "work_format": "remote",
        }
        self.status(self.client.post("/api/employer/invitations", json=p), 422)
        p["salary_to"] = 300000
        self.status(self.client.post("/api/employer/invitations", json=p), 409)
        self.use("candidate")
        need = self.client.get("/api/jobs").json()[0]["id"]
        self.status(
            self.client.post("/api/jobs/" + str(need) + "/apply", json={"share_contacts": False}),
            422,
        )
        self.status(
            self.client.post("/api/jobs/" + str(need) + "/apply", json={"share_contacts": True}),
            200,
        )

    def test_weekly_assignment_manual_review(self):
        self.use("candidate")
        ts = self.client.get("/api/tasks").json()
        self.assertEqual(len(ts), 1)
        self.assertEqual(self.client.get("/api/tasks").json()[0]["id"], ts[0]["id"])
        r = self.client.post(
            "/api/tasks/" + str(ts[0]["id"]) + "/answer",
            json={
                "answer": "Ключ идемпотентности хранится в транзакции. Повтор возвращает сохранённый результат."
            },
        )
        self.status(r, 200)
        aid = r.json()["id"]
        self.status(
            self.client.post(
                "/api/tasks/" + str(ts[0]["id"]) + "/answer",
                json={"answer": "Повторное решение не принимается, потому что ответ отправлен."},
            ),
            409,
        )
        self.use("hr")
        r = self.client.put(
            "/api/employer/task-answers/" + str(aid),
            json={
                "correctness": 2,
                "completeness": 1,
                "reasoning": 2,
                "feedback": "Корректно описана идемпотентность. Добавьте обработку параллельных запросов.",
            },
        )
        self.status(r, 200)
        self.assertEqual(r.json()["score"], 83)
        self.use("candidate")
        self.assertEqual(self.client.get("/api/tasks").json()[0]["answer"]["score"], 83)

    def test_create_need_task(self):
        self.use("hr")
        n = {
            "title": "Новая команда",
            "specialization": "frontend",
            "grade": "Middle",
            "skills": ["React", "TypeScript"],
            "description": "Создавать доступные интерфейсы нового продукта.",
            "salary_from": 180000,
            "salary_to": 240000,
            "work_format": "remote",
            "published": True,
        }
        r = self.client.post("/api/employer/needs", json=n)
        self.status(r, 200)
        self.assertGreater(
            self.client.get("/api/employer/candidates?need_id=" + str(r.json()["id"])).json()[
                "total"
            ],
            0,
        )
        self.status(
            self.client.post(
                "/api/employer/tasks",
                json={
                    "title": "Доступность формы",
                    "specialization": "frontend",
                    "grade": "Middle",
                    "description": "Как обеспечить доступную обработку ошибок в форме регистрации?",
                },
            ),
            200,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
