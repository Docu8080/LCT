"""An explainable fit index, not a probability of successful hiring."""
from assessment import GRADES, SPECIALIZATIONS

SKILL_NEIGHBORS = {"FastAPI": {"Flask":0.6,"Django":0.5}, "React": {"Vue":0.6},
                   "PostgreSQL": {"SQL":0.8,"MySQL":0.7}, "TypeScript":{"JavaScript":0.8}}


def rank_candidate(profile, need, categories, achievements, freshness=1.0):
    spec = need.get("specialization", "backend")
    category = next((c for c in categories if c["specialization"]==spec),None)
    if category is None: return None
    grade = need.get("grade","Middle")
    distance = abs(GRADES.index(category["grade"])-GRADES.index(grade))
    if distance > 1: return None
    wanted = need.get("skills",[])
    have = {s.lower() for s in profile.get("skills",[])}
    hits,missing,near = [],[],[]
    values=[]
    for skill in wanted:
        if skill.lower() in have:
            hits.append(skill)
            # A matching skill supported by the test has full evidence weight.
            values.append(1 if skill.lower() in {s.lower() for s in category.get("verified_skills",[])} else 0.75)
        else:
            close = max((v for s,v in SKILL_NEIGHBORS.get(skill,{}).items() if s.lower() in have),default=0)
            values.append(close)
            (near if close else missing).append(skill)
    stack = sum(values)/len(values) if values else None
    salary = profile.get("salary",0)
    salary_fit = None if not salary or not need.get("salary_to") else min(1,need["salary_to"]/salary)
    fmt = None if need.get("work_format") in {None,"","any"} else (1 if profile.get("work_format") in {need["work_format"],"any"} else 0.35)
    fsp = min(1,0.5+sum(a.get("strength",0.15) for a in achievements)) if achievements else 0.5
    parts=[("Категория",0.30,1 if distance==0 else 0.55),
           ("Результат теста",0.25,category.get("score",0)/100),
           ("Стек",0.20,stack),("Достижения ФСП",0.10,fsp),
           ("Зарплатные ожидания",0.05,salary_fit),("Формат работы",0.05,fmt),
           ("Актуальность",0.05,freshness)]
    total_weight=sum(w for _,w,v in parts if v is not None)
    score=round(100*sum(w*v for _,w,v in parts if v is not None)/total_weight)
    reasons=[f"{SPECIALIZATIONS[spec]} · {category['grade']}: "+("категория совпадает" if not distance else "соседний грейд")]
    if hits:reasons.append("Совпадает стек: "+", ".join(hits))
    if near:reasons.append("Смежный опыт: "+", ".join(near))
    if missing:reasons.append("Стоит уточнить: "+", ".join(missing))
    reasons.append(f"Тест: {category.get('score',0)} из 100")
    reasons.append(f"{len(achievements)} подтверждённых демо-достижения ФСП" if achievements else "Нет истории ФСП — нейтральный вклад")
    return {"score":score,"category":category,"reasons":reasons,
            "breakdown":[{"name":name,"value":round(v*100),"weight":round(w/total_weight*100),"points":round(w*v/total_weight*100,1)} for name,w,v in parts if v is not None]}
