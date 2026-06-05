from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from pydantic import BaseModel as PydanticBaseModel, Field
from typing import List
import os
import logging
import re
from dotenv import load_dotenv

load_dotenv()  

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "\n\n❌  GEMINI_API_KEY not set!\n"
        "    Run:  export GEMINI_API_KEY=your_key_here\n"
        "    Then restart the server.\n"
    )

app = FastAPI(title="SubjectGenAI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SPAM_WORDS = [
    "cash", "free", "winner", "guarantee", "urgent", "100%", "prize",
    "risk-free", "buy direct", "click here", "act now", "limited time",
    "no cost", "earn money", "make money", "double your", "extra income",
    "work from home", "weight loss", "miracle", "once in a lifetime",
]


class GenerateRequest(BaseModel):
    prompt: str
    tone: str = "Professional"
    audience: str = "General"
    industry: str = "General"


class SubjectLineResult(PydanticBaseModel):
    subject: str = Field(description="The email subject line")


class SubjectLinesOutput(PydanticBaseModel):
    subject_lines: List[str] = Field(description="List of exactly 5 email subject lines")


class AnalyzedSubjectLine(BaseModel):
    subject: str
    score: int
    is_spam: bool
    spam_words_found: List[str]
    char_count: int
    mobile_status: str      
    mobile_message: str


class GenerateResponse(BaseModel):
    results: List[AnalyzedSubjectLine]


def analyze(subject: str) -> AnalyzedSubjectLine:
    lower = subject.lower()
    found_spam = [w for w in SPAM_WORDS if w in lower]
    is_spam = len(found_spam) > 0
    char_count = len(subject)

    if char_count > 60:
        mobile_status = "too_long"
        mobile_message = f"Cut off on mobile (>{char_count} chars)"
    elif char_count < 15:
        mobile_status = "too_short"
        mobile_message = "Too short for impact"
    else:
        mobile_status = "ok"
        mobile_message = "Mobile-friendly ✓"

    score = 100
    score -= len(found_spam) * 25
    if char_count > 60:
        score -= 15
    if char_count < 15:
        score -= 10
    if 40 <= char_count <= 60:
        score += 10
    score = max(0, min(100, score))

    return AnalyzedSubjectLine(
        subject=subject,
        score=score,
        is_spam=is_spam,
        spam_words_found=found_spam,
        char_count=char_count,
        mobile_status=mobile_status,
        mobile_message=mobile_message,
    )

def validate_subject_lines(lines: List[str]) -> List[str]:
    """
    Ensures:
    - Exactly 5 lines
    - Each line 15–60 characters
    - No numbering or bullets
    """

    cleaned = []

    for line in lines:
        line = line.strip()

        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        line = re.sub(r"^[-•]\s*", "", line)

        if 15 <= len(line) <= 60:
            cleaned.append(line)

    if len(cleaned) != 5:
        raise ValueError("Model did not return exactly 5 valid subject lines.")

    return cleaned


PROMPT_TEMPLATE = """You are an expert email marketing copywriter. Your ONLY job is to generate exactly 5 email subject lines.

Task Details:
- Email Topic: {prompt}
- Tone: {tone}
- Target Audience: {audience}
- Industry: {industry}

Rules you MUST follow:
1. Generate EXACTLY 5 subject lines — no more, no less.
2. Each subject line must be between 15 and 60 characters long (mobile-friendly).
3. DO NOT use spam trigger words like: free, cash, winner, guarantee, urgent, prize, risk-free, click here, act now, 100%, buy direct.
4. DO NOT include numbering, bullet points, dashes, or any explanation — just the 5 subject lines, one per line.
5. Each subject line must be unique and creative.
6. Match the tone ({tone}) and speak to the audience ({audience}) in an {industry} context.
7. Output NOTHING except the 5 subject lines separated by newlines.

Generate the 5 subject lines now:"""

prompt_template = PromptTemplate(
    input_variables=["prompt", "tone", "audience", "industry"],
    template=PROMPT_TEMPLATE,
)


@app.post("/generate", response_model=GenerateResponse)
async def generate_subject_lines(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    logger.info(f"New generation request | Prompt: {req.prompt}")
    try:
        llm = ChatGoogleGenerativeAI(
            model="models/gemini-flash-latest",
            google_api_key=GEMINI_API_KEY,
            temperature=0.85,
        )

        chain = prompt_template | llm

        for attempt in range(2):
            response = chain.invoke({
                "prompt": req.prompt,
                "tone": req.tone,
                "audience": req.audience,
                "industry": req.industry,
            })

            raw_text = response.content if hasattr(response, "content") else str(response)

            lines = [
                line.strip()
                for line in raw_text.strip().splitlines()
                if line.strip()
            ]

            try:
                subject_lines = validate_subject_lines(lines)
                break
            except ValueError as ve:
                logger.warning(f"Validation failed (attempt {attempt+1}): {ve}")
                if attempt == 1:
                    raise HTTPException(status_code=500, detail=str(ve))


        subject_lines = lines[:5]

        if len(subject_lines) < 1:
            raise HTTPException(status_code=500, detail="Model returned no subject lines.")


        results = [analyze(s) for s in subject_lines]
        logger.info("Successfully generated 5 subject lines.")
        return GenerateResponse(results=results)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/")
def root():
    return {"status": "SubjectGenAI backend is running"}