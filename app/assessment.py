"""Parametric forms: five items per topic, shared difficulty blueprint and EAP scoring."""
import math
import random

SPECIALIZATIONS = {"backend": "Бэкенд-разработка", "frontend": "Фронтенд-разработка"}
GRADES = ["Junior", "Middle", "Senior"]
CUTS = {"Junior": -0.8, "Middle": 0.15, "Senior": 1.05}
TOPICS = {"backend": ["Алгоритмы", "Данные и SQL", "API и архитектура"],
          "frontend": ["JavaScript", "Интерфейсы", "Веб-платформа"]}
BANK_VERSION = "1.0"


def probability(theta, b, guessing=0.02):
    return guessing + (1 - guessing) / (1 + math.exp(-1.5 * (theta - b)))


def posterior(questions, answers):
    grid = [-4 + i * 0.05 for i in range(161)]
    logs = []
    for theta in grid:
        logp = -0.5 * (theta / 1.5) ** 2
        for q in questions:
            correct = str(answers.get(q["id"], "")).strip().lower() == str(q["answer"]).strip().lower()
            p = probability(theta, q["difficulty"], 0.25 if q.get("options") else 0.02)
            logp += math.log(p if correct else 1 - p)
        logs.append(logp)
    maximum = max(logs)
    weights = [math.exp(x - maximum) for x in logs]
    total = sum(weights)
    weights = [x / total for x in weights]
    mean = sum(x * w for x, w in zip(grid, weights))
    se = math.sqrt(sum((x - mean) ** 2 * w for x, w in zip(grid, weights)))
    return mean, se, grid, weights


def evaluate(questions, answers, grade):
    theta, se, grid, weights = posterior(questions, answers)
    chance = sum(w for t, w in zip(grid, weights) if t >= CUTS[grade])
    correct = sum(str(answers.get(q["id"], "")).strip().lower() == str(q["answer"]).strip().lower()
                  for q in questions)
    topics = []
    for name in dict.fromkeys(q["topic"] for q in questions):
        items = [q for q in questions if q["topic"] == name]
        n = sum(str(answers.get(q["id"], "")).strip().lower() == str(q["answer"]).strip().lower() for q in items)
        topics.append({"name": name, "score": round(n / len(items) * 100), "correct": n, "total": len(items)})
    passed = chance >= 0.5
    return {"theta": round(theta, 3), "se": round(se, 3), "confidence": round(max(chance, 1-chance) * 100),
            "passed": passed, "strong": passed and chance >= 0.9,
            "score": round(100 * correct / len(questions)), "correct": correct, "total": len(questions),
            "grade": grade, "topics": topics, "bank_version": BANK_VERSION}


def item(rng, spec, topic, family, level):
    n, k = rng.randint(3, 9), rng.randint(2, 5)
    q = {"prompt": "", "code": "", "answer": "", "skill": "", "template": f"{spec}-{topic}-{family}-L{level}"}
    if spec == "backend":
        if topic == 0:
            q["skill"] = "Python"
            if family == 0:
                code = f"values = list(range({n}))\nprint(sum(x for x in values if x % {k} == 0))"
                answer = sum(x for x in range(n) if x % k == 0)
            elif family == 1:
                code = f"values = [{n}, {k}, {n}, {n+k}, {k}]\nprint(len(set(values)))" if level == 0 else f"values = [{n}, {k}, {n}, {n+k}, {k}]\nprint(sum(set(values)))"
                answer = 3 if level == 0 else 2*(n+k)
                if n == k:
                    answer = 2 if level == 0 else 3*n
            elif family == 2:
                code = f"x = {n}\nfor _ in range({k}):\n    x = x * 2 + {level}\nprint(x)"
                answer = n
                for _ in range(k): answer = answer * 2 + level
            else:
                code = f"a = list(range({n+k}))\nprint(sum(a[{k}::{level+2}]))"
                answer = sum(list(range(n+k))[k::level+2])
            q.update(prompt="Какое число выведет программа на Python 3?", code=code, answer=str(answer))
        elif topic == 1:
            q["skill"] = "SQL"
            rows = [(i, (i % k)+1) for i in range(1, n+1)]
            q["code"] = "orders(id, amount)\n" + "\n".join(f"{i} | {amount}" for i, amount in rows)
            if family == 0:
                sql = f"SELECT COUNT(*) FROM orders WHERE amount > {level+1};"
                answer = sum(v > level+1 for _,v in rows)
            elif family == 1:
                sql = f"SELECT COALESCE(SUM(amount), 0) FROM orders WHERE id % {level+2} = 0;"
                answer = sum(v for i,v in rows if i % (level+2) == 0)
            elif family == 2:
                sql = "SELECT COUNT(DISTINCT amount) FROM orders;"
                answer = len(set(v for _,v in rows))
            else:
                sql = f"SELECT MAX(amount) - MIN(amount) FROM orders WHERE id <= {k};"
                amounts = [v for i,v in rows if i <= k]
                answer = max(amounts)-min(amounts)
            q.update(prompt="Таблица приведена ниже. Какое число вернёт SQL-запрос?", answer=str(answer))
            q["code"] += "\n\n"+sql
        else:
            q["skill"] = "HTTP"
            if family == 0:
                q.update(prompt=f"API ограничен {n*10} запросами в минуту на клиента. Клиент отправляет {k*10} запросов за каждую из трёх минут. Сколько запросов суммарно будет отклонено? Лимит обнуляется каждую минуту.", answer=str(3*max(0,k*10-n*10)))
            elif family == 1:
                q.update(prompt=f"Сервис использует {k} обработчика. Каждый завершает запрос за {n*10} мс. Какова максимальная пропускная способность в запросах в секунду? Округлите вниз; накладных расходов нет.", answer=str(1000*k//(n*10)))
            elif family == 2:
                q.update(prompt=f"В каскаде ретраев после первой неудачи выполняются {level+2} повторных запроса. Пауза перед первым повтором {n} секунд, затем каждый раз удваивается. Сколько секунд суммарно занимает ожидание?", answer=str(n*(2**(level+2)-1)))
            else:
                q.update(prompt="Какой HTTP-статус подходит для успешного создания ресурса с возвратом его адреса в Location?", answer="201", options=["200","201","204","409"])
    else:
        if topic == 0:
            q["skill"] = "JavaScript"
            if family == 0:
                q.update(prompt="Какое число выведет JavaScript?", code=f"const a = [{n}, {k}, {n+k}];\nconsole.log(a.map(x => x * {level+2}).reduce((s, x) => s + x, 0));", answer=str(2*(n+k)*(level+2)))
            elif family == 1:
                q.update(prompt="Какое число выведет JavaScript?", code=f"const a = Array.from({{length: {n}}}, (_, i) => i);\nconsole.log(a.filter(x => x % {k} === 0).length);", answer=str(len([i for i in range(n) if i % k == 0])))
            elif family == 2:
                q.update(prompt="Какое число выведет JavaScript?", code=f"const a = [{n}, {k}, {n}, {n+k}];\nconsole.log([...new Set(a)].length);", answer=str(len(set([n,k,n,n+k]))))
            else:
                q.update(prompt="В каком порядке попадут сообщения в консоль?", code="console.log('A');\nsetTimeout(() => console.log('B'), 0);\nPromise.resolve().then(() => console.log('C'));", answer="ACB", options=["ABC","ACB","BAC","CAB"])
        elif topic == 1:
            q["skill"] = "CSS"
            if family == 0:
                width, pad = n*40, k*5
                q.update(prompt="Какова внешняя ширина элемента в пикселях без margin?", code=f".card {{ width: {width}px; padding: {pad}px; border: {level+1}px solid; box-sizing: content-box; }}", answer=str(width+2*pad+2*(level+1)))
            elif family == 1:
                width, gap, count = n*60, k*4, level+2
                q.update(prompt=f"Контейнер шириной {width}px содержит {count} одинаковых колонок и gap {gap}px. Какова ширина одной колонки? Укажите целую часть числа; padding нет.", answer=str((width-(count-1)*gap)//count))
            elif family == 2:
                q.update(prompt=f"В контейнере {n*20}px элемент занимает {k*10}%. Какова его ширина в пикселях?", answer=str(n*20*k*10//100))
            else:
                q.update(prompt="Какой HTML-элемент даёт нативную семантику действия, доступен с клавиатуры и подходит для отправки формы?", answer="button", options=["div","span","button","section"])
        else:
            q["skill"] = "HTTP"
            if family == 0:
                q.update(prompt=f"Ответ содержит Cache-Control: max-age={n*60}. Прошло {k*10} секунд с загрузки. Сколько секунд кеш ещё свежий?", answer=str(max(0,n*60-k*10)))
            elif family == 1:
                q.update(prompt=f"Страница грузит {n} файлов по {k*10} КБ и один файл {level*20+30} КБ. Сколько всего КБ передано?", answer=str(n*k*10+level*20+30))
            elif family == 2:
                q.update(prompt=f"Окно дебаунса {n*50} мс. События приходят в моменты 0, {k*10}, {k*20} мс. Когда сработает последний обработчик, если следующее событие отменяет предыдущий таймер? Укажите время от начала в мс.", answer=str(k*20+n*50))
            else:
                q.update(prompt="Какая cookie-настройка запрещает JavaScript читать значение cookie через document.cookie?", answer="HttpOnly", options=["HttpOnly","SameSite","Secure","Path"])
    return q


def generate(spec, grade, seed):
    rng = random.Random(seed)
    level = GRADES.index(grade)
    questions = []
    for topic in range(3):
        families = list(range(4)) + [rng.randrange(3)]
        rng.shuffle(families)
        for offset, family in enumerate(families):
            q = item(rng,spec,topic,family,level)
            q.update(id=f"q{len(questions)+1}", topic=TOPICS[spec][topic],
                     difficulty=round(CUTS[grade]+[-0.7,-0.35,0,0.35,0.7][offset],3))
            if q.get("options"): rng.shuffle(q["options"])
            questions.append(q)
    rng.shuffle(questions)
    return questions


def public_questions(questions):
    return [{k:v for k,v in q.items() if k not in {"answer","difficulty","template"}} for q in questions]
