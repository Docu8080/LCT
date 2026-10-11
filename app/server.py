import hashlib
import hmac
import io
import json
import logging
import os
from pathlib import Path
import random
import secrets
import smtplib
import sqlite3
import threading
import time
from contextlib import contextmanager, asynccontextmanager
from email.message import EmailMessage
from typing import Literal
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool, field_validator
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from assessment import SPECIALIZATIONS, GRADES, generate, evaluate, public_questions
from matching import rank_candidate

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("FSP_DATABASE", str(ROOT / "data/fsp.sqlite3")))
DEMO = os.environ.get("FSP_DEMO", "1") == "1"
COOKIE_SECURE = os.environ.get("FSP_COOKIE_SECURE", "0") == "1"
log = logging.getLogger("fsp")
CONSENT_VERSION = "2026-10-11-v2"
TERMS_VERSION = "2026-10-11-v2"
PRIVACY_COLUMNS = {
    'consent_accepted_at': 'REAL',
    'terms_version': 'TEXT',
    'terms_accepted_at': 'REAL',
    'age_confirmed': 'INTEGER NOT NULL DEFAULT 0',
    'age_confirmed_at': 'REAL',
    'acceptance_source': "TEXT NOT NULL DEFAULT 'legacy'",
    'marketing_enabled': 'INTEGER NOT NULL DEFAULT 0',
    'marketing_opted_out_at': 'REAL',
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
 name TEXT NOT NULL, password TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
 consent INTEGER NOT NULL DEFAULT 1, consent_version TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id), data TEXT NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS companies(user_id INTEGER PRIMARY KEY REFERENCES users(id), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(user_id INTEGER REFERENCES users(id), spec TEXT, grade TEXT,
 data TEXT NOT NULL, verified_at REAL NOT NULL, upgrade_until REAL NOT NULL DEFAULT 0, PRIMARY KEY(user_id,spec));
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), csrf TEXT, expires REAL);
CREATE TABLE IF NOT EXISTS email_codes(user_id INTEGER PRIMARY KEY REFERENCES users(id), code TEXT, expires REAL, failures INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),spec TEXT,grade TEXT,
 created REAL,deadline REAL,status TEXT,questions TEXT,answers TEXT,version INTEGER DEFAULT 0,result TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_attempt ON attempts(user_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS needs(id INTEGER PRIMARY KEY,employer INTEGER REFERENCES users(id),data TEXT,published INTEGER DEFAULT 0,created REAL);
CREATE TABLE IF NOT EXISTS invitations(id INTEGER PRIMARY KEY,employer INTEGER REFERENCES users(id),candidate INTEGER REFERENCES users(id),
 data TEXT,status TEXT,created REAL,updated REAL);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_invitation ON invitations(employer,candidate) WHERE status IN ('sent','viewed');
CREATE TABLE IF NOT EXISTS grants(employer INTEGER REFERENCES users(id),candidate INTEGER REFERENCES users(id),revoked INTEGER DEFAULT 0,
 created REAL, PRIMARY KEY(employer,candidate));
CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY,need_id INTEGER REFERENCES needs(id),candidate INTEGER REFERENCES users(id),
 employer INTEGER REFERENCES users(id),status TEXT,created REAL,UNIQUE(need_id,candidate));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,employer INTEGER REFERENCES users(id),data TEXT,created REAL);
CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY,task INTEGER REFERENCES tasks(id),candidate INTEGER REFERENCES users(id),
 created REAL,deadline REAL,status TEXT,reason TEXT,UNIQUE(task,candidate));
CREATE TABLE IF NOT EXISTS task_answers(id INTEGER PRIMARY KEY,assignment INTEGER UNIQUE REFERENCES assignments(id),
 candidate INTEGER REFERENCES users(id),employer INTEGER REFERENCES users(id),answer TEXT,score INTEGER,feedback TEXT,created REAL);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),title TEXT,body TEXT,created REAL,seen INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER,action TEXT,target TEXT,created REAL);
"""
REGISTRY = {
 f"FSP-DEMO-{i:03}": [{"event": f"Кубок спортивного программирования · {2024+i%3}",
 "discipline": "Продуктовое программирование" if i%2 else "Алгоритмическое программирование",
 "result": "2 место" if i%2 else "Финалист", "year":2024+i%3,"strength":0.22,"source":"Демо-реестр ФСП"}]
 for i in range(1,7)
}


def dumps(data): return json.dumps(data,ensure_ascii=False)
def loads(data): return json.loads(data) if data else {}
def digest(value): return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password):
    salt=secrets.token_hex(16)
    key=hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1,maxmem=64*1024*1024)
    return salt+":"+key.hex()


def check_password(password,stored):
    salt,expected=stored.split(":")
    key=hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1,maxmem=64*1024*1024)
    return hmac.compare_digest(key.hex(),expected)


ERASURE_DUMMY_PASSWORD=hash_password(secrets.token_urlsafe(32))


@contextmanager
def db():
    conn=sqlite3.connect(DB_PATH,timeout=15)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()


def notify(conn,user,title,body="",related_user=None):
    conn.execute("INSERT INTO notifications(user_id,title,body,created,related_user) VALUES(?,?,?,?,?)",(user,title,body,time.time(),related_user))


def audit(conn,user,action,target):
    conn.execute("INSERT INTO audit(actor,action,target,created) VALUES(?,?,?,?)",(user,action,str(target),time.time()))


def categories(conn,user):
    return [dict(loads(r["data"]),specialization=r["spec"],grade=r["grade"],verified_at=r["verified_at"])
            for r in conn.execute("SELECT * FROM categories WHERE user_id=?",(user,))]


def profile(conn,user):
    r=conn.execute("SELECT data FROM profiles WHERE user_id=?",(user,)).fetchone()
    if not r:raise HTTPException(404,"Профиль не найден")
    return loads(r["data"])


def company(conn,user):
    r=conn.execute("SELECT data FROM companies WHERE user_id=?",(user,)).fetchone()
    return loads(r["data"]) if r else {"name":"Компания","description":"","contact":"","website":""}


def achievements(p):
    return REGISTRY.get(p.get("fsp_id"),[]) if p.get("show_fsp",True) else []


def has_contacts(conn,employer,candidate):
    grant=conn.execute("SELECT revoked FROM grants WHERE employer=? AND candidate=?",(employer,candidate)).fetchone()
    u=conn.execute("SELECT consent FROM users WHERE id=?",(candidate,)).fetchone()
    return bool(grant and not grant["revoked"] and u and u["consent"])


def view_candidate(conn,candidate,employer=None,own=False):
    p=profile(conn,candidate)
    user=conn.execute("SELECT * FROM users WHERE id=?",(candidate,)).fetchone()
    if not own and (not p.get("published") or not user["consent"]):raise HTTPException(404,"Профиль недоступен")
    allowed=own or (employer is not None and has_contacts(conn,employer,candidate))
    out={k:v for k,v in p.items() if k not in {"email","phone","telegram","name","fsp_pending","fsp_code","fsp_code_expires"}}
    out.update(id=candidate,name=p.get("name") if allowed else f"Талант #{candidate:03}",
               categories=categories(conn,candidate),achievements=achievements(p),contacts_open=allowed)
    if allowed:out["contacts"]={"email":user["email"],"phone":p.get("phone",""),"telegram":p.get("telegram","")}
    if not own:out.pop("fsp_id",None)
    return out


def initialize():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    conn=sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    columns={row[1] for row in conn.execute('PRAGMA table_info(users)')}
    for name,declaration in PRIVACY_COLUMNS.items():
        if name not in columns:conn.execute(f'ALTER TABLE users ADD COLUMN {name} {declaration}')
    notification_columns={row[1] for row in conn.execute('PRAGMA table_info(notifications)')}
    if 'related_user' not in notification_columns:
        conn.execute('ALTER TABLE notifications ADD COLUMN related_user INTEGER')
    conn.commit()
    conn.close()
    DB_PATH.chmod(0o600)
    if DEMO:seed_demo()
    backfill_notification_relations()


def backfill_notification_relations():
    """Associate recognizable historical notices only when a counterpart is unambiguous."""
    with db() as conn:
        pending=list(conn.execute('SELECT * FROM notifications WHERE related_user IS NULL'))
        candidates={r['id']:set() for r in pending}
        for inv in conn.execute('SELECT * FROM invitations'):
            data=loads(inv['data']);name=company(conn,inv['employer'])['name']
            for notice in pending:
                if notice['user_id']==inv['candidate'] and notice['title'] in {'Приглашение от '+name,'Новое приглашение от '+name} and notice['body'].startswith(data.get('title','\0')):
                    candidates[notice['id']].add(inv['employer'])
                if notice['title']=='Статус приглашения изменился' and inv['created']-1<=notice['created']<=inv['updated']+1:
                    if notice['user_id']==inv['employer']:candidates[notice['id']].add(inv['candidate'])
                    elif notice['user_id']==inv['candidate']:candidates[notice['id']].add(inv['employer'])
        for application in conn.execute('SELECT a.*,n.data FROM applications a JOIN needs n ON n.id=a.need_id'):
            for notice in pending:
                if notice['user_id']==application['employer'] and notice['title']=='Новый отклик' and notice['body']==loads(application['data']).get('title') and abs(notice['created']-application['created'])<2:
                    candidates[notice['id']].add(application['candidate'])
        for assignment in conn.execute('SELECT a.*,t.data,t.employer FROM assignments a JOIN tasks t ON t.id=a.task'):
            for notice in pending:
                if notice['user_id']==assignment['candidate'] and notice['title']=='Задание недели доступно' and notice['body']==loads(assignment['data']).get('title') and abs(notice['created']-assignment['created'])<2:
                    candidates[notice['id']].add(assignment['employer'])
        for answer in conn.execute('SELECT a.*,t.data FROM task_answers a JOIN assignments s ON s.id=a.assignment JOIN tasks t ON t.id=s.task'):
            for notice in pending:
                if notice['user_id']==answer['employer'] and notice['title']=='Ответ на задание недели' and notice['body']==loads(answer['data']).get('title') and abs(notice['created']-answer['created'])<2:
                    candidates[notice['id']].add(answer['candidate'])
                if answer['score'] is not None and notice['user_id']==answer['candidate'] and notice['title']=='Проверено задание недели' and notice['body']==f"{answer['score']}% · "+(answer['feedback'] or ''):
                    candidates[notice['id']].add(answer['employer'])
        for notification_id,users in candidates.items():
            if len(users)==1:conn.execute('UPDATE notifications SET related_user=? WHERE id=?',(users.pop(),notification_id))


def seed_demo():
    with db() as conn:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():return
        rng=random.Random(2026)
        password=hash_password("Demo2026!")
        now=time.time()
        def user(email,role,name):
            cur=conn.execute("INSERT INTO users(email,role,name,password,verified,consent_version,created,acceptance_source) VALUES(?,?,?,?,1,?,?, 'synthetic_demo')",(email,role,name,password,CONSENT_VERSION,now))
            return cur.lastrowid
        hr=user("hr@demo.ru","employer","Алина · Север Код")
        second=user("team@demo.ru","employer","Команда Пульс")
        for uid,name,description in [(hr,"Север Код","Создаём продукты для городской инфраструктуры и миллионов пользователей."),(second,"Пульс","Развиваем платформу обучения и аналитики.")]:
            conn.execute("INSERT INTO companies VALUES(?,?)",(uid,dumps({"name":name,"description":description,"contact":"talent@severcode.example.org","website":"https://example.org","industry":"Продуктовая разработка"})))
        names=["Александр Морозов","Мария Волкова","Дмитрий Соколов","Анна Лебедева","Илья Кузнецов","Екатерина Орлова","Никита Попов","Дарья Смирнова"]
        for i in range(32):
            name=names[i%len(names)]
            email="candidate@demo.ru" if i==0 else "fresh@demo.ru" if i==1 else f"talent{i:02}@demo.ru"
            uid=user(email,"candidate",name if i!=1 else "Новый кандидат")
            spec="backend" if i%3!=2 else "frontend"
            skills=(["Python","FastAPI","SQL","PostgreSQL","Docker"] if spec=="backend" else ["JavaScript","TypeScript","React","CSS","HTML"])
            p={"name":name if i!=1 else "Новый кандидат","title":"Python-разработчик" if spec=="backend" else "Frontend-разработчик",
               "phone":"+7 900 000 00 00","telegram":"@demo_talent","about":"Разрабатываю надёжные продукты. Люблю понятные API, внимание к деталям и работу в команде.",
               "skills":skills,"experience":3+i%5,"team_role":"Разработчик","soft_skills":"Коммуникация, самостоятельность, работа в команде",
               "city":["Москва","Казань","Санкт-Петербург"][i%3],"work_format":"remote" if i%2==0 else "hybrid",
               "salary":180000+i%5*15000,"published":i!=1,"show_fsp":True,"fsp_id":f"FSP-DEMO-{i%6+1:03}" if i%3==0 else None,
               "specialization":spec,"declared_grade":"Middle","industry":"Информационные технологии"}
            conn.execute("INSERT INTO profiles VALUES(?,?,?)",(uid,dumps(p),now))
            if i!=1:
                grade="Middle" if i%4<2 else "Junior" if i%4==2 else "Senior"
                score=86 if i==0 else rng.randrange(70,98)
                result={"score":score,"theta":round(0.2+(score-75)/20,2),"confidence":95,"source":"Синтетический демо-профиль",
                        "verified_skills":skills[:3],"topics":[{"name":t,"score":rng.randrange(65,100)} for t in ("Алгоритмы","Данные и SQL","API и архитектура") if spec=="backend"] or [{"name":t,"score":rng.randrange(65,100)} for t in ("JavaScript","Интерфейсы","Веб-платформа")]}
                conn.execute("INSERT INTO categories(user_id,spec,grade,data,verified_at) VALUES(?,?,?,?,?)",(uid,spec,grade,dumps(result),now-86400*35))
        need_ids=[]
        for data in [
            {"title":"Python Backend Developer","specialization":"backend","grade":"Middle","skills":["Python","FastAPI","PostgreSQL"],"description":"Разрабатывать API продуктовой платформы, работать с PostgreSQL и участвовать в проектировании сервисов.","salary_from":180000,"salary_to":260000,"work_format":"remote","city":"Москва"},
            {"title":"Frontend Developer","specialization":"frontend","grade":"Middle","skills":["React","TypeScript","CSS"],"description":"Создавать доступные интерфейсы и развивать дизайн-систему продуктовой команды.","salary_from":160000,"salary_to":240000,"work_format":"hybrid","city":"Москва"},
            {"title":"Junior Python Developer","specialization":"backend","grade":"Junior","skills":["Python","SQL"],"description":"Начать карьеру в продуктовой команде с поддержкой наставника и реальными задачами.","salary_from":90000,"salary_to":140000,"work_format":"remote","city":"Москва"}]:
            need_ids.append(conn.execute("INSERT INTO needs(employer,data,published,created) VALUES(?,?,1,?)",(hr,dumps(data),now)).lastrowid)
        candidate=conn.execute("SELECT id FROM users WHERE email='candidate@demo.ru'").fetchone()["id"]
        invitation={"title":"Python Backend Developer","description":"Александр, ваш опыт Python и результаты теста подходят нашей команде. Приглашаем познакомиться с продуктом и обсудить задачи.","salary_from":190000,"salary_to":260000,"contact":"talent@severcode.example.org","work_format":"remote"}
        conn.execute("INSERT INTO invitations(employer,candidate,data,status,created,updated) VALUES(?,?,?,'sent',?,?)",(hr,candidate,dumps(invitation),now-86400,now-86400))
        notify(conn,candidate,"Новое приглашение от Север Код","Python Backend Developer · 190–260 тыс. ₽",related_user=hr)
        for spec,title,description,keywords in [
            ("backend","API без повторных списаний","Платёжный API получил один и тот же запрос дважды из-за сетевого тайм-аута. Предложите схему защиты от повторного списания: как хранить ключ запроса, обрабатывать параллельные запросы и возвращать результат?",["идемпот","ключ","транзак","повтор"]),
            ("frontend","Форма, которой можно доверять","Пользователь редактирует форму с автосохранением на двух устройствах. Предложите обработку устаревшего ответа, конфликтов, потери сети и доступности уведомлений.",["верси","конфликт","сеть","доступ"])
        ]:
            task={"specialization":spec,"grade":"Middle","title":title,"description":description,"keywords":keywords,"rubric":["Корректность","Полнота","Обоснование"],"topic":"API и архитектура" if spec=="backend" else "Интерфейсы"}
            conn.execute("INSERT INTO tasks(employer,data,created) VALUES(?,?,?)",(hr,dumps(task),now-86400*8))


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield


app=FastAPI(title="ФСП Таланты · API",version="1.0.0",description="Платформа обратного найма. Демо-реестр и данные синтетические.",lifespan=lifespan,docs_url=None,redoc_url=None)
limiter={}
limiter_lock=threading.Lock()


@app.middleware("http")
async def protection(request,call_next):
    if request.url.path.startswith("/api/"):
        if int(request.headers.get("content-length","0"))>100_000:return JSONResponse({"detail":"Слишком большой запрос"},413)
        if request.method in {"POST","PATCH","PUT","DELETE"}:
            origin=request.headers.get("origin")
            if origin and origin not in {f"http://{request.headers.get('host')}",f"https://{request.headers.get('host')}"}:
                return JSONResponse({"detail":"Недопустимый источник запроса"},403)
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="same-origin"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/api/"):response.headers["Cache-Control"]="no-store"
    return response


def throttle(request,key,limit=15):
    identifier=(request.client.host if request.client else "local",key)
    now=time.time()
    with limiter_lock:
        recent=[t for t in limiter.get(identifier,[]) if t>now-60]
        if len(recent)>=limit:raise HTTPException(429,"Слишком много попыток. Повторите через минуту.")
        limiter[identifier]=recent+[now]


def current(request:Request):
    token=request.cookies.get("fsp_session","")
    with db() as conn:
        row=conn.execute("SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?",(digest(token),time.time())).fetchone()
    if not row:raise HTTPException(401,"Войдите в аккаунт")
    if not row["consent"]:raise HTTPException(403,"Согласие на обработку данных отозвано")
    if request.method in {"POST","PATCH","PUT","DELETE"} and not hmac.compare_digest(row["csrf"],request.headers.get("x-csrf-token","")):
        raise HTTPException(403,"Обновите страницу: не совпал защитный токен")
    return dict(row)


def candidate(user=Depends(current)):
    if user["role"]!="candidate":raise HTTPException(403,"Требуется аккаунт кандидата")
    return user


def employer(user=Depends(current)):
    if user["role"]!="employer":raise HTTPException(403,"Требуется аккаунт работодателя")
    return user


class AuthData(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    password:str=Field(min_length=8,max_length=128)
    @field_validator("email")
    @classmethod
    def email_check(cls,value):
        value=value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1] or any(c.isspace() for c in value):raise ValueError("Укажите корректный email")
        return value


class RegisterData(AuthData):
    name:str=Field(min_length=2,max_length=100)
    role:Literal["candidate","employer"]
    consent:StrictBool
    terms_accepted:StrictBool
    age_confirmed:StrictBool


class VerifyData(BaseModel):
    email:str=Field(max_length=254)
    code:str=Field(min_length=6,max_length=6)


def send_code(email,code):
    if not os.environ.get("FSP_SMTP_HOST"):
        if not DEMO:raise HTTPException(503,"Доставка почты не настроена")
        return
    message=EmailMessage()
    message["From"]=os.environ.get("FSP_SMTP_FROM","noreply@example.org")
    message["To"]=email
    message["Subject"]="Подтверждение email · ФСП Таланты"
    message.set_content(f"Код подтверждения: {code}. Действует 15 минут.")
    try:
        with smtplib.SMTP(os.environ["FSP_SMTP_HOST"],int(os.environ.get("FSP_SMTP_PORT","587")),timeout=10) as smtp:
            smtp.starttls()
            if os.environ.get("FSP_SMTP_USER"):smtp.login(os.environ["FSP_SMTP_USER"],os.environ["FSP_SMTP_PASSWORD"])
            smtp.send_message(message)
    except Exception:
        log.exception("SMTP delivery failed")
        raise HTTPException(503,"Письмо не доставлено. Повторите позже.")


def session_response(conn,user,response):
    token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions VALUES(?,?,?,?)",(digest(token),user["id"],csrf,time.time()+86400))
    response.set_cookie("fsp_session",token,max_age=86400,httponly=True,samesite="strict",secure=COOKIE_SECURE,path="/")
    return {"id":user["id"],"email":user["email"],"name":user["name"],"role":user["role"],"csrf":csrf,"demo":DEMO}


@app.post("/api/auth/register",status_code=201,tags=["Авторизация"])
def register(data:RegisterData,request:Request):
    throttle(request,"register",5)
    if not data.consent:raise HTTPException(422,"Нужно согласие на обработку данных")
    if not data.terms_accepted:raise HTTPException(422,"Подтвердите условия использования")
    if not data.age_confirmed:raise HTTPException(422,"Сервис предназначен для пользователей от 18 лет")
    code=f"{secrets.randbelow(1000000):06}"
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=?",(data.email,)).fetchone():raise HTTPException(409,"Этот email уже зарегистрирован")
        send_code(data.email,code)
        now=time.time()
        uid=conn.execute("INSERT INTO users(email,role,name,password,consent_version,created,consent_accepted_at,terms_version,terms_accepted_at,age_confirmed,age_confirmed_at,acceptance_source) VALUES(?,?,?,?,?,?,?,?,?,1,?,'registration')",(data.email,data.role,data.name,hash_password(data.password),CONSENT_VERSION,now,now,TERMS_VERSION,now,now)).lastrowid
        if data.role=="candidate":
            p={"name":data.name,"title":"","phone":"","telegram":"","about":"","skills":[],"experience":0,"team_role":"Разработчик","soft_skills":"","city":"","work_format":"remote","salary":0,"published":False,"show_fsp":False,"fsp_id":None,"specialization":"backend","declared_grade":"Junior","industry":"Информационные технологии"}
            conn.execute("INSERT INTO profiles VALUES(?,?,?)",(uid,dumps(p),time.time()))
        else:conn.execute("INSERT INTO companies VALUES(?,?)",(uid,dumps({"name":data.name,"description":"","contact":data.email,"website":"","industry":"ИТ"})))
        conn.execute("INSERT INTO email_codes(user_id,code,expires) VALUES(?,?,?)",(uid,digest(code),time.time()+900))
        audit(conn,uid,"consent.granted",CONSENT_VERSION)
    return {"email":data.email,"message":"Подтвердите email шестизначным кодом","dev_code":code if DEMO else None}


@app.post("/api/auth/verify",tags=["Авторизация"])
def verify(data:VerifyData,request:Request,response:Response):
    throttle(request,"verify",8)
    ok=False
    with db() as conn:
        row=conn.execute("SELECT c.*,u.email FROM email_codes c JOIN users u ON u.id=c.user_id WHERE u.email=?",(data.email.strip().lower(),)).fetchone()
        if row and row["expires"]>time.time() and row["failures"]<5:
            ok=hmac.compare_digest(row["code"],digest(data.code))
            if ok:
                conn.execute("UPDATE users SET verified=1 WHERE id=?",(row["user_id"],))
                conn.execute("DELETE FROM email_codes WHERE user_id=?",(row["user_id"],))
            else:conn.execute("UPDATE email_codes SET failures=failures+1 WHERE user_id=?",(row["user_id"],))
    if not ok:raise HTTPException(400,"Код неверный, просрочен или исчерпан лимит попыток")
    with db() as conn:
        user=conn.execute("SELECT * FROM users WHERE email=?",(data.email.strip().lower(),)).fetchone()
        return session_response(conn,user,response)


@app.post("/api/auth/login",tags=["Авторизация"])
def login(data:AuthData,request:Request,response:Response):
    throttle(request,"login")
    with db() as conn:
        user=conn.execute("SELECT * FROM users WHERE email=?",(data.email,)).fetchone()
        if not user or not check_password(data.password,user["password"]):raise HTTPException(401,"Email или пароль неверны")
        if not user["verified"]:raise HTTPException(403,"Сначала подтвердите email")
        if not user["consent"]:raise HTTPException(403,"Аккаунт деактивирован после отзыва согласия")
        return session_response(conn,user,response)


@app.post('/api/auth/resend',tags=['Авторизация'])
def resend_verification(data:AuthData,request:Request):
    throttle(request,'resend',3)
    with db() as conn:
        u=conn.execute('SELECT * FROM users WHERE email=?',(data.email,)).fetchone()
        if not u or not check_password(data.password,u['password']):raise HTTPException(401,'Email или пароль неверны')
        if u['verified']:raise HTTPException(409,'Email уже подтверждён. Войдите в аккаунт.')
        code=f'{secrets.randbelow(1000000):06}'
        send_code(data.email,code)
        conn.execute('INSERT INTO email_codes(user_id,code,expires) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET code=excluded.code,expires=excluded.expires,failures=0',(u['id'],digest(code),time.time()+900))
    return {'email':data.email,'dev_code':code if DEMO else None}


@app.post("/api/auth/logout",tags=["Авторизация"])
def logout(request:Request,response:Response,user=Depends(current)):
    with db() as conn:conn.execute("DELETE FROM sessions WHERE token=?",(digest(request.cookies.get("fsp_session","")),))
    response.delete_cookie("fsp_session",path="/")
    return {"ok":True}


@app.get("/api/auth/me",tags=["Авторизация"])
def me(user=Depends(current)):
    return {k:user[k] for k in ("id","email","role","name","csrf")}|{"demo":DEMO,"consent_version":CONSENT_VERSION}


def operator_field(name,limit):
    value=os.environ.get('FSP_OPERATOR_'+name,'').strip()
    value=''.join(char for char in value if char.isprintable())[:limit]
    return value or None


@app.get('/api/legal/config',tags=['Приватность'])
def legal_config():
    operator={key:operator_field(key.upper(),limit) for key,limit in {'name':200,'inn':12,'ogrn':15,'address':500,'email':254}.items()}
    if operator['inn'] and (not operator['inn'].isascii() or not operator['inn'].isdigit() or len(operator['inn']) not in {10,12}):operator['inn']=None
    if operator['ogrn'] and (not operator['ogrn'].isascii() or not operator['ogrn'].isdigit() or len(operator['ogrn']) not in {13,15}):operator['ogrn']=None
    email=operator['email']
    if email and ('@' not in email or '.' not in email.split('@')[-1] or any(char.isspace() for char in email)):operator['email']=None
    return {'operator':operator,'operator_configured':all(operator.values()),'service_age_min':18,'consent_version':CONSENT_VERSION,'terms_version':TERMS_VERSION,'demo':DEMO}


@app.get('/api/account/privacy',tags=['Приватность'])
def account_privacy(user=Depends(current)):
    return {
        'consent':{'accepted':bool(user['consent_accepted_at']),'active':bool(user['consent']),'version':user['consent_version'],'accepted_at':user['consent_accepted_at'],'record_source':user['acceptance_source']},
        'terms':{'accepted':bool(user['terms_accepted_at']),'version':user['terms_version'],'accepted_at':user['terms_accepted_at']},
        'age':{'confirmed':bool(user['age_confirmed']),'confirmed_at':user['age_confirmed_at'],'minimum':18},
        'marketing':{'enabled':bool(user['marketing_enabled']),'opted_out_at':user['marketing_opted_out_at']},
        'deletion':{'available':True,'scope':'active_database','requires_password':True},
    }


@app.post('/api/account/marketing/opt-out',tags=['Приватность'])
def marketing_opt_out(user=Depends(current)):
    now=time.time()
    with db() as conn:
        conn.execute('UPDATE users SET marketing_enabled=0,marketing_opted_out_at=? WHERE id=?',(now,user['id']))
    return {'ok':True,'marketing_enabled':False,'opted_out_at':now}


class DeleteAccountData(BaseModel):
    model_config={'extra':'forbid'}
    password:str=Field(min_length=8,max_length=128)


def erase_user(conn,uid):
    # Remove related records before their parents; the authenticated identity defines ownership.
    conn.execute('DELETE FROM audit WHERE actor=? OR (action="contacts.revoked" AND target=?) OR (action="profile.updated" AND target=?)',(uid,str(uid),str(uid)))
    conn.execute('DELETE FROM audit WHERE action LIKE "invitation.%" AND target IN (SELECT CAST(id AS TEXT) FROM invitations WHERE candidate=? OR employer=?)',(uid,uid))
    conn.execute('DELETE FROM audit WHERE action LIKE "test.%" AND target IN (SELECT id FROM attempts WHERE user_id=?)',(uid,))
    conn.execute('DELETE FROM audit WHERE action="job.applied" AND target IN (SELECT CAST(id AS TEXT) FROM needs WHERE employer=?)',(uid,))
    conn.execute('DELETE FROM notifications WHERE user_id=? OR related_user=?',(uid,uid))
    conn.execute('DELETE FROM task_answers WHERE candidate=? OR employer=? OR assignment IN (SELECT a.id FROM assignments a JOIN tasks t ON t.id=a.task WHERE a.candidate=? OR t.employer=?)',(uid,uid,uid,uid))
    conn.execute('DELETE FROM assignments WHERE candidate=? OR task IN (SELECT id FROM tasks WHERE employer=?)',(uid,uid))
    for table in ('applications','grants','invitations'):
        conn.execute(f'DELETE FROM {table} WHERE candidate=? OR employer=?',(uid,uid))
    for table in ('attempts','email_codes','sessions','categories','profiles','companies'):
        conn.execute(f'DELETE FROM {table} WHERE user_id=?',(uid,))
    conn.execute('DELETE FROM tasks WHERE employer=?',(uid,))
    conn.execute('DELETE FROM needs WHERE employer=?',(uid,))
    conn.execute('DELETE FROM users WHERE id=?',(uid,))


@app.delete('/api/account',tags=['Приватность'])
def delete_account(data:DeleteAccountData,request:Request,response:Response,user=Depends(current)):
    throttle(request,'delete-account',5)
    uid=user['id']
    with db() as conn:
        stored=conn.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()
        if not stored or not check_password(data.password,stored['password']):raise HTTPException(401,'Пароль неверный: аккаунт не удалён')
        erase_user(conn,uid)
    response.delete_cookie('fsp_session',path='/')
    return {'ok':True}


class ErasureData(AuthData):
    model_config={'extra':'forbid'}


@app.post('/api/account/erasure',tags=['Приватность'])
def erase_deactivated_account(data:ErasureData,request:Request,response:Response):
    # A deactivated account has no usable session. Password reauthentication remains available for erasure only.
    expected_origin=f"{request.url.scheme}://{request.headers.get('host')}"
    if request.headers.get('origin')!=expected_origin:raise HTTPException(403,'Недопустимый источник запроса')
    throttle(request,'account-erasure',5)
    with db() as conn:
        user=conn.execute('SELECT * FROM users WHERE email=?',(data.email,)).fetchone()
        password_ok=check_password(data.password,user['password'] if user else ERASURE_DUMMY_PASSWORD)
        if not user or user['consent'] or not password_ok:raise HTTPException(401,'Не удалось подтвердить данные деактивированного аккаунта')
        erase_user(conn,user['id'])
    response.delete_cookie('fsp_session',path='/')
    return {'ok':True}


@app.get("/api/references",tags=["Справочники"])
def references():
    return {"specializations":SPECIALIZATIONS,"grades":GRADES,
            "skills":["Python","FastAPI","Django","Flask","SQL","PostgreSQL","Docker","JavaScript","TypeScript","React","Vue","CSS","HTML","HTTP"],
            "demo":DEMO,"fsp_ids":list(REGISTRY) if DEMO else []}


class ProfileData(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    title:str=Field(max_length=120)
    industry:str=Field(max_length=100,default='Информационные технологии')
    about:str=Field(max_length=3000)
    phone:str=Field(max_length=40)
    telegram:str=Field(max_length=100)
    skills:list[str]=Field(max_length=30)
    experience:int=Field(ge=0,le=60)
    city:str=Field(max_length=100)
    salary:int=Field(ge=0,le=10000000)
    work_format:Literal["remote","hybrid","office","any"]
    team_role:str=Field(max_length=100)
    soft_skills:str=Field(max_length=1000)
    specialization:Literal["backend","frontend"]
    declared_grade:Literal["Junior","Middle","Senior"]
    published:StrictBool=False
    show_fsp:StrictBool=False
    @field_validator("skills")
    @classmethod
    def validate_skills(cls,value):
        if any(len(s)>50 or not s.strip() for s in value):raise ValueError("Некорректный навык")
        return list(dict.fromkeys(s.strip() for s in value))


@app.get("/api/candidate/profile",tags=["Кандидат"])
def own_profile(user=Depends(candidate)):
    with db() as conn:return view_candidate(conn,user["id"],own=True)


@app.put("/api/candidate/profile",tags=["Кандидат"])
def save_profile(data:ProfileData,user=Depends(candidate)):
    with db() as conn:
        p=profile(conn,user["id"])
        p.update(data.model_dump())
        conn.execute("UPDATE profiles SET data=?,updated=? WHERE user_id=?",(dumps(p),time.time(),user["id"]))
        conn.execute("UPDATE users SET name=? WHERE id=?",(data.name,user["id"]))
        audit(conn,user["id"],"profile.updated",user["id"])
        return view_candidate(conn,user["id"],own=True)


@app.post("/api/candidate/consent/revoke",tags=["Кандидат"])
def revoke_consent(response:Response,user=Depends(candidate)):
    return withdraw_consent(response,user)


@app.post('/api/account/consent/revoke',tags=['Приватность'])
def withdraw_consent(response:Response,user=Depends(current)):
    with db() as conn:
        conn.execute("UPDATE users SET consent=0 WHERE id=?",(user["id"],))
        conn.execute("UPDATE grants SET revoked=1 WHERE candidate=? OR employer=?",(user["id"],user["id"]))
        conn.execute('UPDATE needs SET published=0 WHERE employer=?',(user['id'],))
        conn.execute("UPDATE invitations SET status='withdrawn',updated=? WHERE employer=? AND status IN ('sent','viewed')",(time.time(),user['id']))
        conn.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
        audit(conn,user["id"],"consent.revoked",CONSENT_VERSION)
    response.delete_cookie("fsp_session",path="/")
    return {"ok":True}


class FspData(BaseModel):
    fsp_id:str=Field(max_length=50)


class CodeData(BaseModel):
    code:str=Field(min_length=6,max_length=6)


@app.post("/api/candidate/fsp/link",tags=["ФСП"])
def link_fsp(data:FspData,user=Depends(candidate)):
    if not DEMO:raise HTTPException(503,"Реестр ФСП пока не подключён")
    if data.fsp_id not in REGISTRY:raise HTTPException(404,"ID не найден в демо-реестре")
    code=f"{secrets.randbelow(1000000):06}"
    with db() as conn:
        p=profile(conn,user["id"])
        p.update(fsp_pending=data.fsp_id,fsp_code=digest(code),fsp_code_expires=time.time()+900)
        conn.execute("UPDATE profiles SET data=? WHERE user_id=?",(dumps(p),user["id"]))
    return {"dev_code":code,"message":"Демо-код подтверждения владения ID"}


@app.post("/api/candidate/fsp/confirm",tags=["ФСП"])
def confirm_fsp(data:CodeData,user=Depends(candidate)):
    with db() as conn:
        p=profile(conn,user["id"])
        if p.get("fsp_code_expires",0)<time.time() or not hmac.compare_digest(p.get("fsp_code",""),digest(data.code)):raise HTTPException(400,"Код неверный или просрочен")
        p["fsp_id"]=p.pop("fsp_pending")
        p.pop("fsp_code",None);p.pop("fsp_code_expires",None)
        conn.execute("UPDATE profiles SET data=?,updated=? WHERE user_id=?",(dumps(p),time.time(),user["id"]))
        audit(conn,user["id"],"fsp.linked",p["fsp_id"])
        return {"achievements":achievements(p),"fsp_id":p["fsp_id"]}


@app.delete("/api/candidate/fsp",tags=["ФСП"])
def unlink_fsp(user=Depends(candidate)):
    with db() as conn:
        p=profile(conn,user["id"]);p["fsp_id"]=None
        conn.execute("UPDATE profiles SET data=? WHERE user_id=?",(dumps(p),user["id"]))
    return {"ok":True}


class TestChoice(BaseModel):
    specialization:Literal['backend','frontend']
    grade:Literal['Junior','Middle','Senior']


class AnswersData(BaseModel):
    version:int=Field(ge=0)
    answers:dict[str,str]


def eligibility(conn,uid,spec,grade):
    now=time.time()
    cat=conn.execute('SELECT * FROM categories WHERE user_id=? AND spec=?',(uid,spec)).fetchone()
    last=conn.execute("SELECT * FROM attempts WHERE user_id=? AND spec=? AND grade=? AND status='finished' ORDER BY created DESC LIMIT 1",(uid,spec,grade)).fetchone()
    if last and last['created']+30*86400>now:
        return False,'Повтор этого теста доступен через 30 дней после предыдущей попытки'
    if cat and grade!=cat['grade'] and cat['verified_at']+90*86400>now:
        promotion=GRADES.index(grade)==GRADES.index(cat['grade'])+1 and cat['upgrade_until']>now
        failed=conn.execute("SELECT grade,result FROM attempts WHERE user_id=? AND spec=? AND status='finished' ORDER BY created DESC LIMIT 1",(uid,spec)).fetchone()
        lower_after_failure=failed and not loads(failed['result']).get('passed') and GRADES.index(grade)<GRADES.index(failed['grade'])
        if not promotion and not lower_after_failure:return False,'Смена подтверждённой категории доступна через 90 дней; уверенный результат открывает следующий уровень'
    return True,''


def attempt_view(row):
    return {'id':row['id'],'specialization':row['spec'],'grade':row['grade'],'deadline':row['deadline'],
            'questions':public_questions(loads(row['questions'])),'answers':loads(row['answers']),'version':row['version'],'status':row['status'],'result':loads(row['result'])}


@app.get('/api/candidate/tests',tags=['Тестирование'])
def test_status(user=Depends(candidate)):
    with db() as conn:
        active=conn.execute("SELECT * FROM attempts WHERE user_id=? AND status='active'",(user['id'],)).fetchone()
        history=[{'id':r['id'],'specialization':r['spec'],'grade':r['grade'],'created':r['created'],'status':r['status'],'result':loads(r['result'])} for r in conn.execute("SELECT * FROM attempts WHERE user_id=? AND status!='active' ORDER BY created DESC LIMIT 10",(user['id'],))]
        available=[{'specialization':s,'grade':g,'allowed':eligibility(conn,user['id'],s,g)[0],'reason':eligibility(conn,user['id'],s,g)[1]} for s in SPECIALIZATIONS for g in GRADES]
        return {'active':attempt_view(active) if active else None,'history':history,'eligibility':available}


@app.post('/api/candidate/tests',tags=['Тестирование'])
def start_test(data:TestChoice,user=Depends(candidate)):
    with db() as conn:
        active=conn.execute("SELECT * FROM attempts WHERE user_id=? AND status='active'",(user['id'],)).fetchone()
        if active:
            if active['deadline']>time.time():return attempt_view(active)
            conn.execute("UPDATE attempts SET status='expired' WHERE id=?",(active['id'],))
        allowed,reason=eligibility(conn,user['id'],data.specialization,data.grade)
        if not allowed:raise HTTPException(409,reason)
        uid=secrets.token_urlsafe(18);now=time.time()
        questions=generate(data.specialization,data.grade,secrets.randbits(64))
        conn.execute("INSERT INTO attempts(id,user_id,spec,grade,created,deadline,status,questions,answers) VALUES(?,?,?,?,?,?,'active',?,'{}')",(uid,user['id'],data.specialization,data.grade,now,now+30*60,dumps(questions)))
        audit(conn,user['id'],'test.started',uid)
        return attempt_view(conn.execute('SELECT * FROM attempts WHERE id=?',(uid,)).fetchone())


def owned_attempt(conn,uid,attempt_id):
    row=conn.execute('SELECT * FROM attempts WHERE id=? AND user_id=?',(attempt_id,uid)).fetchone()
    if not row:raise HTTPException(404,'Попытка не найдена')
    return row


@app.put('/api/candidate/tests/{attempt_id}/answers',tags=['Тестирование'])
def save_answers(attempt_id:str,data:AnswersData,user=Depends(candidate)):
    with db() as conn:
        row=owned_attempt(conn,user['id'],attempt_id)
        if row['status']!='active' or row['deadline']<time.time():raise HTTPException(409,'Тест уже завершён или время истекло')
        if data.version!=row['version']:raise HTTPException(409,'Ответы изменились на другом устройстве. Обновите страницу.')
        questions={q['id']:q for q in loads(row['questions'])}
        for key,value in data.answers.items():
            if key not in questions or len(value)>256 or (questions[key].get('options') and value not in questions[key]['options']):raise HTTPException(422,'Недопустимый ответ')
        answers=loads(row['answers']);answers.update(data.answers)
        conn.execute('UPDATE attempts SET answers=?,version=version+1 WHERE id=?',(dumps(answers),attempt_id))
        return {'version':row['version']+1,'saved':len(answers)}


@app.post('/api/candidate/tests/{attempt_id}/finish',tags=['Тестирование'])
def finish_test(attempt_id:str,user=Depends(candidate)):
    with db() as conn:
        row=owned_attempt(conn,user['id'],attempt_id)
        if row['status']=='finished':return loads(row['result'])
        if row['status']!='active':raise HTTPException(409,'Попытка закрыта')
        questions=loads(row['questions']);result=evaluate(questions,loads(row['answers']),row['grade'])
        passed_topics={t['name'] for t in result['topics'] if t['score']>=60}
        result.update(specialization=row['spec'],grade=row['grade'],verified_skills=sorted({q['skill'] for q in questions if q['topic'] in passed_topics}))
        now=time.time()
        conn.execute("UPDATE attempts SET status='finished',result=?,version=version+1 WHERE id=?",(dumps(result),attempt_id))
        if result['passed']:
            conn.execute('INSERT INTO categories(user_id,spec,grade,data,verified_at,upgrade_until) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,spec) DO UPDATE SET grade=excluded.grade,data=excluded.data,verified_at=excluded.verified_at,upgrade_until=excluded.upgrade_until',
                (user['id'],row['spec'],row['grade'],dumps(result),now,now+14*86400 if result['strong'] else 0))
        audit(conn,user['id'],'test.finished',attempt_id)
        notify(conn,user['id'],'Результат теста готов',f"{SPECIALIZATIONS[row['spec']]} · {row['grade']} · {result['score']}%")
        return result


class CompanyData(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    description:str=Field(max_length=3000)
    contact:str=Field(min_length=3,max_length=200)
    website:str=Field(max_length=200,default='')
    industry:str=Field(max_length=100,default='Продуктовая разработка')


@app.get('/api/employer/company',tags=['Компания'])
def get_company(user=Depends(employer)):
    with db() as conn:return company(conn,user['id'])


@app.put('/api/employer/company',tags=['Компания'])
def save_company(data:CompanyData,user=Depends(employer)):
    with db() as conn:conn.execute('UPDATE companies SET data=? WHERE user_id=?',(dumps(data.model_dump()),user['id']))
    return data.model_dump()


class NeedData(BaseModel):
    title:str=Field(min_length=3,max_length=120)
    specialization:Literal['backend','frontend']
    grade:Literal['Junior','Middle','Senior']
    skills:list[str]=Field(max_length=20)
    description:str=Field(min_length=20,max_length=5000)
    salary_from:int=Field(ge=1,le=10_000_000)
    salary_to:int=Field(ge=1,le=10_000_000)
    work_format:Literal['remote','hybrid','office']
    city:str=Field(max_length=100,default='')
    published:bool=False
    @field_validator('salary_to')
    @classmethod
    def range_check(cls,value,info):
        if value<info.data.get('salary_from',0):raise ValueError('Верхняя граница зарплаты меньше нижней')
        return value
    @field_validator('skills')
    @classmethod
    def skills_check(cls,value):return ProfileData.validate_skills(value)


def need_view(row,conn):
    return dict(loads(row['data']),id=row['id'],published=bool(row['published']),company=company(conn,row['employer']),employer=row['employer'])


@app.get('/api/employer/needs',tags=['Потребности'])
def list_needs(user=Depends(employer)):
    with db() as conn:return [need_view(r,conn) for r in conn.execute('SELECT * FROM needs WHERE employer=? ORDER BY id DESC',(user['id'],))]


@app.post('/api/employer/needs',tags=['Потребности'])
def create_need(data:NeedData,user=Depends(employer)):
    p=data.model_dump();published=p.pop('published')
    with db() as conn:
        uid=conn.execute('INSERT INTO needs(employer,data,published,created) VALUES(?,?,?,?)',(user['id'],dumps(p),published,time.time())).lastrowid
        return need_view(conn.execute('SELECT * FROM needs WHERE id=?',(uid,)).fetchone(),conn)


@app.put('/api/employer/needs/{need_id}',tags=['Потребности'])
def edit_need(need_id:int,data:NeedData,user=Depends(employer)):
    p=data.model_dump();published=p.pop('published')
    with db() as conn:
        if not conn.execute('SELECT id FROM needs WHERE id=? AND employer=?',(need_id,user['id'])).fetchone():raise HTTPException(404,'Потребность не найдена')
        conn.execute('UPDATE needs SET data=?,published=? WHERE id=?',(dumps(p),published,need_id))
    return {'ok':True}


@app.get('/api/employer/candidates',tags=['Подбор'])
def find_candidates(need_id:int|None=None,specialization:Literal['backend','frontend']='backend',grade:Literal['Junior','Middle','Senior']='Middle',q:str='',fsp:bool=False,user=Depends(employer)):
    with db() as conn:
        if need_id:
            row=conn.execute('SELECT * FROM needs WHERE id=? AND employer=?',(need_id,user['id'])).fetchone()
            if not row:raise HTTPException(404,'Потребность не найдена')
            need=loads(row['data'])
        else:need={'specialization':specialization,'grade':grade,'skills':[],'salary_to':0,'work_format':''}
        result=[]
        for row in conn.execute('SELECT u.id,p.data,p.updated FROM profiles p JOIN users u ON u.id=p.user_id WHERE u.consent=1 AND u.verified=1'):
            p=loads(row['data'])
            if not p.get('published'):continue
            a=achievements(p)
            if fsp and not a:continue
            if q and q.lower() not in (' '.join(p.get('skills',[]))+' '+p.get('title','')+' '+p.get('about','')).lower():continue
            cats=categories(conn,row['id'])
            freshness=max(.25,1-(time.time()-row['updated'])/(86400*180))
            match=rank_candidate(p,need,cats,a,freshness)
            if match:result.append(dict(view_candidate(conn,row['id'],user['id']),match=match))
        return {'candidates':sorted(result,key=lambda p:(-p['match']['score'],p['id'])),'need':need,'total':len(result)}


@app.get('/api/employer/candidates/{candidate_id}',tags=['Подбор'])
def candidate_detail(candidate_id:int,user=Depends(employer)):
    with db() as conn:return view_candidate(conn,candidate_id,user['id'])


class InvitationData(BaseModel):
    candidate_id:int
    title:str=Field(min_length=3,max_length=120)
    description:str=Field(min_length=20,max_length=3000)
    salary_from:int=Field(ge=1,le=10_000_000)
    salary_to:int=Field(ge=1,le=10_000_000)
    contact:str=Field(min_length=3,max_length=200)
    work_format:Literal['remote','hybrid','office']
    @field_validator('salary_to')
    @classmethod
    def salary_check(cls,value,info):return NeedData.range_check(value,info)


@app.post('/api/employer/invitations',tags=['Приглашения'])
def invite(data:InvitationData,user=Depends(employer)):
    with db() as conn:
        view_candidate(conn,data.candidate_id,user['id'])
        if not categories(conn,data.candidate_id):raise HTTPException(409,'У кандидата пока нет подтверждённой категории')
        p=data.model_dump();p.pop('candidate_id')
        try:uid=conn.execute("INSERT INTO invitations(employer,candidate,data,status,created,updated) VALUES(?,?,?,'sent',?,?)",(user['id'],data.candidate_id,dumps(p),time.time(),time.time())).lastrowid
        except sqlite3.IntegrityError:raise HTTPException(409,'У этого кандидата уже есть активное приглашение от вашей компании')
        notify(conn,data.candidate_id,'Приглашение от '+company(conn,user['id'])['name'],p['title'],related_user=user['id'])
        audit(conn,user['id'],'invitation.sent',uid)
        return {'id':uid,'status':'sent'}


@app.get('/api/invitations',tags=['Приглашения'])
def invitations(user=Depends(current)):
    with db() as conn:
        conn.execute("UPDATE invitations SET status='expired',updated=? WHERE status IN ('sent','viewed') AND created<?",(time.time(),time.time()-14*86400))
        column='candidate' if user['role']=='candidate' else 'employer'
        out=[]
        for r in conn.execute(f'SELECT * FROM invitations WHERE {column}=? ORDER BY created DESC',(user['id'],)):
            item=dict(loads(r['data']),id=r['id'],status=r['status'],created=r['created'],employer=r['employer'],company=company(conn,r['employer']),candidate_id=r['candidate'],contacts_open=has_contacts(conn,r['employer'],r['candidate']))
            if user['role']=='employer':
                try:item['candidate']=view_candidate(conn,r['candidate'],user['id'])
                except HTTPException:item['candidate']={'id':r['candidate'],'name':'Профиль скрыт','contacts_open':False}
            out.append(item)
        return out


class Decision(BaseModel):
    status:Literal['viewed','accepted','declined','withdrawn']
    share_contacts:StrictBool=False


@app.patch('/api/invitations/{invitation_id}',tags=['Приглашения'])
def respond(invitation_id:int,data:Decision,user=Depends(current)):
    with db() as conn:
        r=conn.execute('SELECT * FROM invitations WHERE id=?',(invitation_id,)).fetchone()
        owner=r and (r['candidate']==user['id'] if user['role']=='candidate' else r['employer']==user['id'])
        if not owner:raise HTTPException(404,'Приглашение не найдено')
        if data.status==r['status']:return {'status':r['status']}
        if r['status'] not in {'sent','viewed'} or r['created']<time.time()-14*86400:raise HTTPException(409,'Приглашение уже закрыто')
        if user['role']=='candidate':
            if data.status=='withdrawn':raise HTTPException(403,'Недопустимое действие')
            if data.status=='accepted':
                if not data.share_contacts:raise HTTPException(422,'Подтвердите отдельное разрешение на контакты')
                conn.execute('INSERT INTO grants(employer,candidate,created) VALUES(?,?,?) ON CONFLICT(employer,candidate) DO UPDATE SET revoked=0,created=excluded.created',(r['employer'],user['id'],time.time()))
        elif data.status!='withdrawn':raise HTTPException(403,'Работодатель может только отозвать приглашение')
        conn.execute('UPDATE invitations SET status=?,updated=? WHERE id=?',(data.status,time.time(),invitation_id))
        notify(conn,r['employer'] if user['role']=='candidate' else r['candidate'],'Статус приглашения изменился',data.status,related_user=user['id'])
        audit(conn,user['id'],'invitation.'+data.status,invitation_id)
    return {'status':data.status}


@app.get('/api/candidate/contacts',tags=['Приватность'])
def contact_grants(user=Depends(candidate)):
    with db() as conn:return [dict(company(conn,r['employer']),employer=r['employer'],created=r['created']) for r in conn.execute('SELECT * FROM grants WHERE candidate=? AND revoked=0',(user['id'],))]


@app.delete('/api/candidate/contacts/{employer_id}',tags=['Приватность'])
def revoke_contacts(employer_id:int,user=Depends(candidate)):
    with db() as conn:
        conn.execute('UPDATE grants SET revoked=1 WHERE candidate=? AND employer=?',(user['id'],employer_id))
        audit(conn,user['id'],'contacts.revoked',employer_id)
    return {'ok':True}


@app.get('/api/jobs',tags=['Вакансии'])
def jobs(user=Depends(current)):
    with db() as conn:
        return [dict(need_view(r,conn),applied=bool(conn.execute('SELECT id FROM applications WHERE need_id=? AND candidate=?',(r['id'],user['id'])).fetchone())) for r in conn.execute('SELECT * FROM needs WHERE published=1 ORDER BY created DESC')]


class ApplyData(BaseModel):
    share_contacts:StrictBool


@app.post('/api/jobs/{need_id}/apply',tags=['Вакансии'])
def apply_job(need_id:int,data:ApplyData,user=Depends(candidate)):
    if not data.share_contacts:raise HTTPException(422,'Для отклика подтвердите передачу контактов этой компании')
    with db() as conn:
        need=conn.execute('SELECT * FROM needs WHERE id=? AND published=1',(need_id,)).fetchone()
        if not need:raise HTTPException(404,'Вакансия не найдена')
        if not profile(conn,user['id']).get('published'):raise HTTPException(409,'Сначала опубликуйте профиль')
        existing=conn.execute('SELECT id FROM applications WHERE need_id=? AND candidate=?',(need_id,user['id'])).fetchone()
        if existing:return {'id':existing['id']}
        uid=conn.execute("INSERT INTO applications(need_id,candidate,employer,status,created) VALUES(?,?,?,'sent',?)",(need_id,user['id'],need['employer'],time.time())).lastrowid
        conn.execute('INSERT INTO grants(employer,candidate,created) VALUES(?,?,?) ON CONFLICT(employer,candidate) DO UPDATE SET revoked=0,created=excluded.created',(need['employer'],user['id'],time.time()))
        notify(conn,need['employer'],'Новый отклик',loads(need['data'])['title'],related_user=user['id'])
        audit(conn,user['id'],'job.applied',need_id)
        return {'id':uid}


@app.get('/api/applications',tags=['Вакансии'])
def applications(user=Depends(current)):
    column='candidate' if user['role']=='candidate' else 'employer'
    with db() as conn:
        out=[]
        for r in conn.execute(f'SELECT * FROM applications WHERE {column}=? ORDER BY created DESC',(user['id'],)):
            n=conn.execute('SELECT * FROM needs WHERE id=?',(r['need_id'],)).fetchone()
            item={'id':r['id'],'need':need_view(n,conn),'created':r['created'],'status':r['status']}
            if user['role']=='employer':
                try:item['candidate']=view_candidate(conn,r['candidate'],user['id'])
                except HTTPException:item['candidate']={'name':'Профиль скрыт','id':r['candidate']}
            out.append(item)
        return out


class TaskData(BaseModel):
    title:str=Field(min_length=3,max_length=120)
    specialization:Literal['backend','frontend']
    grade:Literal['Junior','Middle','Senior']
    description:str=Field(min_length=30,max_length=5000)
    topic:str=Field(max_length=100,default='')
    keywords:list[str]=Field(max_length=10,default=[])
    rubric:list[str]=Field(default=['Корректность','Полнота','Обоснование'],min_length=3,max_length=3)


@app.post('/api/employer/tasks',tags=['Задания недели'])
def create_task(data:TaskData,user=Depends(employer)):
    with db() as conn:
        uid=conn.execute('INSERT INTO tasks(employer,data,created) VALUES(?,?,?)',(user['id'],dumps(data.model_dump()),time.time())).lastrowid
    return {'id':uid}


@app.get('/api/tasks',tags=['Задания недели'])
def list_tasks(user=Depends(current)):
    with db() as conn:
        if user['role']=='employer':
            out=[]
            for r in conn.execute('SELECT * FROM tasks WHERE employer=? ORDER BY created DESC',(user['id'],)):
                submissions=[]
                for a in conn.execute('SELECT * FROM task_answers WHERE employer=? AND assignment IN (SELECT id FROM assignments WHERE task=?)',(user['id'],r['id'])):
                    try:p=view_candidate(conn,a['candidate'],user['id'])
                    except HTTPException:p={'name':'Профиль скрыт','id':a['candidate']}
                    submissions.append(dict(id=a['id'],answer=a['answer'],score=a['score'],feedback=a['feedback'],candidate=p))
                out.append(dict(loads(r['data']),id=r['id'],submissions=submissions))
            return out
        cats=categories(conn,user['id'])
        last=conn.execute('SELECT created FROM assignments WHERE candidate=? ORDER BY created DESC LIMIT 1',(user['id'],)).fetchone()
        if cats and (not last or last['created']<time.time()-7*86400):
            choices=[]
            for r in conn.execute('SELECT t.* FROM tasks t JOIN users u ON u.id=t.employer WHERE u.consent=1 AND t.id NOT IN (SELECT task FROM assignments WHERE candidate=?)',(user['id'],)):
                t=loads(r['data']);cat=next((c for c in cats if c['specialization']==t['specialization'] and c['grade']==t['grade']),None)
                if cat:choices.append((r,t,cat))
            if choices:
                def weakness(choice):
                    _,task,category=choice
                    return next((topic['score'] for topic in category.get('topics',[]) if topic['name']==task.get('topic')),101)
                r,t,cat=min(choices,key=weakness)
                topic=t.get('topic') or 'Практика'
                score=next((x['score'] for x in cat.get('topics',[]) if x['name']==topic),None)
                reason=f"Категория {cat['grade']} · тема «{topic}»"+(f' · результат теста {score}%' if score is not None else '')
                conn.execute("INSERT INTO assignments(task,candidate,created,deadline,status,reason) VALUES(?,?,?,?,'assigned',?)",(r['id'],user['id'],time.time(),time.time()+7*86400,reason))
                notify(conn,user['id'],'Задание недели доступно',t['title'],related_user=r['employer'])
        out=[]
        for r in conn.execute('SELECT a.*,t.data,t.employer FROM assignments a JOIN tasks t ON t.id=a.task WHERE candidate=? ORDER BY a.created DESC',(user['id'],)):
            t=loads(r['data']);t.pop('keywords',None)
            answer=conn.execute('SELECT * FROM task_answers WHERE assignment=?',(r['id'],)).fetchone()
            out.append(dict(t,id=r['id'],company=company(conn,r['employer']),deadline=r['deadline'],status=r['status'],reason=r['reason'],answer=dict(answer) if answer else None))
        return out


class TaskAnswerData(BaseModel):
    answer:str=Field(min_length=20,max_length=8000)


@app.post('/api/tasks/{assignment_id}/answer',tags=['Задания недели'])
def answer_task(assignment_id:int,data:TaskAnswerData,user=Depends(candidate)):
    with db() as conn:
        a=conn.execute('SELECT a.*,t.employer,t.data FROM assignments a JOIN tasks t ON t.id=a.task WHERE a.id=? AND a.candidate=?',(assignment_id,user['id'])).fetchone()
        if not a:raise HTTPException(404,'Задание не найдено')
        if not conn.execute('SELECT id FROM users WHERE id=? AND consent=1',(a['employer'],)).fetchone():raise HTTPException(409,'Аккаунт работодателя деактивирован')
        if a['status']!='assigned' or a['deadline']<time.time():raise HTTPException(409,'Задание закрыто или срок истёк')
        uid=conn.execute('INSERT INTO task_answers(assignment,candidate,employer,answer,created) VALUES(?,?,?,?,?)',(assignment_id,user['id'],a['employer'],data.answer,time.time())).lastrowid
        conn.execute("UPDATE assignments SET status='submitted' WHERE id=?",(assignment_id,))
        notify(conn,a['employer'],'Ответ на задание недели',loads(a['data'])['title'],related_user=user['id'])
        return {'id':uid}


class ReviewData(BaseModel):
    correctness:int=Field(ge=0,le=2)
    completeness:int=Field(ge=0,le=2)
    reasoning:int=Field(ge=0,le=2)
    feedback:str=Field(min_length=10,max_length=3000)


@app.put('/api/employer/task-answers/{answer_id}',tags=['Задания недели'])
def review_task(answer_id:int,data:ReviewData,user=Depends(employer)):
    score=round((data.correctness+data.completeness+data.reasoning)/6*100)
    with db() as conn:
        a=conn.execute('SELECT * FROM task_answers WHERE id=? AND employer=?',(answer_id,user['id'])).fetchone()
        if not a:raise HTTPException(404,'Ответ не найден')
        conn.execute('UPDATE task_answers SET score=?,feedback=? WHERE id=?',(score,data.feedback,answer_id))
        conn.execute("UPDATE assignments SET status='reviewed' WHERE id=?",(a['assignment'],))
        conn.execute('UPDATE profiles SET updated=? WHERE user_id=?',(time.time(),a['candidate']))
        notify(conn,a['candidate'],'Проверено задание недели',f'{score}% · '+data.feedback,related_user=user['id'])
    return {'score':score}


@app.get('/api/notifications',tags=['Уведомления'])
def notifications(user=Depends(current)):
    with db() as conn:return [dict(r) for r in conn.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 40',(user['id'],))]


@app.post('/api/notifications/read',tags=['Уведомления'])
def read_notifications(user=Depends(current)):
    with db() as conn:conn.execute('UPDATE notifications SET seen=1 WHERE user_id=?',(user['id'],))
    return {'ok':True}


def profile_pdf(p):
    fonts=[ROOT/'fonts/DejaVuSans.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font=next((f for f in fonts if f.exists()),None)
    if font is None:raise HTTPException(503,'Для PDF установите шрифт DejaVu Sans')
    if 'ProfileFont' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('ProfileFont',str(font)))
    buf=io.BytesIO();doc=SimpleDocTemplate(buf,title='Профиль · ФСП Таланты',author='ФСП Таланты',topMargin=42,bottomMargin=42)
    styles=getSampleStyleSheet()
    for s in styles.byName.values():s.fontName='ProfileFont'
    styles['Title'].textColor=colors.HexColor('#2457e7')
    styles['BodyText'].leading=16
    flow=[]
    def line(text,style='BodyText'):flow.append(Paragraph(escape(str(text).replace('₽','руб.')),styles[style]));flow.append(Spacer(1,10))
    line('ФСП ТАЛАНТЫ','Heading2');line(p['name'],'Title');line(p.get('title',''),'Heading2')
    line('Проверяемые навыки. Возможности, которые находят вас.')
    for c in p['categories']:
        line(f"{SPECIALIZATIONS[c['specialization']]} · {c['grade']} · тест {c['score']}%",'Heading2')
        line('Подтверждённые навыки: '+', '.join(c.get('verified_skills',[])))
        line('Источник: '+c.get('source','Параметрический тест платформы'))
    line(p.get('about',''))
    line('Стек: '+', '.join(p.get('skills',[])))
    line(f"Город: {p.get('city','')} · Опыт: {p.get('experience',0)} лет · Ожидания: {p.get('salary',0):,} ₽")
    line('Командная роль: '+p.get('team_role',''));line('Гибкие навыки: '+p.get('soft_skills',''))
    if p['achievements']:
        line('Достижения ФСП','Heading2')
        for a in p['achievements']:line(a['event']+' · '+a['result']+' · '+a['source'])
    else:line('История ФСП отсутствует или скрыта участником.')
    if p['contacts_open']:
        line('Контакты','Heading2')
        for key,value in p['contacts'].items():
            if value:line(f'{key}: {value}')
    else:line('Контакты скрыты. Для связи отправьте приглашение через платформу.')
    if DEMO:line('Демонстрационная среда. Реестр ФСП и начальные профили синтетические.')
    doc.build(flow);buf.seek(0)
    return StreamingResponse(buf,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="talent-{p["id"]}.pdf"','Cache-Control':'no-store'})


@app.get('/api/candidate/profile.pdf',tags=['PDF'])
def own_pdf(user=Depends(candidate)):
    with db() as conn:p=view_candidate(conn,user['id'],own=True)
    return profile_pdf(p)


@app.get('/api/employer/candidates/{candidate_id}/profile.pdf',tags=['PDF'])
def employer_pdf(candidate_id:int,user=Depends(employer)):
    with db() as conn:p=view_candidate(conn,candidate_id,user['id'])
    return profile_pdf(p)


@app.get('/api/health',tags=['Система'])
def health():return {'status':'ok','demo':DEMO,'version':'1.0.0'}


app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')


@app.get('/docs',include_in_schema=False)
def api_documentation():return FileResponse(ROOT/'static/api.html')


@app.get('/',include_in_schema=False)
def index():return FileResponse(ROOT/'static/index.html',headers={'Cache-Control':'no-cache'})


@app.get('/{page:path}', include_in_schema=False)
def frontend_page(page: str):
    if page.startswith('api/') or page == 'api':
        return JSONResponse({'detail': 'Not Found'}, status_code=404)
    public_pages = {'terms', 'privacy', 'cookies', 'help', 'accessibility', 'login', 'register', 'home','refunds','consent','operator','deletion','licenses'}
    status = 200 if page.strip('/') in public_pages else 404
    return FileResponse(ROOT/'static/index.html', status_code=status, headers={'Cache-Control': 'no-cache'})
