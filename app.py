import os
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
"bn":{"home":"হোম","dashboard":"ড্যাশবোর্ড","resumes":"আমার রিজিউমে","history":"ইতিহাস","jobs":"জব তুলনা","builder":"রিজিউমে বিল্ডার","applications":"আবেদন","interview":"ইন্টারভিউ প্রস্তুতি","admin":"অ্যাডমিন","login":"লগইন","logout":"লগআউট","analyze":"রিজিউমে বিশ্লেষণ","upload":"রিজিউমে আপলোড","job_title":"জব টাইটেল","job_description":"জব বিবরণ","download":"রিপোর্ট ডাউনলোড","delete":"মুছুন","save":"সেভ","recommend":"জব সুপারিশ"},
"te":{"home":"హోమ్","dashboard":"డాష్‌బోర్డ్","resumes":"నా రెజ్యూమేలు","history":"చరిత్ర","jobs":"ఉద్యోగాల పోలిక","builder":"రెజ్యూమే బిల్డర్","applications":"దరఖాస్తులు","interview":"ఇంటర్వ్యూ సిద్ధత","admin":"అడ్మిన్","login":"లాగిన్","logout":"లాగౌట్","analyze":"రెజ్యూమే విశ్లేషణ","upload":"రెజ్యూమే అప్‌లోడ్","job_title":"ఉద్యోగ శీర్షిక","job_description":"ఉద్యోగ వివరణ","download":"నివేదిక డౌన్‌లోడ్","delete":"తొలగించు","save":"సేవ్","recommend":"ఉద్యోగ సూచనలు"},
"mr":{"home":"मुख्यपृष्ठ","dashboard":"डॅशबोर्ड","resumes":"माझे रिझ्युमे","history":"इतिहास","jobs":"नोकरी तुलना","builder":"रिझ्युमे बिल्डर","applications":"अर्ज","interview":"मुलाखत तयारी","admin":"अॅडमिन","login":"लॉगिन","logout":"लॉगआउट","analyze":"रिझ्युमे विश्लेषण","upload":"रिझ्युमे अपलोड","job_title":"नोकरीचे शीर्षक","job_description":"नोकरीचे वर्णन","download":"अहवाल डाउनलोड","delete":"हटवा","save":"जतन करा","recommend":"नोकरीच्या शिफारसी"},
"ta":{"home":"முகப்பு","dashboard":"டாஷ்போர்டு","resumes":"என் ரெஸ்யூமேக்கள்","history":"வரலாறு","jobs":"வேலை ஒப்பீடு","builder":"ரெஸ்யூமே உருவாக்கி","applications":"விண்ணப்பங்கள்","interview":"நேர்காணல் தயாரிப்பு","admin":"நிர்வாகம்","login":"உள்நுழைவு","logout":"வெளியேறு","analyze":"ரெஸ்யூமே பகுப்பாய்வு","upload":"ரெஸ்யூமே பதிவேற்றம்","job_title":"வேலை தலைப்பு","job_description":"வேலை விளக்கம்","download":"அறிக்கையை பதிவிறக்கு","delete":"நீக்கு","save":"சேமி","recommend":"வேலை பரிந்துரைகள்"},
"gu":{"home":"હોમ","dashboard":"ડેશબોર્ડ","resumes":"મારા રિઝ્યુમે","history":"ઇતિહાસ","jobs":"નોકરી સરખામણી","builder":"રિઝ્યુમે બિલ્ડર","applications":"અરજીઓ","interview":"ઇન્ટરવ્યુ તૈયારી","admin":"એડમિન","login":"લૉગિન","logout":"લૉગઆઉટ","analyze":"રિઝ્યુમે વિશ્લેષણ","upload":"રિઝ્યુમે અપલોડ","job_title":"નોકરીનું શીર્ષક","job_description":"નોકરીનું વર્ણન","download":"રિપોર્ટ ડાઉનલોડ","delete":"કાઢી નાખો","save":"સાચવો","recommend":"નોકરીની ભલામણો"},
"kn":{"home":"ಮುಖಪುಟ","dashboard":"ಡ್ಯಾಶ್‌ಬೋರ್ಡ್","resumes":"ನನ್ನ ರೆಸ್ಯೂಮೆಗಳು","history":"ಇತಿಹಾಸ","jobs":"ಉದ್ಯೋಗ ಹೋಲಿಕೆ","builder":"ರೆಸ್ಯೂಮೆ ಬಿಲ್ಡರ್","applications":"ಅರ್ಜಿಗಳು","interview":"ಸಂದರ್ಶನ ತಯಾರಿ","admin":"ನಿರ್ವಾಹಕ","login":"ಲಾಗಿನ್","logout":"ಲಾಗ್‌ಔಟ್","analyze":"ರೆಸ್ಯೂಮೆ ವಿಶ್ಲೇಷಣೆ","upload":"ರೆಸ್ಯೂಮೆ ಅಪ್‌ಲೋಡ್","job_title":"ಉದ್ಯೋಗ ಶೀರ್ಷಿಕೆ","job_description":"ಉದ್ಯೋಗ ವಿವರಣೆ","download":"ವರದಿ ಡೌನ್‌ಲೋಡ್","delete":"ಅಳಿಸಿ","save":"ಉಳಿಸಿ","recommend":"ಉದ್ಯೋಗ ಶಿಫಾರಸುಗಳು"},
"ml":{"home":"ഹോം","dashboard":"ഡാഷ്ബോർഡ്","resumes":"എന്റെ റെസ്യൂമുകൾ","history":"ചരിത്രം","jobs":"ജോലി താരതമ്യം","builder":"റെസ്യൂമെ ബിൽഡർ","applications":"അപേക്ഷകൾ","interview":"ഇന്റർവ്യൂ തയ്യാറെടുപ്പ്","admin":"അഡ്മിൻ","login":"ലോഗിൻ","logout":"ലോഗൗട്ട്","analyze":"റെസ്യൂമെ വിശകലനം","upload":"റെസ്യൂമെ അപ്‌ലോഡ്","job_title":"ജോലി ശീർഷകം","job_description":"ജോലി വിവരണം","download":"റിപ്പോർട്ട് ഡൗൺലോഡ്","delete":"ഇല്ലാതാക്കുക","save":"സംരക്ഷിക്കുക","recommend":"ജോലി ശുപാർശകൾ"},
"pa":{"home":"ਹੋਮ","dashboard":"ਡੈਸ਼ਬੋਰਡ","resumes":"ਮੇਰੇ ਰਿਜ਼ਿਊਮੇ","history":"ਇਤਿਹਾਸ","jobs":"ਨੌਕਰੀ ਤੁਲਨਾ","builder":"ਰਿਜ਼ਿਊਮੇ ਬਿਲਡਰ","applications":"ਅਰਜ਼ੀਆਂ","interview":"ਇੰਟਰਵਿਊ ਤਿਆਰੀ","admin":"ਐਡਮਿਨ","login":"ਲੌਗਇਨ","logout":"ਲੌਗਆਉਟ","analyze":"ਰਿਜ਼ਿਊਮੇ ਵਿਸ਼ਲੇਸ਼ਣ","upload":"ਰਿਜ਼ਿਊਮੇ ਅੱਪਲੋਡ","job_title":"ਨੌਕਰੀ ਦਾ ਸਿਰਲੇਖ","job_description":"ਨੌਕਰੀ ਦਾ ਵੇਰਵਾ","download":"ਰਿਪੋਰਟ ਡਾਊਨਲੋਡ","delete":"ਮਿਟਾਓ","save":"ਸੇਵ","recommend":"ਨੌਕਰੀ ਦੀਆਂ ਸਿਫ਼ਾਰਸ਼ਾਂ"},
"ur":{"home":"ہوم","dashboard":"ڈیش بورڈ","resumes":"میرے ریزیومے","history":"تاریخ","jobs":"ملازمت کا موازنہ","builder":"ریزیومے بلڈر","applications":"درخواستیں","interview":"انٹرویو کی تیاری","admin":"ایڈمن","login":"لاگ ان","logout":"لاگ آؤٹ","analyze":"ریزیومے کا تجزیہ","upload":"ریزیومے اپ لوڈ","job_title":"ملازمت کا عنوان","job_description":"ملازمت کی تفصیل","download":"رپورٹ ڈاؤن لوڈ","delete":"حذف کریں","save":"محفوظ کریں","recommend":"ملازمت کی سفارشات"},
"es":{"home":"Inicio","dashboard":"Panel","resumes":"Mis currículums","history":"Historial","jobs":"Comparar empleos","builder":"Creador de currículum","applications":"Solicitudes","interview":"Preparación de entrevista","admin":"Administrador","login":"Iniciar sesión","logout":"Cerrar sesión","analyze":"Analizar currículum","upload":"Subir currículum","job_title":"Título del empleo","job_description":"Descripción del empleo","download":"Descargar informe","delete":"Eliminar","save":"Guardar","recommend":"Recomendaciones de empleo"},
"fr":{"home":"Accueil","dashboard":"Tableau de bord","resumes":"Mes CV","history":"Historique","jobs":"Comparer les emplois","builder":"Créateur de CV","applications":"Candidatures","interview":"Préparation à l'entretien","admin":"Administrateur","login":"Connexion","logout":"Déconnexion","analyze":"Analyser le CV","upload":"Télécharger le CV","job_title":"Intitulé du poste","job_description":"Description du poste","download":"Télécharger le rapport","delete":"Supprimer","save":"Enregistrer","recommend":"Recommandations d'emploi"},
"de":{"home":"Startseite","dashboard":"Dashboard","resumes":"Meine Lebensläufe","history":"Verlauf","jobs":"Jobs vergleichen","builder":"Lebenslauf-Builder","applications":"Bewerbungen","interview":"Interviewvorbereitung","admin":"Admin","login":"Anmelden","logout":"Abmelden","analyze":"Lebenslauf analysieren","upload":"Lebenslauf hochladen","job_title":"Jobtitel","job_description":"Jobbeschreibung","download":"Bericht herunterladen","delete":"Löschen","save":"Speichern","recommend":"Jobempfehlungen"},
"it":{"home":"Home","dashboard":"Dashboard","resumes":"I miei curriculum","history":"Cronologia","jobs":"Confronta lavori","builder":"Creatore di curriculum","applications":"Candidature","interview":"Preparazione al colloquio","admin":"Amministratore","login":"Accedi","logout":"Esci","analyze":"Analizza curriculum","upload":"Carica curriculum","job_title":"Titolo del lavoro","job_description":"Descrizione del lavoro","download":"Scarica rapporto","delete":"Elimina","save":"Salva","recommend":"Raccomandazioni di lavoro"},
"pt":{"home":"Início","dashboard":"Painel","resumes":"Meus currículos","history":"Histórico","jobs":"Comparar vagas","builder":"Criador de currículo","applications":"Candidaturas","interview":"Preparação para entrevista","admin":"Administrador","login":"Entrar","logout":"Sair","analyze":"Analisar currículo","upload":"Enviar currículo","job_title":"Título da vaga","job_description":"Descrição da vaga","download":"Baixar relatório","delete":"Excluir","save":"Salvar","recommend":"Recomendações de vagas"},
"ar":{"home":"الرئيسية","dashboard":"لوحة التحكم","resumes":"سيرتي الذاتية","history":"السجل","jobs":"مقارنة الوظائف","builder":"منشئ السيرة الذاتية","applications":"الطلبات","interview":"التحضير للمقابلة","admin":"المشرف","login":"تسجيل الدخول","logout":"تسجيل الخروج","analyze":"تحليل السيرة الذاتية","upload":"رفع السيرة الذاتية","job_title":"المسمى الوظيفي","job_description":"وصف الوظيفة","download":"تنزيل التقرير","delete":"حذف","save":"حفظ","recommend":"توصيات الوظائف"},
"ja":{"home":"ホーム","dashboard":"ダッシュボード","resumes":"マイ履歴書","history":"履歴","jobs":"求人比較","builder":"履歴書ビルダー","applications":"応募","interview":"面接準備","admin":"管理者","login":"ログイン","logout":"ログアウト","analyze":"履歴書を分析","upload":"履歴書をアップロード","job_title":"職種名","job_description":"求人内容","download":"レポートをダウンロード","delete":"削除","save":"保存","recommend":"求人のおすすめ"},
"ko":{"home":"홈","dashboard":"대시보드","resumes":"내 이력서","history":"기록","jobs":"채용 공고 비교","builder":"이력서 작성기","applications":"지원서","interview":"면접 준비","admin":"관리자","login":"로그인","logout":"로그아웃","analyze":"이력서 분석","upload":"이력서 업로드","job_title":"직무명","job_description":"채용 공고 설명","download":"보고서 다운로드","delete":"삭제","save":"저장","recommend":"채용 추천"},
"zh":{"home":"首页","dashboard":"仪表板","resumes":"我的简历","history":"历史记录","jobs":"职位比较","builder":"简历制作器","applications":"申请","interview":"面试准备","admin":"管理员","login":"登录","logout":"退出登录","analyze":"分析简历","upload":"上传简历","job_title":"职位名称","job_description":"职位描述","download":"下载报告","delete":"删除","save":"保存","recommend":"职位推荐"},
"ru":{"home":"Главная","dashboard":"Панель управления","resumes":"Мои резюме","history":"История","jobs":"Сравнить вакансии","builder":"Конструктор резюме","applications":"Заявки","interview":"Подготовка к собеседованию","admin":"Администратор","login":"Войти","logout":"Выйти","analyze":"Анализ резюме","upload":"Загрузить резюме","job_title":"Название вакансии","job_description":"Описание вакансии","download":"Скачать отчет","delete":"Удалить","save":"Сохранить","recommend":"Рекомендации по вакансиям"}
}
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

if __name__=="__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)))











