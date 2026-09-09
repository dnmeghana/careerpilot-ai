import re


def generate_questions(title: str, description: str | None, interview_type: str, resume_text: str | None = None) -> list[dict[str, str]]:
    description_text = description or "the responsibilities described in the posting"
    keywords = re.findall(r"\b[A-Za-z][A-Za-z+#.-]{2,}\b", description_text)
    resume_keywords = re.findall(r"\b[A-Za-z][A-Za-z+#.-]{2,}\b", resume_text or "")
    focus_keywords = list(dict.fromkeys(keyword.lower() for keyword in (keywords[:3] + resume_keywords[:2])))
    focus = ", ".join(focus_keywords) or "the role's core responsibilities"
    prompts = {
        "HR": [
            ("Behavioral", "Why are you interested in the {title} role and this company?", "Medium", "Connect your motivation to the company, the role, and a specific strength you bring."),
            ("Behavioral", "What kind of environment helps you do your best work?", "Easy", "Describe how you communicate, prioritize, and collaborate with concrete examples."),
            ("Role Specific", "What are you hoping to learn or contribute in your next role?", "Medium", "Tie your growth goals to the role's responsibilities and near-term impact."),
        ],
        "Behavioral": [
            ("Behavioral", "Tell me about a time you took ownership of a difficult outcome.", "Medium", "Use STAR: context, your specific actions, the result, and what you learned."),
            ("Behavioral", "Describe a time you disagreed with a teammate and how you handled it.", "Medium", "Show empathy, clear communication, the trade-off you made, and the outcome."),
            ("Problem Solving", "Tell me about a time you had to prioritize competing demands.", "Medium", "Explain your decision criteria, communication, execution, and measurable result."),
        ],
        "Technical": [
            ("Technical", "Which skills from this posting would you apply most often as a {title}?", "Medium", "Choose two or three relevant skills, explain your depth, and give evidence from past work."),
            ("Problem Solving", "How would you investigate a problem involving {focus}?", "Hard", "Clarify the goal, form hypotheses, inspect evidence, test safely, and communicate findings."),
            ("Technical", "Tell me about a technical trade-off you made and why.", "Hard", "Frame the constraints, options considered, decision, risks, and how you validated it."),
        ],
        "System Design": [
            ("Role Specific", "How would you begin designing a system for the core needs of a {title} role?", "Medium", "Clarify users, scale, latency, reliability, data, and success criteria before choosing components."),
            ("Technical", "Design a service that supports workflows related to {focus}.", "Hard", "Describe the API, data model, major components, scaling strategy, and failure handling."),
            ("Problem Solving", "How would you make that system observable and resilient as usage grows?", "Hard", "Cover bottlenecks, caching or queues, monitoring, alerting, graceful degradation, and recovery."),
        ],
    }
    return [
        {"category": category, "question": question.format(title=title, focus=focus), "difficulty": difficulty, "suggested_answer": answer}
        for category, question, difficulty, answer in prompts[interview_type]
    ]