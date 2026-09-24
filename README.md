# ResumeAI Pro — Complete Career Platform

A Flask-based portfolio project combining resume parsing, TF-IDF/cosine matching, ATS-style heuristics, skill-gap analysis, resume builder, job comparison, recommendations, interview practice, application tracking, user accounts and an admin portal.

## Live Demo
https://resumeai-1-1ltq.onrender.com

## Run
```powershell
python -m pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5001

## Admin demo
Username: `admin`
Password: `admin123`

## Main modules
- Resume/JD analyzer
- Match, ATS, skill and keyword scores
- Reject / Review / Shortlist decision
- PDF analysis report + CSV export
- Resume file manager and deletion
- History deletion
- 20+ UI language selector
- User signup/login
- Resume Builder + PDF export
- Job comparison
- Admin job creation
- Job recommendations
- Application tracker
- Interview preparation
- Admin user/analysis management

## Important
The matching engine is a transparent demo implementation using TF-IDF/cosine similarity and deterministic skill/keyword heuristics. It is not a proprietary LLM or a production hiring system. For real deployment, add HTTPS, CSRF protection, secure secrets, rate limiting, production WSGI hosting, cloud storage, consent/privacy controls and human review.

## NEW: Bulk Resume Screening
- Open **Bulk Screen** from the navigation.
- Paste one Job Description and select multiple PDF/DOCX resumes in one upload.
- Screen up to 100 resumes per batch (8 MB per resume; 100 MB total request limit).
- Choose an automatic shortlist threshold from **80% to 90%**.
- Every resume is scored with the existing Match Score, ATS Score, Skill Score and Keyword Coverage logic.
- Results are ranked highest-to-lowest.
- Resumes meeting the threshold are labeled **SHORTLIST**; the rest are labeled **REJECT** for screening purposes.
- A recruiter should still review candidates before making a real employment decision.

