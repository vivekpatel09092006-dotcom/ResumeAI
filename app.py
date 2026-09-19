from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from pathlib import Path
from resume_parser import extract_text
from matcher import analyze_match
import sqlite3, os, uuid, csv, io, json, re

BASE=Path(__file__).resolve().parent
DB=BASE/"database"/"resumeai.db"; UP=BASE/"uploads"; REPORTS=BASE/"reports"
UP.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True); DB.parent.mkdir(exist_ok=True)
app=Flask(__name__); app.secret_key="resumeai-change-this-secret"
app.config["MAX_CONTENT_LENGTH"]=100*1024*1024
ALLOWED={".pdf",".docx"}

LANGS={
"en":"English","hi":"Hindi","bn":"Bengali","te":"Telugu","mr":"Marathi","ta":"Tamil","gu":"Gujarati",
"kn":"Kannada","ml":"Malayalam","pa":"Punjabi","ur":"Urdu","es":"Spanish","fr":"French","de":"German",
"it":"Italian","pt":"Portuguese","ar":"Arabic","ja":"Japanese","ko":"Korean","zh":"Chinese","ru":"Russian"
}
T={
"en":{"home":"Home","dashboard":"Dashboard","resumes":"My Resumes","history":"History","jobs":"Compare Jobs","builder":"Resume Builder","applications":"Applications","interview":"Interview Prep","admin":"Admin","login":"Login","logout":"Logout","analyze":"Analyze Resume","upload":"Upload Resume","job_title":"Job Title","job_description":"Job Description","download":"Download Report","delete":"Delete","save":"Save","recommend":"Job Recommendations"},
"hi":{"home":"होम","dashboard":"डैशबोर्ड","resumes":"मेरे रिज़्यूमे","history":"इतिहास","jobs":"जॉब तुलना","builder":"रिज़्यूमे बिल्डर","applications":"आवेदन","interview":"इंटरव्यू तैयारी","admin":"एडमिन","login":"लॉगिन","logout":"लॉगआउट","analyze":"रिज़्यूमे विश्लेषण","upload":"रिज़्यूमे अपलोड","job_title":"जॉब टाइटल","job_description":"जॉब विवरण","download":"रिपोर्ट डाउनलोड","delete":"डिलीट","save":"सेव","recommend":"जॉब सुझाव"},
"bn":{"home":"হোম","dashboard":"ড্যাশবোর্ড","resumes":"আমার রিজিউমে","history":"ইতিহাস","jobs":"জব তুলনা","builder":"রিজিউমে বিল্ডার","applications":"আবেদন","interview":"ইন্টারভিউ প্রস্তুতি","admin":"অ্যাডমিন","login":"লগইন","logout":"লগআউট","analyze":"রিজিউমে বিশ্লেষণ","upload":"রিজিউমে আপলোড","job_title":"জব টাইটেল","job_description":"জব বিবরণ","download":"রিপোর্ট ডাউনলোড","delete":"মুছুন","save":"সেভ","recommend":"জব সুপারিশ"}
}
for code in LANGS:
    T.setdefault(code,T["en"])

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=conn()
    c.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS resumes(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,resume_name TEXT NOT NULL,stored_name TEXT NOT NULL,text TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,resume_id INTEGER,resume_name TEXT,job_title TEXT,job_description TEXT,score REAL,ats_score REAL,decision TEXT,decision_reason TEXT,matching_skills TEXT,missing_skills TEXT,keyword_rate REAL,similarity REAL,skill_score REAL,result_json TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,recruiter_name TEXT,title TEXT,company TEXT,description TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,job_title TEXT,company TEXT,status TEXT,notes TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS builder_profiles(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER UNIQUE,full_name TEXT,email TEXT,phone TEXT,location TEXT,linkedin TEXT,github TEXT,summary TEXT,education TEXT,skills TEXT,projects TEXT,experience TEXT,certifications TEXT,achievements TEXT,updated_at TEXT,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    """); c.commit(); c.close()
init()

def user():
    uid=session.get("uid")
    if not uid:return None
    c=conn(); u=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); c.close(); return u
def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if not user(): return redirect(url_for("login",next=request.path))
        return f(*a,**k)
    return w
def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return f(*a,**k)
    return w
def now(): return datetime.now().strftime("%Y-%m-%d %H:%M")
def del_upload(name):
    if name:
        p=UP/os.path.basename(name)
        if p.exists(): p.unlink(missing_ok=True)

@app.context_processor
def globals():
    code=session.get("lang","en")
    return {"user":user(),"admin":session.get("admin",False),"langs":LANGS,"tr":T.get(code,T["en"]),"lang":code}

@app.route("/set-language/<code>")
def set_language(code):
    if code in LANGS: session["lang"]=code
    return redirect(request.referrer or url_for("index"))

@app.route("/")
def index(): return render_template("index.html")

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if not name or not email or len(pw)<6: flash("Enter name, valid email and password (6+ characters)."); return redirect(url_for("register"))
        c=conn()
        try:
            cur=c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",(name,email,generate_password_hash(pw),now())); c.commit()
            session["uid"]=cur.lastrowid
        except sqlite3.IntegrityError:
            c.close(); flash("Email already registered."); return redirect(url_for("login"))
        c.close(); return redirect(url_for("dashboard"))
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); pw=request.form.get("password",""); c=conn()
        u=c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"],pw): session["uid"]=u["id"]; return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid email or password.")
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/analyze",methods=["POST"])
def analyze():
    f=request.files.get("resume"); jd=request.form.get("job_description","").strip(); title=request.form.get("job_title","").strip() or "Untitled Job"
    if not f or not f.filename or not jd: flash("Resume and Job Description are required."); return redirect(url_for("index"))
    ext=Path(f.filename).suffix.lower()
    if ext not in ALLOWED: flash("Only PDF and DOCX files are supported."); return redirect(url_for("index"))
    stored=uuid.uuid4().hex+ext; f.save(UP/stored)
    try: text=extract_text(UP/stored); result=analyze_match(text,jd)
    except Exception as e: del_upload(stored); flash("Analysis failed: "+str(e)); return redirect(url_for("index"))
    uid=user()["id"] if user() else None
    c=conn(); c.execute("INSERT INTO resumes(user_id,resume_name,stored_name,text,created_at) VALUES(?,?,?,?,?)",(uid,secure_filename(f.filename),stored,text,now())); rid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("""INSERT INTO analyses(user_id,resume_id,resume_name,job_title,job_description,score,ats_score,decision,decision_reason,matching_skills,missing_skills,keyword_rate,similarity,skill_score,result_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (uid,rid,secure_filename(f.filename),title,jd,result["score"],result["ats_score"],result["decision"],result["decision_reason"],", ".join(result["matching_skills"]),", ".join(result["missing_skills"]),result["keyword_rate"],result["similarity"],result["skill_score"],json.dumps(result),now()))
    aid=c.execute("SELECT last_insert_rowid()").fetchone()[0]; c.commit(); c.close()
    return redirect(url_for("result",aid=aid))

@app.route("/result/<int:aid>")
def result(aid):
    c=conn(); a=c.execute("SELECT * FROM analyses WHERE id=?",(aid,)).fetchone(); c.close()
    if not a: return "Analysis not found",404
    return render_template("result.html",a=a,result=json.loads(a["result_json"]))

@app.route("/dashboard")
@login_required
def dashboard():
    uid=user()["id"]; c=conn()
    rows=c.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 8",(uid,)).fetchall()
    stats=c.execute("SELECT COUNT(*) n,COALESCE(AVG(score),0) avg,COALESCE(MAX(score),0) best FROM analyses WHERE user_id=?",(uid,)).fetchone()
    resumes=c.execute("SELECT COUNT(*) n FROM resumes WHERE user_id=?",(uid,)).fetchone()["n"]
    c.close(); return render_template("dashboard.html",rows=rows,stats=stats,resume_count=resumes)

@app.route("/resumes")
@login_required
def resumes():
    c=conn(); rows=c.execute("SELECT * FROM resumes WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall(); c.close()
    return render_template("resumes.html",rows=rows)

@app.route("/resume/delete/<int:rid>",methods=["POST"])
@login_required
def resume_delete(rid):
    c=conn(); r=c.execute("SELECT * FROM resumes WHERE id=? AND user_id=?",(rid,user()["id"])).fetchone()
    if r:
        del_upload(r["stored_name"]); c.execute("UPDATE analyses SET resume_id=NULL WHERE resume_id=? AND user_id=?",(rid,user()["id"])); c.execute("DELETE FROM resumes WHERE id=?",(rid,)); c.commit()
    c.close(); flash("Resume deleted."); return redirect(request.referrer or url_for("resumes"))

@app.route("/history")
@login_required
def history():
    c=conn(); rows=c.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall(); c.close()
    return render_template("history.html",rows=rows)

@app.route("/history/delete/<int:aid>",methods=["POST"])
@login_required
def history_delete(aid):
    c=conn(); a=c.execute("SELECT * FROM analyses WHERE id=? AND user_id=?",(aid,user()["id"])).fetchone()
    if a: c.execute("DELETE FROM analyses WHERE id=?",(aid,)); c.commit()
    c.close(); return redirect(url_for("history"))

@app.route("/history/delete-all",methods=["POST"])
@login_required
def history_all():
    c=conn(); c.execute("DELETE FROM analyses WHERE user_id=?",(user()["id"],)); c.commit(); c.close(); return redirect(url_for("history"))

@app.route("/bulk-screen",methods=["GET","POST"])
def bulk_screen():
    if request.method == "GET":
        return render_template("bulk.html")

    title = request.form.get("job_title", "").strip() or "Untitled Job"
    current_user = user()
    jd = request.form.get("job_description", "").strip()
    try:
        threshold = int(request.form.get("threshold", "80"))
    except ValueError:
        threshold = 80
    threshold = max(20, min(95, threshold))
    files = [f for f in request.files.getlist("resumes") if f and f.filename]

    if not jd:
        flash("Job Description is required.")
        return redirect(url_for("bulk_screen"))
    if not files:
        flash("Select at least one PDF or DOCX resume.")
        return redirect(url_for("bulk_screen"))
    if len(files) > 100:
        flash("Maximum 100 resumes can be screened in one batch.")
        return redirect(url_for("bulk_screen"))

    results = []
    skipped = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        name = secure_filename(f.filename) or "resume"
        if ext not in ALLOWED:
            skipped.append(name + " (unsupported format)")
            continue
        # Per-file safety limit while allowing a larger total batch.
        try:
            f.stream.seek(0, os.SEEK_END)
            size = f.stream.tell()
            f.stream.seek(0)
        except Exception:
            size = 0
        if size > 8 * 1024 * 1024:
            skipped.append(name + " (over 8 MB)")
            continue

        stored = uuid.uuid4().hex + ext
        path = UP / stored
        try:
            f.save(path)
            text = extract_text(path)
            r = analyze_match(text, jd)
            decision = "SHORTLIST" if r["score"] >= threshold else "REJECT"
            reason = (f"Match score {r['score']}% meets the {threshold}% threshold."
                      if decision == "SHORTLIST" else
                      f"Match score {r['score']}% is below the {threshold}% threshold.")
            results.append({
                "name": name, "score": r["score"], "ats_score": r["ats_score"],
                "skill_score": r["skill_score"], "keyword_rate": r["keyword_rate"],
                "decision": decision, "reason": reason,
                "matching_skills": r["matching_skills"], "missing_skills": r["missing_skills"]
            })
            if current_user:
                c = conn()
                c.execute(
                    "INSERT INTO resumes(user_id,resume_name,stored_name,text,created_at) VALUES(?,?,?,?,?)",
                    (current_user["id"], name, stored, text, now())
                )
                rid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                c.execute(
                    "INSERT INTO analyses(user_id,resume_id,resume_name,job_title,job_description,score,ats_score,decision,decision_reason,matching_skills,missing_skills,keyword_rate,similarity,skill_score,result_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (current_user["id"], rid, name, title, jd, r["score"], r["ats_score"], decision, reason, ", ".join(r["matching_skills"]), ", ".join(r["missing_skills"]), r["keyword_rate"], r["similarity"], r["skill_score"], json.dumps(r), now())
                )
                c.commit()
                c.close()
        except Exception as e:
            skipped.append(name + " (analysis failed)")
        finally:
            if not current_user:
                del_upload(stored)

    results.sort(key=lambda x: x["score"], reverse=True)
    shortlisted_rows = [x for x in results if x["decision"] == "SHORTLIST"]
    rejected_rows = [x for x in results if x["decision"] == "REJECT"]
    return render_template(
        "bulk_result.html", results=results, shortlisted_rows=shortlisted_rows,
        rejected_rows=rejected_rows, count=len(results), shortlisted=len(shortlisted_rows),
        rejected=len(rejected_rows), skipped=skipped, threshold=threshold,
        job_title=title, top_score=(results[0]["score"] if results else 0)
    )

@app.route("/compare",methods=["GET","POST"])
@login_required
def compare():
    results=[]
    if request.method=="POST":
        f=request.files.get("resume"); raw=request.form.get("jobs","").strip()
        if not f or Path(f.filename).suffix.lower() not in ALLOWED: flash("Upload PDF/DOCX resume."); return redirect(url_for("compare"))
        temp=UP/(uuid.uuid4().hex+Path(f.filename).suffix.lower()); f.save(temp)
        try: text=extract_text(temp)
        finally: temp.unlink(missing_ok=True)
        for block in [x.strip() for x in raw.split("\n\n") if x.strip()][:10]:
            first,*rest=block.split("\n",1); desc=rest[0] if rest else block
            r=analyze_match(text,desc); results.append({"title":first[:80],"score":r["score"],"decision":r["decision"],"missing":r["missing_skills"][:5]})
        results.sort(key=lambda x:x["score"],reverse=True)
    return render_template("compare.html",results=results)

@app.route("/builder",methods=["GET","POST"])
@login_required
def builder():
    c=conn(); p=c.execute("SELECT * FROM builder_profiles WHERE user_id=?",(user()["id"],)).fetchone()
    if request.method=="POST":
        data={k:request.form.get(k,"").strip() for k in ["full_name","email","phone","location","linkedin","github","summary","education","skills","projects","experience","certifications","achievements"]}
        if p:
            c.execute("""UPDATE builder_profiles SET full_name=?,email=?,phone=?,location=?,linkedin=?,github=?,summary=?,education=?,skills=?,projects=?,experience=?,certifications=?,achievements=?,updated_at=? WHERE user_id=?""",
                      (*data.values(),now(),user()["id"]))
        else:
            c.execute("""INSERT INTO builder_profiles(user_id,full_name,email,phone,location,linkedin,github,summary,education,skills,projects,experience,certifications,achievements,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (user()["id"],*data.values(),now()))
        c.commit(); p=c.execute("SELECT * FROM builder_profiles WHERE user_id=?",(user()["id"],)).fetchone(); flash("Resume profile saved.")
    c.close(); return render_template("builder.html",p=p)

@app.route("/builder/download")
@login_required
def builder_download():
    c=conn(); p=c.execute("SELECT * FROM builder_profiles WHERE user_id=?",(user()["id"],)).fetchone(); c.close()
    if not p: flash("Save your resume profile first."); return redirect(url_for("builder"))
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    out=REPORTS/f"resume_{user()['id']}.pdf"; styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=40,bottomMargin=40)
    story=[Paragraph(p["full_name"] or user()["name"],styles["Title"]),Paragraph(" | ".join(x for x in [p["email"],p["phone"],p["location"]] if x),styles["Normal"]),Spacer(1,10)]
    for label,key in [("Summary","summary"),("Education","education"),("Skills","skills"),("Projects","projects"),("Experience","experience"),("Certifications","certifications"),("Achievements","achievements")]:
        if p[key]: story += [Paragraph(label,styles["Heading2"]),Paragraph(p[key].replace("\n","<br/>"),styles["BodyText"]),Spacer(1,8)]
    doc.build(story); return send_file(out,as_attachment=True,download_name="ResumeAI_Builder.pdf")

@app.route("/applications",methods=["GET","POST"])
@login_required
def applications():
    c=conn()
    if request.method=="POST":
        c.execute("INSERT INTO applications(user_id,job_title,company,status,notes,created_at) VALUES(?,?,?,?,?,?)",(user()["id"],request.form.get("job_title"),request.form.get("company"),request.form.get("status"),request.form.get("notes"),now())); c.commit()
    rows=c.execute("SELECT * FROM applications WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall(); c.close()
    return render_template("applications.html",rows=rows)

@app.route("/applications/delete/<int:aid>",methods=["POST"])
@login_required
def application_delete(aid):
    c=conn(); c.execute("DELETE FROM applications WHERE id=? AND user_id=?",(aid,user()["id"])); c.commit(); c.close(); return redirect(url_for("applications"))

@app.route("/interview")
@login_required
def interview():
    c=conn(); a=c.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1",(user()["id"],)).fetchone(); c.close()
    skills=(a["matching_skills"].split(", ") if a and a["matching_skills"] else ["Python","SQL","Communication","Projects"])
    questions=[f"Explain your experience with {s}." for s in skills[:6]]+[ "Tell me about a challenging project and how you solved it.","Why are you a good fit for this role?","Explain one project from your resume."]
    return render_template("interview.html",questions=questions)

@app.route("/recommendations")
@login_required
def recommendations():
    c=conn(); a=c.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1",(user()["id"],)).fetchone()
    jobs=c.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall(); c.close()
    out=[]
    if a:
        from matcher import analyze_match
        for j in jobs:
            r=analyze_match(a["resume_name"]+" "+a["matching_skills"],j["description"])
            out.append((j,r["score"]))
        out.sort(key=lambda x:x[1],reverse=True)
    return render_template("recommendations.html",jobs=out)

@app.route("/reports/<int:aid>")
@login_required
def report(aid):
    c=conn(); a=c.execute("SELECT * FROM analyses WHERE id=? AND user_id=?",(aid,user()["id"])).fetchone(); c.close()
    if not a:return "Not found",404
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    r=json.loads(a["result_json"]); out=REPORTS/f"analysis_{aid}.pdf"; styles=getSampleStyleSheet()
    doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=40,bottomMargin=40)
    story=[Paragraph("ResumeAI Pro â€” Analysis Report",styles["Title"]),Paragraph(f"Job: {a['job_title']}",styles["Heading2"]),Paragraph(f"Match Score: {r['score']}% | ATS: {r['ats_score']}%",styles["BodyText"]),Paragraph(f"Decision: {r['decision']} â€” {r['decision_reason']}",styles["BodyText"]),Spacer(1,12)]
    for label,val in [("Matching Skills",", ".join(r["matching_skills"]) or "None"),("Missing Skills",", ".join(r["missing_skills"]) or "None"),("Keyword Coverage",f"{r['keyword_rate']}%"),("Suggestions","<br/>".join("â€¢ "+x for x in r["suggestions"]))]:
        story += [Paragraph(label,styles["Heading2"]),Paragraph(val,styles["BodyText"]),Spacer(1,8)]
    doc.build(story); return send_file(out,as_attachment=True,download_name=f"ResumeAI_Analysis_{aid}.pdf")

@app.route("/export-csv")
@login_required
def export_csv():
    c=conn(); rows=c.execute("SELECT id,resume_name,job_title,score,ats_score,decision,keyword_rate,created_at FROM analyses WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall(); c.close()
    s=io.StringIO(); w=csv.writer(s); w.writerow(rows[0].keys() if rows else ["id","resume_name","job_title","score","ats_score","decision","keyword_rate","created_at"])
    for r in rows:w.writerow(list(r))
    return send_file(io.BytesIO(s.getvalue().encode()),as_attachment=True,download_name="ResumeAI_History.csv",mimetype="text/csv")

@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST" and request.form.get("username")=="admin" and request.form.get("password")=="admin123":
        session["admin"]=True; return redirect(url_for("admin"))
    flash("Invalid admin credentials."); return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout(): session.pop("admin",None); return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    c=conn(); users=c.execute("SELECT * FROM users ORDER BY id DESC").fetchall(); analyses=c.execute("SELECT * FROM analyses ORDER BY id DESC").fetchall()
    jobs=c.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall(); apps=c.execute("SELECT COUNT(*) n FROM applications").fetchone()["n"]
    stats={"users":len(users),"analyses":len(analyses),"jobs":len(jobs),"applications":apps}
    c.close(); return render_template("admin.html",users=users,analyses=analyses,jobs=jobs,stats=stats)

@app.route("/admin/job",methods=["POST"])
@admin_required
def admin_job():
    c=conn(); c.execute("INSERT INTO jobs(recruiter_name,title,company,description,created_at) VALUES(?,?,?,?,?)",(request.form.get("recruiter_name"),request.form.get("title"),request.form.get("company"),request.form.get("description"),now())); c.commit(); c.close(); return redirect(url_for("admin"))

@app.route("/admin/analysis/delete/<int:aid>",methods=["POST"])
@admin_required
def admin_analysis_delete(aid):
    c=conn(); c.execute("DELETE FROM analyses WHERE id=?",(aid,)); c.commit(); c.close(); return redirect(url_for("admin"))

@app.route("/admin/user/delete/<int:uid>",methods=["POST"])
@admin_required
def admin_user_delete(uid):
    c=conn(); rs=c.execute("SELECT stored_name FROM resumes WHERE user_id=?",(uid,)).fetchall()
    for r in rs: del_upload(r["stored_name"])
    c.execute("DELETE FROM users WHERE id=?",(uid,)); c.commit(); c.close(); return redirect(url_for("admin"))

@app.route("/health")
def health(): return jsonify({"status":"ok","service":"ResumeAI Pro Career Platform"})

if __name__=="__main__": app.run(debug=True)










