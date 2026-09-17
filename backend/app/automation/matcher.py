"""Job title normalization, flexible/semantic matching, and runtime job identity verification."""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse


# Standard role acronyms and abbreviations
ACRONYM_MAP: Dict[str, str] = {
    "sde": "software development engineer",
    "swe": "software engineer",
    "dev": "developer",
    "sr": "senior",
    "jr": "junior",
    "mgr": "manager",
    "qa": "quality assurance",
    "sdet": "software development engineer in test",
    "pm": "product manager",
    "tpm": "technical product manager",
    "em": "engineering manager",
    "sre": "site reliability engineer",
    "devops": "development operations",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "fe": "frontend",
    "be": "backend",
    "fs": "full stack",
    "infosec": "information security",
}

# Core role equivalence families (roles inside each set are synonyms for primary discipline)
SYNONYMOUS_ROLE_FAMILIES: List[Set[str]] = [
    {"software developer", "software development engineer", "software engineer", "developer", "programmer", "software programmer"},
    {"frontend developer", "frontend engineer", "front end developer", "front end engineer", "ui engineer", "web developer"},
    {"backend developer", "backend engineer", "back end developer", "back end engineer", "server engineer"},
    {"full stack developer", "full stack engineer", "fullstack developer", "fullstack engineer"},
    {"qa engineer", "quality assurance engineer", "test engineer", "automation engineer", "sdet", "software development engineer in test"},
    {"devops engineer", "site reliability engineer", "sre", "platform engineer", "infrastructure engineer", "cloud engineer"},
    {"data scientist", "machine learning engineer", "ml engineer", "ai engineer"},
    {"data engineer", "big data engineer", "analytics engineer"},
    {"product manager", "technical product manager", "product owner"},
]

# Seniority levels ranked from 1 to 7
SENIORITY_RANKS: Dict[str, int] = {
    "intern": 1,
    "coop": 1,
    "associate": 2,
    "junior": 2,
    "entry": 2,
    "mid": 3,
    "senior": 4,
    "staff": 5,
    "principal": 6,
    "lead": 5,
    "distinguished": 7,
    "fellow": 7,
    "director": 6,
    "vp": 7,
}

# Roman numeral mappings
ROMAN_NUMERAL_RANKS: Dict[str, int] = {
    "i": 2,    # Level 1 / Junior
    "ii": 3,   # Level 2 / Mid
    "iii": 4,  # Level 3 / Senior
    "iv": 5,   # Level 4 / Staff
    "v": 6,    # Level 5 / Principal
}

# Specializations / sub-disciplines
SPECIALIZATIONS: List[str] = [
    "backend", "back end",
    "frontend", "front end",
    "full stack", "fullstack",
    "mobile", "ios", "android",
    "platform", "infrastructure", "cloud",
    "devops", "sre",
    "security", "infosec", "cybersecurity",
    "embedded", "firmware", "iot",
    "data", "analytics", "data warehouse",
    "machine learning", "ml", "ai", "artificial intelligence",
    "distributed systems", "systems",
    "testing", "automation", "qa",
]

# Non-engineering / non-development functional roles to prevent naive substring matches
# E.g. "Software Sales", "Customer Support for Software"
FUNCTIONAL_ROLE_STOPWORDS: Set[str] = {
    "sales", "recruiter", "recruiting", "talent", "accountant", "accounting",
    "legal", "counsel", "attorney", "marketing", "copywriter", "support",
    "customer", "representative", "specialist", "executive", "clerk", "janitor",
    "assistant", "operations", "coordinator", "admin", "administrator",
}


@dataclass
class ParsedTitle:
    original: str
    normalized: str
    core_role: str
    seniority: Optional[str] = None
    seniority_rank: Optional[int] = None
    specializations: List[str] = field(default_factory=list)
    functional_domains: List[str] = field(default_factory=list)
    is_technical_builder: bool = True


class JobTitleNormalizer:
    """Normalizes job titles and extracts structured role semantics."""

    @classmethod
    def clean_text(cls, text: str) -> str:
        if not text:
            return ""
        # Lowercase
        s = text.lower()
        # Replace punctuation like dashes, pipes, slashes, commas with space
        s = re.sub(r"[\-\|\,\/\:\;\(\)\[\]\_\.\&]+", " ", s)
        # Collapse multiple spaces
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @classmethod
    def parse(cls, title: str) -> ParsedTitle:
        clean = cls.clean_text(title)
        tokens = clean.split()

        # Resolve acronyms for individual tokens
        expanded_tokens = [ACRONYM_MAP.get(tok, tok) for tok in tokens]
        expanded_text = " ".join(expanded_tokens)

        seniority: Optional[str] = None
        seniority_rank: Optional[int] = None

        # Check Roman numerals
        for tok in tokens:
            if tok in ROMAN_NUMERAL_RANKS:
                seniority = tok.upper()
                seniority_rank = ROMAN_NUMERAL_RANKS[tok]
                break

        # Check named seniority ranks
        if not seniority:
            for s_name, s_rank in SENIORITY_RANKS.items():
                pattern = rf"\b{re.escape(s_name)}\b"
                if re.search(pattern, expanded_text):
                    seniority = s_name
                    seniority_rank = s_rank
                    break

        # Detect functional domains (e.g. Sales, Support, HR, Marketing)
        functional_domains: List[str] = []
        for stopword in FUNCTIONAL_ROLE_STOPWORDS:
            if re.search(rf"\b{re.escape(stopword)}\b", clean):
                functional_domains.append(stopword)

        # Detect specializations
        specializations: List[str] = []
        for spec in SPECIALIZATIONS:
            if re.search(rf"\b{re.escape(spec)}\b", clean):
                specializations.append(spec)

        # Core role extraction: remove seniority tokens to find core title
        core_tokens = []
        for tok in expanded_tokens:
            if tok in ROMAN_NUMERAL_RANKS or tok in SENIORITY_RANKS:
                continue
            core_tokens.append(tok)
        raw_core_role = " ".join(core_tokens).strip()

        # Map to canonical representative if in a known synonym family
        canonical_core_role = raw_core_role
        for family in SYNONYMOUS_ROLE_FAMILIES:
            if raw_core_role in family:
                canonical_core_role = "software developer" if "software developer" in family else sorted(list(family))[0]
                break

        # Check if title refers to a developer/builder role vs pure sales/support/etc
        is_builder = True
        builder_indicators = {"developer", "engineer", "programmer", "architect", "scientist", "coder"}
        has_builder = any(ind in core_tokens for ind in builder_indicators)
        if functional_domains and not has_builder:
            is_builder = False
        # If it has "sales" + "specialist" or "customer support" even with "software", it's not a developer
        if any(d in ("sales", "support", "recruiter", "marketing") for d in functional_domains) and not has_builder:
            is_builder = False

        return ParsedTitle(
            original=title,
            normalized=expanded_text,
            core_role=canonical_core_role,
            seniority=seniority,
            seniority_rank=seniority_rank,
            specializations=specializations,
            functional_domains=functional_domains,
            is_technical_builder=is_builder,
        )


# Geographic location clusters for fuzzy/regional compatibility
LOCATION_CLUSTERS: Dict[str, Set[str]] = {
    "new york": {"new york", "nyc", "ny", "manhattan", "brooklyn", "queens", "new york city"},
    "san francisco": {"san francisco", "sf", "bay area", "ca", "california", "san jose", "silicon valley", "oakland", "palo alto", "mountain view", "sunnyvale"},
    "seattle": {"seattle", "wa", "washington", "bellevue", "redmond"},
    "boston": {"boston", "ma", "massachusetts", "cambridge"},
    "austin": {"austin", "tx", "texas"},
    "chicago": {"chicago", "il", "illinois"},
    "los angeles": {"los angeles", "la", "ca", "california", "santa monica"},
    "bangalore": {"bangalore", "bengaluru", "blr", "karnataka", "india", "in"},
    "hyderabad": {"hyderabad", "telangana", "india", "in"},
    "pune": {"pune", "maharashtra", "india", "in"},
    "delhi": {"delhi", "noida", "gurugram", "gurgaon", "ncr", "india", "in"},
    "london": {"london", "uk", "united kingdom", "england"},
    "toronto": {"toronto", "on", "ontario", "canada"},
}


def calculate_location_compatibility(
    desired_location: Optional[str], candidate_location: Optional[str]
) -> tuple[float, List[str]]:
    """Evaluates location match considering aliases, regions, and remote options."""
    reasons: List[str] = []
    if not desired_location:
        return 80.0, ["Target location not specified (flexible)."]
    if not candidate_location:
        return 75.0, ["Job location unspecified in posting."]

    d_clean = desired_location.lower().strip()
    c_clean = candidate_location.lower().strip()

    # Remote check
    if any(k in d_clean or k in c_clean for k in ("remote", "anywhere", "work from home", "wfh", "virtual")):
        reasons.append("Remote location compatibility.")
        return 100.0, reasons

    # Direct substring match
    if d_clean in c_clean or c_clean in d_clean:
        reasons.append(f"Location matches directly: '{candidate_location}'.")
        return 100.0, reasons

    # Cluster matching
    d_cluster = None
    for cluster_name, aliases in LOCATION_CLUSTERS.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", d_clean) for alias in aliases):
            d_cluster = cluster_name
            break

    c_cluster = None
    for cluster_name, aliases in LOCATION_CLUSTERS.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", c_clean) for alias in aliases):
            c_cluster = cluster_name
            break

    if d_cluster and c_cluster and d_cluster == c_cluster:
        reasons.append(f"Location matches geographic area ({d_cluster.title()}).")
        return 95.0, reasons

    # Token overlap
    d_tokens = set(re.findall(r"\b[a-z]{2,}\b", d_clean))
    c_tokens = set(re.findall(r"\b[a-z]{2,}\b", c_clean))
    overlap = d_tokens.intersection(c_tokens)
    if overlap:
        reasons.append(f"Partial geographic overlap ({', '.join(overlap)}).")
        return 70.0, reasons

    reasons.append(f"Location divergence: user desires '{desired_location}' but job is in '{candidate_location}'.")
    return 30.0, reasons


def parse_experience_range(exp_text: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Extract minimum and maximum years of experience from arbitrary text."""
    if not exp_text:
        return None, None
    text = exp_text.lower()
    m_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:yrs|years|yr)?", text)
    if m_range:
        return float(m_range.group(1)), float(m_range.group(2))
    m_min = re.search(r"(?:minimum|min|at least|\+)?\s*(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:yrs|years|yr)", text)
    if m_min:
        val = float(m_min.group(1))
        return val, val + 3.0
    m_digit = re.search(r"(\d+(?:\.\d+)?)\s*(?:yrs|years|yr)", text)
    if m_digit:
        val = float(m_digit.group(1))
        return val, val + 2.0
    return None, None


def calculate_experience_compatibility(
    user_years: Optional[int | float],
    job_exp_str: Optional[str] = None,
    candidate_description: Optional[str] = None,
    candidate_seniority_rank: Optional[int] = None,
) -> tuple[float, List[str]]:
    """Score experience compatibility against requirements or seniority tiers."""
    reasons: List[str] = []
    if user_years is None:
        return 80.0, ["User experience years not configured (flexible)."]

    min_exp, max_exp = parse_experience_range(job_exp_str)
    if min_exp is None and candidate_description:
        min_exp, max_exp = parse_experience_range(candidate_description)

    if min_exp is not None and max_exp is not None:
        if min_exp <= user_years <= max_exp:
            reasons.append(f"Experience within required range ({min_exp:.0f}-{max_exp:.0f} yrs for {user_years:.0f} yrs).")
            return 100.0, reasons
        elif user_years < min_exp:
            gap = min_exp - user_years
            if gap <= 1.0:
                reasons.append(f"Slightly below target experience ({user_years:.0f} yrs vs {min_exp:.0f}-{max_exp:.0f} yrs).")
                return 80.0, reasons
            elif gap <= 2.5:
                reasons.append(f"Moderate experience gap ({user_years:.0f} yrs vs {min_exp:.0f}-{max_exp:.0f} yrs).")
                return 55.0, reasons
            else:
                reasons.append(f"Significant experience deficit ({user_years:.0f} yrs vs min {min_exp:.0f} yrs).")
                return 30.0, reasons
        else:
            over = user_years - max_exp
            if over <= 2.0:
                reasons.append(f"Slightly senior for posting ({user_years:.0f} yrs vs max {max_exp:.0f} yrs).")
                return 90.0, reasons
            elif over <= 4.0:
                reasons.append(f"Noticeably overqualified for range ({user_years:.0f} yrs vs max {max_exp:.0f} yrs).")
                return 70.0, reasons
            else:
                reasons.append(f"Substantially overqualified for posting ({user_years:.0f} yrs vs max {max_exp:.0f} yrs).")
                return 50.0, reasons

    if candidate_seniority_rank is not None:
        expected_years = {1: 0, 2: 1, 3: 3, 4: 5, 5: 8, 6: 10, 7: 12}.get(candidate_seniority_rank, 3)
        diff = abs(user_years - expected_years)
        if diff <= 1:
            reasons.append(f"Experience aligns with seniority tier (~{expected_years} yrs).")
            return 100.0, reasons
        elif diff <= 3:
            reasons.append(f"Acceptable seniority variance (~{expected_years} yrs expected).")
            return 80.0, reasons
        else:
            reasons.append(f"Noticeable seniority variance (~{expected_years} yrs expected vs {user_years:.0f} yrs).")
            return 50.0, reasons

    return 80.0, ["Posting does not specify strict experience requirements."]


def check_company_match(
    specific_company: Optional[str], candidate_company: str
) -> tuple[bool, float, List[str]]:
    """Verify company match when user specifies a specific company requirement."""
    reasons: List[str] = []
    if not specific_company or not specific_company.strip():
        return True, 100.0, []

    s_clean = specific_company.lower().strip()
    c_clean = candidate_company.lower().strip()

    if s_clean in c_clean or c_clean in s_clean:
        reasons.append(f"Company matches configured target '{specific_company}'.")
        return True, 100.0, reasons

    reasons.append(f"Company '{candidate_company}' does not match requested company '{specific_company}'.")
    return False, 0.0, reasons


class SkillMatchTuple(tuple):
    """Tuple subclass allowing both 2-element unpacking (score, reasons) and attribute access."""
    def __new__(cls, score: float, reasons: List[str], matched_skills: List[str], missing_skills: List[str]):
        return super().__new__(cls, (score, reasons))

    def __init__(self, score: float, reasons: List[str], matched_skills: List[str], missing_skills: List[str]):
        self.score = score
        self.reasons = reasons
        self.matched_skills = matched_skills
        self.missing_skills = missing_skills


def match_resume_skills(
    user_skills: Optional[List[str]],
    candidate_skills: Optional[List[str]],
    candidate_description: Optional[str] = None,
) -> SkillMatchTuple:
    """Calculate skill overlap percentage, missing skills, and collect reasoning."""
    reasons: List[str] = []
    if not user_skills:
        return SkillMatchTuple(70.0, ["No resume skills provided for skill matching."], [], [])

    cand_skills_set = {s.lower().strip() for s in (candidate_skills or []) if s and s.strip()}
    if candidate_description:
        desc_lower = candidate_description.lower()
        for u_skill in user_skills:
            if re.search(rf"\b{re.escape(u_skill.lower())}\b", desc_lower):
                cand_skills_set.add(u_skill.lower().strip())
        tech_vocab = [
            "python", "javascript", "typescript", "react", "fastapi", "docker", "aws",
            "sql", "postgresql", "node", "node.js", "java", "kubernetes", "git", "c++",
            "golang", "go", "ruby", "rails", "django", "flask", "gcp", "azure", "graphql",
            "redis", "mongodb", "kafka", "ci/cd", "terraform", "linux", "html", "css"
        ]
        for tech in tech_vocab:
            if re.search(rf"\b{re.escape(tech)}\b", desc_lower):
                cand_skills_set.add(tech)

    user_skills_set = {s.lower().strip() for s in user_skills if s and s.strip()}
    matched = user_skills_set.intersection(cand_skills_set)
    missing = cand_skills_set.difference(user_skills_set)

    matched_list = [s.title() for s in sorted(matched)]
    missing_list = [s.title() for s in sorted(missing)]

    if not cand_skills_set:
        return SkillMatchTuple(70.0, ["No specific skills extracted from job posting."], [], [])

    ratio = len(matched) / len(user_skills_set) if user_skills_set else 0.0
    score = round(ratio * 100.0, 1)
    if matched_list:
        reasons.append(f"Skills matched ({len(matched_list)}/{len(user_skills_set)}): {', '.join(matched_list[:6])}.")
    else:
        reasons.append("No overlap between resume skills and job requirements.")

    if missing_list:
        reasons.append(f"Missing skills: {', '.join(missing_list[:4])}.")

    return SkillMatchTuple(score, reasons, matched_list, missing_list)


def normalize_job_url_for_dedup(url: str) -> str:
    """Strip query tracking parameters for deduplication comparison."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
    if not url:
        return ""
    parsed = urlparse(url)
    clean_query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_") and k.lower() not in ("ref", "source", "tracking")]
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", urlencode(clean_query), "")).strip()


def is_duplicate_candidate(
    candidate_url: str,
    candidate_title: str,
    candidate_company: str,
    existing_records: List[Any],
    candidate_requisition_id: Optional[str] = None,
    candidate_location: Optional[str] = None,
    already_applied_records: Optional[List[Any]] = None,
) -> bool:
    """Return True if candidate is already present in database records or already applied."""
    c_norm_url = normalize_job_url_for_dedup(candidate_url)
    c_title = JobTitleNormalizer.clean_text(candidate_title)
    c_company = candidate_company.lower().strip()
    c_req_id = (candidate_requisition_id or extract_requisition_id_from_url_or_text(candidate_url) or "").strip().lower()

    # Check already-applied records first
    all_targets = list(existing_records)
    if already_applied_records:
        all_targets.extend(already_applied_records)

    for rec in all_targets:
        rec_url = getattr(rec, "job_url", getattr(rec, "url", "")) or ""
        rec_title = getattr(rec, "exact_title", getattr(rec, "title", "")) or ""
        rec_company = (getattr(rec, "company", "") or "").lower().strip()
        rec_location = getattr(rec, "location", None)
        rec_req_id = (getattr(rec, "requisition_id", None) or extract_requisition_id_from_url_or_text(rec_url) or "").strip().lower()

        # 1. Requisition ID check: If both have requisition IDs, same requisition ID + same company = duplicate
        if c_req_id and rec_req_id:
            if c_req_id == rec_req_id and (not c_company or not rec_company or c_company == rec_company):
                return True
            # If both have different requisition IDs, they are distinct positions (not duplicates)
            if c_req_id != rec_req_id and c_company == rec_company and c_title == JobTitleNormalizer.clean_text(rec_title):
                continue

        # 2. Canonical URL check
        if c_norm_url and normalize_job_url_for_dedup(rec_url) == c_norm_url:
            return True

        # 3. Company + Title + Location check
        if c_company and c_company == rec_company:
            if JobTitleNormalizer.clean_text(rec_title) == c_title:
                # If locations are provided and completely in different clusters, allow distinct positions
                if candidate_location and rec_location:
                    loc_score, _ = calculate_location_compatibility(candidate_location, rec_location)
                    if loc_score < 50.0:
                        continue
                return True

    return False


@dataclass
class JobMatchResult:
    match_score: float  # 0.0 to 100.0
    is_match: bool
    title_score: float
    skills_score: float
    location_score: float
    experience_score: float
    normalized_target_title: str
    normalized_job_title: str
    reasons: List[str] = field(default_factory=list)
    breakdown: Dict[str, Any] = field(default_factory=dict)
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)


class JobMatchScorer:
    """Calculates multi-factor similarity score between target role preferences and candidate job."""

    def __init__(self, match_threshold: float = 60.0):
        self.match_threshold = match_threshold

    def calculate_title_similarity(self, target_title: str, candidate_title: str) -> Tuple[float, List[str]]:
        target_p = JobTitleNormalizer.parse(target_title)
        cand_p = JobTitleNormalizer.parse(candidate_title)
        reasons: List[str] = []

        # 1. Exact string match
        if target_p.normalized == cand_p.normalized:
            reasons.append("Exact normalized title match.")
            return 100.0, reasons

        # 2. Check for functional domain mismatch (e.g. Developer vs Sales Specialist)
        # If target is a builder (developer/engineer) but candidate is in a non-builder functional domain
        if target_p.is_technical_builder and not cand_p.is_technical_builder:
            reasons.append(f"Role mismatch: Target is an engineering/developer role, but candidate is in '{', '.join(cand_p.functional_domains)}'.")
            return 15.0, reasons

        # If both are builders, check if they belong to the same core role family
        is_synonymous_family = False
        for family in SYNONYMOUS_ROLE_FAMILIES:
            target_in_family = any(re.search(rf"\b{re.escape(f_member)}\b", target_p.normalized) for f_member in family)
            cand_in_family = any(re.search(rf"\b{re.escape(f_member)}\b", cand_p.normalized) for f_member in family)
            if target_in_family and cand_in_family:
                is_synonymous_family = True
                break

        base_score = 0.0
        if target_p.core_role and target_p.core_role == cand_p.core_role:
            base_score = 100.0
            reasons.append(f"Core role matches canonical title ('{target_p.core_role}').")
        elif is_synonymous_family:
            base_score = 90.0
            reasons.append(f"Core role matches known synonym family ('{target_p.core_role}' ~= '{cand_p.core_role}').")
        else:
            # Word token overlap between core roles
            t_words = set(target_p.core_role.split())
            c_words = set(cand_p.core_role.split())
            if t_words and c_words:
                overlap = t_words.intersection(c_words)
                union = t_words.union(c_words)
                jaccard = len(overlap) / len(union) if union else 0.0
                base_score = jaccard * 80.0
                if overlap:
                    reasons.append(f"Core keyword overlap: {', '.join(overlap)}.")
            else:
                base_score = 20.0

        # Specialization assessment
        if target_p.specializations and cand_p.specializations:
            common_specs = set(target_p.specializations).intersection(set(cand_p.specializations))
            if common_specs:
                base_score = min(100.0, base_score + 10.0)
                reasons.append(f"Matching specialization: {', '.join(common_specs)}.")
            else:
                # Conflicting specialization (e.g. Backend vs Frontend)
                base_score = max(20.0, base_score - 30.0)
                reasons.append(f"Divergent specialization: Target has '{target_p.specializations}', candidate has '{cand_p.specializations}'.")
        elif not target_p.specializations and cand_p.specializations:
            # Target is generic (e.g. "Software Developer") and candidate is specialized (e.g. "Software Developer - Backend")
            base_score = min(98.0, base_score + 5.0)
            reasons.append(f"Candidate role adds domain specialization: {', '.join(cand_p.specializations)}.")

        # Seniority level assessment
        if target_p.seniority_rank and cand_p.seniority_rank:
            diff = abs(target_p.seniority_rank - cand_p.seniority_rank)
            if diff == 0:
                base_score = min(100.0, base_score + 5.0)
                reasons.append(f"Matching seniority level: {target_p.seniority}.")
            elif diff == 1:
                # Adjacent level (e.g. Mid vs Senior or Junior vs Mid)
                base_score = max(30.0, base_score - 5.0)
                reasons.append(f"Slight seniority variance: Target '{target_p.seniority}' vs Candidate '{cand_p.seniority}'.")
            else:
                # Large gap (e.g. Junior vs Staff)
                base_score = max(20.0, base_score - 25.0)
                reasons.append(f"Significant seniority variance: Target '{target_p.seniority}' vs Candidate '{cand_p.seniority}'.")
        elif not target_p.seniority_rank and cand_p.seniority_rank:
            # Target is flexible about seniority; allow senior/junior with slight normalization
            base_score = min(95.0, base_score)
            reasons.append(f"Candidate specifies seniority '{cand_p.seniority}' (target was flexible).")

        return round(max(0.0, min(100.0, base_score)), 1), reasons

    def score_job(
        self,
        target_role: str,
        candidate_title: str,
        candidate_description: Optional[str] = None,
        candidate_location: Optional[str] = None,
        candidate_skills: Optional[List[str]] = None,
        user_skills: Optional[List[str]] = None,
        user_location: Optional[str] = None,
        user_experience_years: Optional[int | float] = None,
        employment_type_pref: Optional[str] = None,
        candidate_company: Optional[str] = None,
        specific_company: Optional[str] = None,
        candidate_experience_str: Optional[str] = None,
    ) -> JobMatchResult:
        """Computes comprehensive multi-factor match score with transparent breakdown."""
        target_p = JobTitleNormalizer.parse(target_role)
        cand_p = JobTitleNormalizer.parse(candidate_title)

        # 1. Title Similarity (Weight: 40%)
        title_score, title_reasons = self.calculate_title_similarity(target_role, candidate_title)
        reasons = list(title_reasons)

        # 2. Skills Match (Weight: 25%)
        skills_score, skill_reasons = match_resume_skills(user_skills, candidate_skills, candidate_description)
        reasons.extend(skill_reasons)
        skills_res = match_resume_skills(user_skills, candidate_skills, candidate_description)
        skills_score = skills_res.score
        reasons.extend(skills_res.reasons)

        # 3. Experience Match (Weight: 20%)
        exp_score, exp_reasons = calculate_experience_compatibility(
            user_years=user_experience_years,
            job_exp_str=candidate_experience_str,
            candidate_description=candidate_description,
            candidate_seniority_rank=cand_p.seniority_rank,
        )
        reasons.extend(exp_reasons)

        # 4. Location Match (Weight: 15%)
        loc_score, loc_reasons = calculate_location_compatibility(user_location, candidate_location)
        reasons.extend(loc_reasons)

        # 5. Company Matching (Strict or Soft)
        company_matched = True
        if specific_company and candidate_company:
            comp_ok, comp_score, comp_reasons = check_company_match(specific_company, candidate_company)
            reasons.extend(comp_reasons)
            if not comp_ok:
                company_matched = False

        # Weighted Total Score: Title (40%), Skills (25%), Experience (20%), Location (15%)
        weighted_score = (
            (title_score * 0.40) +
            (skills_score * 0.25) +
            (exp_score * 0.20) +
            (loc_score * 0.15)
        )
        final_score = round(max(0.0, min(100.0, weighted_score)), 1)

        is_match = final_score >= self.match_threshold and title_score >= 40.0
        if not company_matched:
            is_match = False
            final_score = min(final_score, 30.0)

        breakdown = {
            "title_score": title_score,
            "skills_score": skills_score,
            "location_score": loc_score,
            "experience_score": exp_score,
            "weighted_score": final_score,
            "company_matched": company_matched,
        }

        return JobMatchResult(
            match_score=final_score,
            is_match=is_match,
            title_score=title_score,
            skills_score=skills_score,
            location_score=loc_score,
            experience_score=exp_score,
            normalized_target_title=target_p.normalized,
            normalized_job_title=cand_p.normalized,
            reasons=reasons,
            breakdown=breakdown,
            matched_skills=skills_res.matched_skills,
            missing_skills=skills_res.missing_skills,
        )


@dataclass
class SelectedJobIdentity:
    """Immutable identity record for a specific job selected by the user."""
    company: str
    exact_title: str
    job_url: str
    job_id: Optional[str] = None
    requisition_id: Optional[str] = None
    location: Optional[str] = None
    source: str = "portal"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelectedJobIdentity":
        return cls(
            company=str(data.get("company", "")),
            exact_title=str(data.get("exact_title", data.get("title", ""))),
            job_url=str(data.get("job_url", data.get("url", ""))),
            job_id=str(data["job_id"]) if data.get("job_id") else None,
            requisition_id=str(data["requisition_id"]) if data.get("requisition_id") else None,
            location=str(data["location"]) if data.get("location") else None,
            source=str(data.get("source", "portal")),
        )


def extract_requisition_id_from_url_or_text(url: Optional[str], text: Optional[str] = None) -> Optional[str]:
    """Extracts job posting or requisition ID from URLs and web portal content."""
    if url:
        parsed = urlparse(url)
        path = parsed.path

        # 1. Common query parameters for requisition ID (e.g. ?gh_jid=12345, ?jobId=67890, ?reqId=R-123)
        query_params = parse_qs(parsed.query)
        for key in ("gh_jid", "jobId", "job_id", "reqId", "req_id", "requisitionId", "id"):
            if key in query_params and query_params[key]:
                val = query_params[key][0].strip()
                if val and (val.isdigit() or re.match(r"^[A-Za-z0-9\-_]{4,}$", val)):
                    return val

        # 2. Common path patterns:
        # e.g. /jobs/12345, /posting/67890, /job/R-10293, /apply/12345
        path_match = re.search(r"/(?:jobs|job|posting|postings|positions|apply|requisition)/([A-Za-z0-9\-_]{4,})", path, re.I)
        if path_match:
            candidate = path_match.group(1)
            if re.search(r"\d", candidate):  # Must contain at least one digit to be an ID
                return candidate

        # 3. Trailing ID in path (e.g. /careers/software-engineer-12345)
        tail_match = re.search(r"[\-/]([0-9]{4,})(?:/|$)", path)
        if tail_match:
            return tail_match.group(1)

    # 4. On-page text patterns
    if text:
        text_match = re.search(
            r"(?:job\s*id|req(?:uisition)?\s*(?:id|#|number)?)\s*[:#-]?\s*([A-Za-z0-9\-_]{4,})",
            text,
            re.I,
        )
        if text_match:
            candidate = text_match.group(1).strip()
            if re.search(r"\d", candidate):
                return candidate

    return None


@dataclass
class JobVerificationResult:
    is_verified: bool
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    match_reasons: List[str] = field(default_factory=list)
    mismatch_reasons: List[str] = field(default_factory=list)
    extracted_job_id: Optional[str] = None
    extracted_page_title: Optional[str] = None
    extracted_url: Optional[str] = None

    @property
    def reason(self) -> str:
        if not self.is_verified and self.mismatch_reasons:
            return "; ".join(self.mismatch_reasons)
        if self.match_reasons:
            return "; ".join(self.match_reasons)
        return "Page verified" if self.is_verified else "Verification failed"

    @property
    def details(self) -> Dict[str, Any]:
        return {
            "is_verified": self.is_verified,
            "confidence": self.confidence,
            "match_reasons": self.match_reasons,
            "mismatch_reasons": self.mismatch_reasons,
            "extracted_job_id": self.extracted_job_id,
            "extracted_page_title": self.extracted_page_title,
            "extracted_url": self.extracted_url,
        }


def verify_current_page_matches_selected_job(
    selected_job: SelectedJobIdentity,
    current_url: str,
    page_title: str,
    page_content: Optional[str] = None,
) -> JobVerificationResult:
    """Verifies that the current browser page strictly corresponds to the selected job posting.
    
    Tolerates minor portal title formatting variations, but guards against:
    - Mismatched requisition/job IDs
    - Mismatched specializations (e.g. Frontend vs Backend)
    - Different locations when requisition is location-specific
    - Redirects to unrelated career portal index pages
    """
    match_reasons: List[str] = []
    mismatch_reasons: List[str] = []

    # 1. Normalize URLs
    selected_parsed = urlparse(selected_job.job_url)
    current_parsed = urlparse(current_url)

    # Check for empty or about:blank
    if not current_url or current_url.lower().strip() == "about:blank":
        mismatch_reasons.append("Current browser page is about:blank or not loaded.")
        return JobVerificationResult(
            is_verified=False,
            confidence="LOW",
            mismatch_reasons=mismatch_reasons,
            extracted_url=current_url,
            extracted_page_title=page_title,
        )

    # 2. Requisition ID Check
    selected_req_id = selected_job.requisition_id or extract_requisition_id_from_url_or_text(selected_job.job_url)
    page_req_id = extract_requisition_id_from_url_or_text(current_url, page_content)

    if selected_req_id and page_req_id:
        if selected_req_id.lower() == page_req_id.lower():
            match_reasons.append(f"Requisition ID matches perfectly ({page_req_id}).")
        else:
            mismatch_reasons.append(
                f"Job ID mismatch: Expected requisition '{selected_req_id}', but page shows '{page_req_id}'."
            )
            return JobVerificationResult(
                is_verified=False,
                confidence="LOW",
                match_reasons=match_reasons,
                mismatch_reasons=mismatch_reasons,
                extracted_job_id=page_req_id,
                extracted_page_title=page_title,
                extracted_url=current_url,
            )

    # 3. Canonical Domain Check
    if selected_parsed.netloc and current_parsed.netloc:
        if selected_parsed.netloc.lower() == current_parsed.netloc.lower():
            match_reasons.append(f"Domain matches ({selected_parsed.netloc}).")
        else:
            # Check if domain was a third-party ATS redirection (e.g. company.com -> greenhouse.io)
            ats_domains = {"greenhouse.io", "lever.co", "myworkdayjobs.com", "icims.com", "smartrecruiters.com", "taleo.net", "jobvite.com"}
            is_ats_redirect = any(ats in current_parsed.netloc.lower() for ats in ats_domains)
            if not is_ats_redirect:
                mismatch_reasons.append(f"Domain mismatch: Expected '{selected_parsed.netloc}', but found '{current_parsed.netloc}'.")

    # 4. Title & Specialization Check
    # Parse selected job title and on-page title
    sel_p = JobTitleNormalizer.parse(selected_job.exact_title)
    page_p = JobTitleNormalizer.parse(page_title)

    # Check for specialization divergence (e.g. Backend vs Frontend)
    if sel_p.specializations and page_p.specializations:
        common_specs = set(sel_p.specializations).intersection(set(page_p.specializations))
        if not common_specs:
            mismatch_reasons.append(
                f"Specialization mismatch: Selected job is '{sel_p.specializations}', but page shows '{page_p.specializations}'."
            )
            return JobVerificationResult(
                is_verified=False,
                confidence="LOW",
                match_reasons=match_reasons,
                mismatch_reasons=mismatch_reasons,
                extracted_job_id=page_req_id,
                extracted_page_title=page_title,
                extracted_url=current_url,
            )

    # Core role similarity between selected job and page title
    scorer = JobMatchScorer()
    title_score, _ = scorer.calculate_title_similarity(selected_job.exact_title, page_title)

    # Allow page title to contain portal branding or slight wording differences
    # E.g. "Software Developer - Backend" vs "Software Developer - Backend | Stripe Careers"
    if title_score >= 50.0 or (sel_p.core_role and sel_p.core_role in page_p.normalized):
        match_reasons.append(f"Page title corresponds to selected role (Title match: {title_score}%).")
    else:
        # If the requisition ID matches, we can be slightly more lenient on title differences
        if selected_req_id and page_req_id and selected_req_id.lower() == page_req_id.lower():
            match_reasons.append("Title differs slightly, but requisition ID is confirmed.")
        else:
            mismatch_reasons.append(
                f"Page title mismatch: Expected '{selected_job.exact_title}', but found '{page_title}'."
            )

    # 5. Location Check (if specified and visible in content/title)
    if selected_job.location:
        sel_loc_lower = selected_job.location.lower().strip()
        combined_text = f"{page_title} {page_content or ''}".lower()

        known_cities = [
            "new york", "san francisco", "london", "austin", "seattle",
            "toronto", "paris", "berlin", "boston", "chicago",
            "los angeles", "dublin", "singapore", "bangalore", "sydney"
        ]

        selected_city = next((c for c in known_cities if c in sel_loc_lower), None)
        if selected_city and "remote" not in sel_loc_lower:
            for other_city in known_cities:
                if other_city != selected_city:
                    title_has_other = other_city in page_title.lower()
                    content_has_explicit_other = (
                        f"location: {other_city}" in combined_text or
                        f"location - {other_city}" in combined_text or
                        f"office: {other_city}" in combined_text or
                        f"office - {other_city}" in combined_text or
                        f"based in {other_city}" in combined_text
                    )
                    if (title_has_other or content_has_explicit_other) and selected_city not in combined_text and "remote" not in combined_text:
                        mismatch_reasons.append(
                            f"Location mismatch: Selected job is in '{selected_job.location}', but page specifies '{other_city.title()}'."
                        )
                        break

    # Final Verification Evaluation
    if mismatch_reasons:
        return JobVerificationResult(
            is_verified=False,
            confidence="LOW",
            match_reasons=match_reasons,
            mismatch_reasons=mismatch_reasons,
            extracted_job_id=page_req_id,
            extracted_page_title=page_title,
            extracted_url=current_url,
        )

    confidence = "HIGH" if (selected_req_id and page_req_id) or title_score >= 80.0 else "MEDIUM"
    return JobVerificationResult(
        is_verified=True,
        confidence=confidence,
        match_reasons=match_reasons,
        mismatch_reasons=mismatch_reasons,
        extracted_job_id=page_req_id,
        extracted_page_title=page_title,
        extracted_url=current_url,
    )
