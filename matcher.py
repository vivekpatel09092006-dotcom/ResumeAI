import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILLS = [
"python","sql","mysql","postgresql","mongodb","nosql","pandas","numpy","matplotlib",
"seaborn","scikit-learn","machine learning","deep learning","artificial intelligence",
"nlp","power bi","tableau","excel","statistics","data analysis","data visualization",
"flask","django","fastapi","java","c++","javascript","html","css","react","git","github",
"docker","aws","azure","spark","hadoop","tensorflow","pytorch","communication",
"problem solving","data structures","algorithms","rest api","linux","cloud computing",
"dbms","oop","spring boot","kafka","airflow"
]
SECTIONS = ["summary","objective","education","skills","projects","experience","internship",
            "certifications","achievements","contact","email","phone","linkedin","github"]

def norm(s): return re.sub(r"\s+", " ", s.lower()).strip()

def find_terms(text, terms):
    t = norm(text)
    return sorted({x for x in terms if re.search(r"\b"+re.escape(x)+r"\b", t)})

def analyze_match(resume_text, jd_text):
    r, j = norm(resume_text), norm(jd_text)
    try:
        sim = float(cosine_similarity(TfidfVectorizer(stop_words="english").fit_transform([r,j]))[0,1] * 100)
    except Exception:
        sim = 0.0
    jd_skills = find_terms(j, SKILLS)
    resume_skills = find_terms(r, SKILLS)
    matching = [s for s in jd_skills if s in resume_skills]
    missing = [s for s in jd_skills if s not in resume_skills]
    skill_rate = (len(matching)/len(jd_skills)*100) if jd_skills else sim
    keywords = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.-]{2,}\b", j)
    stop = {"the","and","for","with","that","this","are","you","your","from","our","will","have","has","job","role","work","team","looking","into","about","using","years","year"}
    kw = []
    for x in keywords:
        x=x.lower()
        if x not in stop and x not in kw: kw.append(x)
    kw = kw[:30]
    covered = [x for x in kw if x in r]
    keyword_rate = len(covered)/len(kw)*100 if kw else 0
    score = (sim*0.15 + skill_rate*0.55 + keyword_rate*0.30) if jd_skills else (sim*0.35 + keyword_rate*0.65)
    score = round(min(100,max(0,score)),1)

    section_hits = {s: bool(re.search(r"\b"+re.escape(s)+r"\b", r)) for s in SECTIONS}
    present_sections = sum(section_hits.values())
    ats = round(min(100, max(0, 45 + present_sections*5 + min(len(resume_skills),12)*2 + min(len(covered),10)*1.5)),1)
    if len(r) < 500: ats = max(35, ats-15)

    if jd_skills and skill_rate < 50:
        decision, reason = "REJECT", "Required-skill coverage is below 50%."
    elif score < 50:
        decision, reason = "REJECT", "Overall match score is below 50%."
    elif score >= 75 and (not jd_skills or skill_rate >= 70):
        decision, reason = "SHORTLIST", "Strong match across job text, skills and keywords."
    else:
        decision, reason = "REVIEW", "Moderate match; recruiter review is recommended."

    suggestions=[]
    if ats < 70: suggestions.append("Improve ATS readiness with clearer headings, measurable achievements and standard section names.")
    if missing: suggestions.append("Add or learn the missing job skills: " + ", ".join(missing[:8]) + ".")
    if keyword_rate < 65: suggestions.append("Use relevant keywords from the job description naturally in Skills and Projects.")
    if not section_hits["projects"]: suggestions.append("Add a Projects section with 2–3 relevant projects and technologies used.")
    if not section_hits["education"]: suggestions.append("Add a clearly labeled Education section.")
    if not section_hits["experience"] and not section_hits["internship"]: suggestions.append("Add internship, experience, or strong project evidence where applicable.")
    if not suggestions: suggestions.append("Good structure. Keep achievements measurable and tailor the resume for each job.")

    return {
        "score": score, "similarity": round(sim,1), "skill_score": round(skill_rate,1),
        "keyword_rate": round(keyword_rate,1), "ats_score": ats,
        "resume_skills": resume_skills, "matching_skills": matching, "missing_skills": missing,
        "decision": decision, "decision_reason": reason, "suggestions": suggestions,
        "keywords": kw, "covered_keywords": covered, "sections": section_hits
    }

