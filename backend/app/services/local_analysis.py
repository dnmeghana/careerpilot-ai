import re
from collections import Counter

STOP_WORDS = set("a an and are as at be by for from has have in is it of on or that the their this to with you your our we will into about using work working role team years".split())
SKILL_TERMS = {
    "python", "javascript", "typescript", "react", "vue", "angular", "sql", "postgresql", "mysql", "git", "docker", "kubernetes", "aws", "azure", "gcp", "fastapi", "django", "node.js", "node", "java", "c++", "go", "rust", "terraform", "linux", "figma", "tableau", "excel", "pandas", "numpy", "graphql", "rest", "api", "machine learning", "data analysis", "project management", "communication", "leadership", "ci/cd", "agile", "scrum"}


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"\bci\s*/?\s*cd\b", "ci/cd", text.lower())
    return [token.rstrip(".,:;!?)]}") for token in re.findall(r"[a-z][a-z0-9+#./-]{1,}", normalized) if token not in STOP_WORDS and not token.isdigit()]


def _keywords(text: str) -> list[str]:
    tokens = _tokens(text)
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common()]


def analyze_resume_job(resume_text: str, job_description: str) -> dict:
    resume_tokens = set(_tokens(resume_text))
    job_tokens = set(_tokens(job_description))
    resume_keywords = set(_keywords(resume_text))
    job_keywords = _keywords(job_description)
    matching = sorted({term for term in SKILL_TERMS if term in resume_tokens and term in job_tokens})
    missing = sorted({term for term in SKILL_TERMS if term in job_tokens and term not in resume_tokens})
    matching_keywords = resume_keywords & set(job_keywords)
    match_percentage = round((len(matching_keywords) / len(set(job_keywords))) * 100, 1) if job_keywords else 0
    important_missing = [keyword for keyword in job_keywords if keyword not in resume_keywords][:8]
    experience = [keyword for keyword in job_keywords if keyword in resume_keywords][:8]
    suggestions = [f"Add evidence of {skill} to a project or experience bullet." for skill in missing[:3]]
    if missing:
        suggestions.append("Mirror the job description's terminology where it accurately describes your experience.")
    if not suggestions:
        suggestions.append("Quantify the impact of your most relevant experience with clear outcomes.")
    return {"match_percentage": match_percentage, "matching_skills": matching, "missing_skills": missing, "missing_keywords": important_missing, "relevant_experience_keywords": experience, "recommended_skills": missing[:5], "resume_improvement_suggestions": suggestions}