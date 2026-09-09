from app.services.local_analysis import analyze_resume_job


def test_local_analysis_returns_deterministic_keyword_comparison() -> None:
    result = analyze_resume_job(
        "Built Python and React services with SQL and Git. Improved checkout reliability.",
        "Senior engineer building Python and React services with SQL, Docker, AWS, and CI/CD. Own checkout reliability.",
    )

    assert result["matching_skills"] == ["python", "react", "sql"]
    assert result["missing_skills"] == ["aws", "ci/cd", "docker"]
    assert "docker" in result["missing_keywords"]
    assert result["match_percentage"] > 0
    assert result["resume_improvement_suggestions"]