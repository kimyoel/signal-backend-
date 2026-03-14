# ─────────────────────────────────────────
# prompts.py — AI 프롬프트 모음 v2.1
# 에이전트 A가 사용하는 모든 AI 프롬프트를 한 곳에서 관리
#
# 변경 이력:
# v1.0 - 초기 버전 (숫자만 반환, 기준 모호)
# v2.0 - JSON 출력 강제, few-shot 예시 추가, 콘텐츠 타입별 채점 기준 분리
# v2.1 - TRANSLATE_SUMMARIZE_PROMPT 개선: 메타 서술 금지, 실제 내용 요약 강제
# ─────────────────────────────────────────

# ═══════════════════════════════════════════════════════════
# 중요도 채점 기준 설계 원칙
# ═══════════════════════════════════════════════════════════
#
# 【5점 - 즉각 시장 영향】
#   → 지금 당장 시장이 움직이거나 이미 움직인 사건
#   예) 미 FOMC 금리 결정, BTC 20%+ 급등락, 전쟁 선포,
#       대형 거래소 해킹/파산, 국가 차원 암호화폐 전면 금지/승인
#
# 【4점 - 주목할 뉴스】
#   → 1~2주 내 시장에 영향을 줄 가능성이 높은 사건
#   예) Fed 의장/부의장 발언, BTC 8~20% 변동, 대형 규제 발표,
#       ETF 승인/거절, 기관 대량 매수/매도 공개, 상장 폐지
#
# 【3점 - 주목할 만한 뉴스】
#   → 투자자가 알아야 할 일반 뉴스
#   예) 경제지표 발표(CPI/PPI/NFP), 기업 실적, 소규모 규제 변화,
#       알트코인 프로젝트 업데이트, 분석가 의견
#
# 【2점 - 낮은 관련성】
#   → 간접적 영향만 있는 일반 경제/금융 뉴스
#   예) 일반 주식 뉴스, 관련성 낮은 기업 M&A, 해외 지역 뉴스
#
# 【1점 - 무관하거나 노이즈】
#   → 투자와 무관하거나 광고성 콘텐츠
#   예) 연예/스포츠, 일반 과학기술 뉴스, 홍보성 글
#
# ═══════════════════════════════════════════════════════════

# ──────────────────────────────────────────
# 1-A. 일반 뉴스 중요도 채점 (Gemini Flash-Lite)
# 입력: RSS/NewsAPI에서 수집한 뉴스
# 출력: JSON {\"score\": 1~5, \"reason\": \"한 줄 이유\"}
# ──────────────────────────────────────────
NEWS_SCORING_PROMPT = """You are a financial news importance scorer for crypto and macro investors.

Score the following news from 1 to 5 based on its market impact potential.

SCORING CRITERIA:
- 5: IMMEDIATE market impact (Fed rate decision, BTC 20%+ move, exchange hack, war declaration, country-level ban/approval)
- 4: HIGH impact within 1-2 weeks (Fed official speech, BTC 8-20% move, major regulation, ETF ruling, institutional bulk trade)
- 3: NOTABLE news investors should know (CPI/PPI/NFP data, earnings, minor regulation, project updates, analyst opinions)
- 2: LOW relevance (indirect economic news, unrelated M&A, regional news)
- 1: NOISE or IRRELEVANT (entertainment, general tech, promotional content)

EXAMPLES:
---
Title: "Federal Reserve raises interest rates by 50 basis points"
Content: "The Federal Open Market Committee voted unanimously to increase the federal funds rate..."
Output: {{"score": 5, "reason": "Fed rate hike directly impacts risk assets and crypto market"}}
---
Title: "BlackRock files for Bitcoin spot ETF amendment"
Content: "Asset management giant BlackRock has updated its Bitcoin ETF filing..."
Output: {{"score": 4, "reason": "ETF filing update signals institutional momentum, market-moving"}}
---
Title: "US CPI data comes in at 3.2%, slightly above expectations"
Content: "The Bureau of Labor Statistics reported consumer prices rose 3.2%..."
Output: {{"score": 3, "reason": "Inflation data affects Fed policy outlook, relevant but not immediate"}}
---
Title: "Tech company announces new software update"
Content: "A major software firm released version 5.0 of its productivity suite..."
Output: {{"score": 1, "reason": "Unrelated to crypto or macro markets"}}
---

NOW SCORE THIS NEWS:
Title: {title}
Content preview: {content_preview}

Respond ONLY with valid JSON in this exact format:
{{"score": <integer 1-5>, "reason": "<one sentence in Korean explaining why>"}}\
"""


# ──────────────────────────────────────────
# 1-B. 애널리스트/인플루언서 Substack 채점 (Gemini Flash-Lite)
# 입력: Substack RSS에서 수집한 애널리스트 글
# 출력: JSON {\"score\": 1~5, \"reason\": \"한 줄 이유\"}
# 특이점: 일반 뉴스보다 threshold 낮게 (3점도 가치있음)
# ──────────────────────────────────────────
ANALYST_SCORING_PROMPT = """You are scoring a financial analyst or influencer article for crypto/macro investors.

These are curated posts from trusted analysts (Arthur Hayes, Lyn Alden, Raoul Pal, Willy Woo, etc.)
Score based on insight depth and market relevance — NOT just news impact.

SCORING CRITERIA FOR ANALYST CONTENT:
- 5: Major market thesis or prediction with strong supporting argument (e.g., "Bitcoin supercycle thesis", "Dollar collapse framework")
- 4: Important market analysis with actionable insights (e.g., liquidity analysis, on-chain data interpretation, macro setup)
- 3: Useful educational or contextual analysis (e.g., historical comparison, sector overview, framework explanation)
- 2: General opinion or lightly supported commentary
- 1: Promotional, irrelevant, or low-quality content

EXAMPLES:
---
Title: "Why Bitcoin Hits $1M Before 2030" by Arthur Hayes
Content: "The global debt supercycle combined with monetary debasement creates the perfect environment..."
Output: {{"score": 5, "reason": "주요 BTC 가격 전망 + 매크로 근거, 시장에 즉각적 영향 가능"}}
---
Title: "March Liquidity Update: M2 Expanding Globally" by Lyn Alden
Content: "Global M2 money supply is expanding at the fastest rate since 2021..."
Output: {{"score": 4, "reason": "글로벌 유동성 분석, 위험자산 방향성에 직접 연관"}}
---
Title: "Understanding the Halving Cycle" by Rekt Capital
Content: "In this article, I explain how Bitcoin's 4-year halving cycle historically affects price..."
Output: {{"score": 3, "reason": "교육적 내용, 사이클 이해에 유용하나 즉각적 시장 영향 없음"}}
---

NOW SCORE THIS ANALYST CONTENT:
Author/Source: {source}
Title: {title}
Content preview: {content_preview}

Respond ONLY with valid JSON in this exact format:
{{"score": <integer 1-5>, "reason": "<one sentence in Korean explaining why>"}}\
"""


# ──────────────────────────────────────────
# 1-C. 트위터/X 인플루언서 트윗 채점 (Gemini Flash-Lite)
# 입력: twitterapi.io에서 수집한 트윗
# 출력: JSON {\"score\": 1~5, \"reason\": \"한 줄 이유\"}
# 특이점: 짧은 텍스트, 맥락 파악 중요, 밈/슬랭 고려
# ──────────────────────────────────────────
TWITTER_SCORING_PROMPT = """You are scoring a tweet from a crypto/macro influencer for investment relevance.

These tweets are from pre-curated expert accounts: Saylor, PlanB, Willy Woo, Lyn Alden, Kobeissi Letter, etc.
These are NOT random tweets — they are from handpicked experts whose every market-related tweet has signal value.
Short content is normal for tweets — score based on the signal value.

SCORING CRITERIA FOR TWEETS:
- 5: Breaking news announcement, major position disclosure, urgent market warning (e.g., "Just bought 10,000 BTC", "Fed emergency meeting called")
- 4: Strong market signal or important data point (e.g., whale movement data, key technical level breach, new institutional development)
- 3: Any market-related commentary, analysis, or opinion from these experts (macro observation, price levels, economic data, sentiment, predictions)
- 2: Pure retweet without added comment, OR vague content with zero market signal
- 1: Clearly off-topic: meme, personal life, promotional/ad content with zero investment relevance

IMPORTANT — DEFAULT TO 3, NOT 2:
- These accounts are pre-screened experts. When in doubt, score 3 (not 2).
- If the tweet mentions ANY of: price levels, economic data, on-chain metrics, market trend, Fed/macro, crypto/stocks → minimum score 3
- RT (retweet) WITHOUT any added comment = 1~2 points ONLY
- RT WITH author's own comment or analysis = treat as original, score 3~4
- Data/chart tweet = 3~4 points  
- Personal opinion or market view from credible source = 3~4 points
- Breaking news or position disclosure = 4~5 points
- ONLY score 1~2 for: pure memes, personal life posts, promotional content, off-topic content

ABSOLUTE MINIMUM RULE:
Any tweet that contains economic data, market commentary, asset prices, investment thesis, 
policy analysis, or any discussion of financial markets = MINIMUM SCORE 3, no exceptions.
Score 1 ONLY IF: joke/meme with zero financial content, completely personal (birthday, travel, food), 
or pure advertisement with no market signal whatsoever.
Score 2 ONLY IF: very vague reference to markets without any specific signal or insight.
DEFAULT: When you are unsure between 2 and 3 — always choose 3.

EXAMPLES:
---
Author: @saylor, Tweet: "MicroStrategy acquires 5,000 BTC for $420M. Total holdings: 150,000 BTC"
Output: {{"score": 5, "reason": "기관 대량 매수 공시, 즉각적 시장 영향 높음"}}
---
Author: @100trillionUSD, Tweet: "S2F model update: On-track for $100K target by Q4. Current deviation: -12%"
Output: {{"score": 4, "reason": "PlanB의 S2F 모델 업데이트, BTC 가격 방향성 시그널"}}
---
Author: @woonomic, Tweet: "On-chain: Exchange outflows hit 6-month high. HODLers accumulating."
Output: {{"score": 4, "reason": "온체인 데이터 기반 축적 신호, 중기 상승 가능성"}}
---
Author: @APompliano, Tweet: "RT @CoinDesk: Bitcoin ETF sees record inflows"
Output: {{"score": 2, "reason": "단순 리트윗, 추가 인사이트 없음"}}
---
Author: @saylor, Tweet: "Orange is the new black 🟠"
Output: {{"score": 1, "reason": "밈성 트윗, 투자 정보 없음"}}
---

NOW SCORE THIS TWEET:
Author: @{username}
Tweet: {tweet_text}

Respond ONLY with valid JSON in this exact format:
{{"score": <integer 1-5>, "reason": "<one sentence in Korean explaining why>"}}\
"""


# ──────────────────────────────────────────
# 2. 번역 + 요약 프롬프트 (Gemini Flash) — v2.1 개선
# - 영문 뉴스 → 한국어 번역 + 1~2문장 요약
# - 이미 한국어인 뉴스는 요약만 수행
#
# ⚠️ 핵심 수정 (v2.1):
#   이전 버전에서 AI가 "이 기사는 ~에 관한 내용입니다" 같은
#   메타 서술(무슨 글인지 설명)을 생성하는 문제 수정.
#   → 실제 사건/수치/사실을 직접 서술하도록 강제.
# ──────────────────────────────────────────
TRANSLATE_SUMMARIZE_PROMPT = """다음 뉴스/콘텐츠를 한국어로 번역하고 핵심 내용을 1~2문장으로 요약하라.

규칙:
- 이미 한국어라면 요약만 수행
- 번역은 자연스러운 한국 투자자 언어로 (직역 금지)
- 요약은 실제 일어난 일, 발표된 수치, 구체적 사실을 직접 서술할 것
- 과장 표현, 투자 권유 표현 금지

⛔ 절대 금지 — 메타 서술 패턴 (글이 무엇인지 설명하는 방식):
  "이 기사는 ~에 관한 내용입니다"
  "이 뉴스는 ~를 다루고 있습니다"
  "~에 대한 분석 글입니다"
  "~을 설명하는 기사입니다"

✅ 올바른 요약 패턴 (실제 내용을 직접 서술):
  나쁜 예: "이 기사는 연준의 금리 인상에 관한 내용입니다."
  좋은 예: "연준이 기준금리를 0.5%p 인상해 5.25~5.5%로 올렸다. 추가 인상 가능성도 시사했다."

  나쁜 예: "이 트윗은 BTC 매수에 관한 Saylor의 트윗입니다."
  좋은 예: "Saylor가 MicroStrategy 명의로 BTC 5,000개($4.2억)를 추가 매수했다고 공개했다."

출력 형식 (반드시 JSON):
{{
  "title_ko": "한국어 제목 (명확하고 간결하게, 핵심 사실 포함)",
  "summary_ko": "1~2문장 요약 — 실제 수치·사실·결과를 직접 서술"
}}

원문 제목: {title}
원문 내용: {content}

JSON만 반환. 다른 텍스트 금지."""


# ──────────────────────────────────────────
# 3. GPT — 매크로 경제 시각 분석
# - 금리, 달러, 위험자산, 유동성 관점
# - 절대 투자 추천/매수/매도 표현 금지
# ──────────────────────────────────────────
GPT_MACRO_PROMPT = """다음 뉴스를 매크로 경제 관점에서 분석하라.

규칙:
- 100~150자 이내로 작성
- 금리, 달러, 위험자산, 유동성 관점 중심
- 투자 추천, 종목 언급, "매수/매도" 표현 절대 금지
- "관측", "패턴", "환경 변화", "데이터 변화" 표현 사용
- 사실 기반, 과장 없이

뉴스: {news_title}
내용: {news_summary}"""


# ──────────────────────────────────────────
# 4. Gemini — 데이터/온체인 패턴 분석
# - 수치, 데이터 패턴, 지표 변화 중심
# ──────────────────────────────────────────
GEMINI_DATA_PROMPT = """다음 뉴스와 관련된 온체인 데이터 또는 정량적 시장 데이터 관점에서 분석하라.

규칙:
- 100~150자 이내
- 수치, 데이터 패턴, 지표 변화 중심
- 투자 권유 표현 절대 금지
- "데이터 패턴", "지표 변화", "관측" 표현 사용

뉴스: {news_title}
내용: {news_summary}"""


# ──────────────────────────────────────────
# 5. Grok (xAI) — 소셜 센티먼트 분석
# - X(트위터) 커뮤니티 반응, 언급량 변화
# ──────────────────────────────────────────
GROK_SOCIAL_PROMPT = """다음 뉴스에 대한 X(트위터) 투자자 커뮤니티의 반응과 소셜 센티먼트를 분석하라.

규칙:
- 100~150자 이내
- 소셜 반응, 커뮤니티 정서, 언급량 변화 중심
- 투자 조언 금지
- X 실시간 데이터 참조 활용

뉴스: {news_title}
내용: {news_summary}"""


# ──────────────────────────────────────────
# 6. Claude — 환각 검증
# - 3개 AI 분석 결과를 검토해서 문제 있으면 FAIL 반환
# - 투자 권유 표현, 사실 오류, 과장 표현 체크
# ──────────────────────────────────────────
CLAUDE_VERIFY_PROMPT = """다음 3개의 AI 분석을 검토하라.

확인 사항:
1. 투자 권유 표현이 있는가? (매수 추천, 수익 보장, 목표가 제시 등)
2. 명백한 사실 오류가 있는가?
3. 과장되거나 공포/탐욕을 자극하는 표현이 있는가?

문제가 없으면 "PASS"만 반환.
문제가 있으면 "FAIL: [구체적 문제]" 형식으로 반환.

GPT 분석: {gpt_analysis}
Gemini 분석: {gemini_analysis}
Grok 분석: {grok_analysis}"""


# ──────────────────────────────────────────
# 7. 콘텐츠 타입별 중요도 임계값
# 이 값 이상인 항목만 DB 저장 → Threads 발행
# ──────────────────────────────────────────
CONTENT_THRESHOLDS = {
    "news": 4,        # 일반 뉴스: 높은 기준 (노이즈 많음)
    "analyst": 3,     # 애널리스트 Substack: 중간 기준 (인사이트 가치)
    "twitter": 3,     # 트위터: 중간 기준 (짧지만 시그널 가치)
    "influencer": 3,  # 인플루언서 (twitter와 동일)
}

# ──────────────────────────────────────────
# 하위 호환성: 기존 코드에서 SCORING_PROMPT 사용 시
# NEWS_SCORING_PROMPT로 리다이렉트
# ──────────────────────────────────────────
SCORING_PROMPT = NEWS_SCORING_PROMPT
