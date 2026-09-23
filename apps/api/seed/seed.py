"""
apps/api/seed/seed.py

Authoritative database seed script for the AI Marketing Intelligence OS:
1. Organization & Admin User
2. 5 Multi-Product Portfolio with deep ProductBrains (including problems_NOT_solved)
3. Cross-Product Relationships
4. 15 Monitored Source Platforms with capabilities
5. 46 Worker Types & Initial active Worker fleet distributed across 3D zones
"""

import asyncio
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import engine, Base, AsyncSessionLocal
from core.config import settings
from core.security import hash_password, encrypt_credential
from models import (
    Organization, User, Role,
    Product, ProductBrain, ProductFeature, ProductProblem, ProductRelationship,
    WorkerType, Worker,
    Source, SourceConnection, SourceHealth
)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

async def seed_database():
    print("=" * 60)
    print("AI Marketing Intelligence OS — Seeding Database")
    print("=" * 60)

    # 1. Create all tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] All database tables verified / created.")

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        org = await session.get(Organization, settings.DEFAULT_ORG_ID)
        if org:
            print("[INFO] Default organization already exists. Skipping duplicate seeding.")
            return

        # ----------------------------------------------------------------------
        # 1. Organization & Admin User
        # ----------------------------------------------------------------------
        print("\n[1/5] Seeding Organization & Security Roles...")
        org = Organization(
            id=settings.DEFAULT_ORG_ID,
            name=settings.DEFAULT_ORG_NAME,
            slug="acme-growth",
            plan="enterprise",
            settings={
                "features": ["3d_command_center", "portfolio_routing", "autonomous_drafting"],
                "max_active_workers": 100,
                "monthly_budget_usd": 5000.0
            }
        )
        session.add(org)

        admin_role = Role(
            organization_id=org.id,
            name="Admin",
            permissions=["*"]
        )
        session.add(admin_role)

        admin_user = User(
            organization_id=org.id,
            email="admin@acmegrowth.com",
            name="Chief Intelligence Officer",
            password_hash=hash_password("AdminSecurePassword2026!"),
            role_name="owner"
        )
        session.add(admin_user)
        await session.flush()
        print(f"  [OK] Organization created: {org.name} ({org.id})")

        # ----------------------------------------------------------------------
        # 2. Seed 5 Products with rich ProductBrains
        # ----------------------------------------------------------------------
        print("\n[2/5] Seeding 5 Portfolio Products & ProductBrains...")
        
        products_data = [
            {
                "id": "10000000-0000-0000-0000-000000000001",
                "name": "ROASSensor",
                "slug": "roas-sensor",
                "category": "Ad Analytics & Attribution",
                "description": "Real-time multi-touch ad attribution and server-side tracking solving Meta/Stripe ROAS discrepancies.",
                "website": "https://roassensor.io",
                "brain": {
                    "icp": "D2C brands, E-commerce stores, and Performance Marketing Agencies spending $10k-$500k/mo on Meta and Google Ads.",
                    "personas": ["Head of Growth", "Performance Marketing Manager", "E-commerce Founder", "Media Buyer"],
                    "industries": ["E-commerce", "Direct-to-Consumer (D2C)", "Retail", "Subscription Boxes"],
                    "problems_solved": [
                        "Meta Ads Manager reporting different revenue than Stripe/Shopify",
                        "iOS 14.5+ privacy signal loss causing ad optimization failure",
                        "Inability to attribute blended CAC across TikTok, Meta, and Google Ads",
                        "Over-reporting and double-counting conversions between ad platforms"
                    ],
                    "problems_not_solved": [
                        "Organic social media scheduling or content creation",
                        "Customer refund disputes or chargeback management",
                        "Email support automation or ticketing",
                        "Website SEO keyword ranking audits"
                    ],
                    "product_boundaries": "ROASSensor ONLY deals with paid ad tracking, conversion APIs, and attribution. It does NOT generate ad creatives or manage payment gateways.",
                    "keywords": ["ROAS mismatch", "Meta attribution", "server-side tracking", "Shopify vs Facebook ads", "ad spend waste", "blended ROAS"],
                    "semantic_concepts": ["multi-touch attribution", "conversion API (CAPI)", "first-party pixel", "data discrepancy", "paid acquisition"],
                    "customer_language": ["Facebook reports 3x ROAS but bank account says 1.2x", "Stripe numbers don't match Meta", "scaling ads feels like gambling"],
                    "negative_keywords": ["seo backlink", "refund dispute", "customer ticket", "chargeback won", "organic search ranking"],
                    "competitors": ["Triple Whale", "Northbeam", "Hyros"],
                    "alternatives": ["Google Analytics 4 (GA4)", "Shopify default analytics"],
                    "objections": ["We already look at GA4", "Attribution tools are too expensive", "Setup is too complex"],
                    "proof_points": [
                        "Server-side CAPI integration verified by Meta Business Partners",
                        "Average client recovers 23% in wasted ad spend within 14 days",
                        "Sub-second sync with Shopify and Stripe webhooks"
                    ],
                    "pricing": {"starter": "$199/mo", "growth": "$499/mo", "enterprise": "$1,299/mo"},
                    "integrations": ["Meta Ads", "Google Ads", "TikTok Ads", "Shopify", "Stripe", "Klaviyo"],
                    "approved_claims": [
                        "Reconciles 100% of real Stripe orders with exact ad clicks",
                        "Bypasses client-side ad blockers using first-party domain cookies"
                    ],
                    "forbidden_claims": [
                        "Guarantees a 10x ROAS increase overnight",
                        "Fixes bad ad copy or unappealing products"
                    ]
                }
            },
            {
                "id": "10000000-0000-0000-0000-000000000002",
                "name": "RevenueSensor",
                "slug": "revenue-sensor",
                "category": "Revenue & Churn Intelligence",
                "description": "Subscription revenue analytics, churn prediction, and Cohort LTV forecasting for B2B SaaS.",
                "website": "https://revenuesensor.io",
                "brain": {
                    "icp": "B2B SaaS and subscription apps with $50k-$10M ARR seeking cohort retention insights and churn prevention.",
                    "personas": ["Chief Financial Officer (CFO)", "VP Finance", "SaaS Founder", "VP of Customer Success"],
                    "industries": ["B2B SaaS", "Mobile App Subscriptions", "Membership Platforms"],
                    "problems_solved": [
                        "Inaccurate Net Revenue Retention (NRR) and MRR movement visibility",
                        "High involuntary churn from failed credit card renewals",
                        "Lack of predictive signals before a high-value account churns",
                        "Complex manual cohort analysis spreadsheets"
                    ],
                    "problems_not_solved": [
                        "Ad attribution or media buying",
                        "Search engine optimization (SEO)",
                        "Support chat response drafting"
                    ],
                    "product_boundaries": "RevenueSensor focuses purely on subscription metrics, revenue recognition, and churn indicators.",
                    "keywords": ["SaaS churn rate", "NRR calculation", "MRR expansion", "predictive churn", "failed payment recovery"],
                    "semantic_concepts": ["customer lifetime value", "net revenue retention", "involuntary churn", "dunning"],
                    "customer_language": ["We lose 5% MRR every month to expired cards", "Cohort analysis takes days in Excel"],
                    "negative_keywords": ["ROAS mismatch", "ad creative", "SEO audit", "backlink exchange"],
                    "competitors": ["ProfitWell", "ChartMogul", "Baremetrics"],
                    "alternatives": ["Stripe Billing Dashboard", "Custom SQL queries"],
                    "objections": ["Stripe already has charts", "We calculate this in our warehouse"],
                    "proof_points": ["Recovers 42% of failed payments automatically", "Accurate GAAP-compliant revenue recognition"],
                    "pricing": {"starter": "$149/mo", "growth": "$399/mo", "scale": "$899/mo"},
                    "integrations": ["Stripe", "Paddle", "Recurly", "QuickBooks", "HubSpot"],
                    "approved_claims": ["Real-time MRR and churn tracking with zero setup delays"],
                    "forbidden_claims": ["Eliminates voluntary churn completely"]
                }
            },
            {
                "id": "10000000-0000-0000-0000-000000000003",
                "name": "RefundSensor",
                "slug": "refund-sensor",
                "category": "Dispute & Chargeback Defense",
                "description": "Autonomous chargeback defense, friendly-fraud mitigation, and refund root-cause analyzer.",
                "website": "https://refundsensor.io",
                "brain": {
                    "icp": "High-volume merchants, digital goods sellers, and e-commerce brands hit by friendly fraud and dispute fees.",
                    "personas": ["Head of Operations", "Risk & Fraud Officer", "E-commerce Founder"],
                    "industries": ["Digital Goods", "Gaming", "E-commerce", "Travel & Events"],
                    "problems_solved": [
                        "Friendly fraud chargebacks eating 2-5% of gross merchant volume",
                        "Visa/Mastercard excessive dispute ratio penalty warnings",
                        "Tedious manual evidence submission for bank disputes",
                        "No visibility into which products or customer segments generate refunds"
                    ],
                    "problems_not_solved": [
                        "Paid advertising or ROAS",
                        "Organic search traffic generation",
                        "General customer helpdesk inquiries"
                    ],
                    "product_boundaries": "RefundSensor exclusively handles dispute resolution, refund policy enforcement, and chargeback prevention.",
                    "keywords": ["chargeback alert", "friendly fraud", "win Stripe dispute", "Visa dispute monitoring", "refund rate"],
                    "semantic_concepts": ["representment", "compelling evidence", "Ethoca alerts", "Verifi CDRN"],
                    "customer_language": ["Customer claimed unauthorized transaction after downloading", "Stripe dispute fees are killing us"],
                    "negative_keywords": ["ROAS", "ad spend", "organic traffic", "Google keyword ranking"],
                    "competitors": ["Chargeflow", "Signifyd", "Midigator"],
                    "alternatives": ["Manual Stripe dispute portal", "Standard merchant evidence docs"],
                    "objections": ["Disputes are too rare for us", "Banks always side with customers"],
                    "proof_points": ["78% win rate on digital goods disputes with automated representment"],
                    "pricing": {"performance": "25% of recovered funds only", "enterprise": "$499/mo + 15%"},
                    "integrations": ["Stripe", "Shopify", "PayPal", "Braintree", "Adyen"],
                    "approved_claims": ["Zero upfront cost with pure success-fee pricing option"],
                    "forbidden_claims": ["100% dispute win rate guarantee"]
                }
            },
            {
                "id": "10000000-0000-0000-0000-000000000004",
                "name": "SupportAI",
                "slug": "support-ai",
                "category": "Autonomous Customer Support",
                "description": "Self-learning AI customer support agent resolving 70%+ of Tier-1 queries across chat, email, and social DMs.",
                "website": "https://supportai.io",
                "brain": {
                    "icp": "High-growth software, e-commerce, and marketplace businesses inundated with repetitive customer tickets.",
                    "personas": ["VP Customer Experience", "Head of Support", "COO", "Founder"],
                    "industries": ["SaaS", "E-commerce", "Fintech", "Marketplaces"],
                    "problems_solved": [
                        "Support ticket backlogs causing slow first-response times",
                        "High cost of 24/7 human support shifts",
                        "Inconsistent agent answers to common policy questions",
                        "Repetitive 'where is my order' and 'how do I reset password' requests"
                    ],
                    "problems_not_solved": [
                        "Ad attribution and media buying",
                        "Accounting and revenue recognition",
                        "SEO keyword planning"
                    ],
                    "product_boundaries": "SupportAI handles conversational support and ticket triage. It does not replace core CRM or billing systems.",
                    "keywords": ["customer support backlog", "AI support bot", "automate Zendesk", "first response time", "deflection rate"],
                    "semantic_concepts": ["ticket deflection", "omnichannel inbox", "RAG knowledge base", "sentiment analysis"],
                    "customer_language": ["We get 500 tickets a day asking the exact same question", "Customers angry about waiting 12 hours"],
                    "negative_keywords": ["ROAS discrepancy", "MRR cohort", "chargeback ratio", "backlink audit"],
                    "competitors": ["Intercom Fin", "Zendesk AI", "Gorgias"],
                    "alternatives": ["Hiring BPO agency in Philippines", "Rule-based chatbot"],
                    "objections": ["AI chatbots hallucinate and make customers angry", "Setup takes too long"],
                    "proof_points": ["Average deflection of 71% without human escalation", "Strict grounding in verified docs only"],
                    "pricing": {"starter": "$0.80 per resolved ticket", "enterprise": "$1,499/mo unlimited"},
                    "integrations": ["Zendesk", "Intercom", "Freshdesk", "Shopify", "Slack", "Email"],
                    "approved_claims": ["Only answers from approved company knowledge base — zero hallucinations"],
                    "forbidden_claims": ["Can replace 100% of human staff without oversight"]
                }
            },
            {
                "id": "10000000-0000-0000-0000-000000000005",
                "name": "SEOPro",
                "slug": "seo-pro",
                "category": "Programmatic SEO & Content Intelligence",
                "description": "Autonomous search opportunity finder, competitor content gap detector, and programmatic SEO builder.",
                "website": "https://seopro.io",
                "brain": {
                    "icp": "Content-driven SaaS, marketplaces, and e-commerce companies seeking compounding organic traffic.",
                    "personas": ["Head of SEO", "Content Marketing Lead", "CMO", "Founder"],
                    "industries": ["Tech & SaaS", "Directories & Marketplaces", "E-commerce"],
                    "problems_solved": [
                        "Competitors ranking for hundreds of lucrative high-intent comparison terms",
                        "High agency retainer fees with slow keyword delivery",
                        "Unclear keyword difficulty vs business intent trade-off",
                        "Outdated content suffering gradual decay in Google SERPs"
                    ],
                    "problems_not_solved": [
                        "Paid Facebook or Meta ad tracking",
                        "Chargeback disputes",
                        "Customer support ticket answering"
                    ],
                    "product_boundaries": "SEOPro is focused exclusively on organic search traffic, keyword topology, content gap analysis, and programmatic pages.",
                    "keywords": ["content gap analysis", "programmatic SEO", "competitor keywords", "SERP decay", "search intent"],
                    "semantic_concepts": ["topical authority", "search engine results pages", "keyword clustering", "schema markup"],
                    "customer_language": ["Our organic traffic dropped after recent algorithm update", "Competitors dominate every 'vs' keyword"],
                    "negative_keywords": ["Meta ROAS", "chargeback representment", "MRR churn", "support deflection"],
                    "competitors": ["Ahrefs", "Semrush", "SurferSEO"],
                    "alternatives": ["Manual Google search console spreadsheets", "Freelance SEO consultants"],
                    "objections": ["SEO takes 6 months to see results", "AI content gets penalized"],
                    "proof_points": ["Generates verifiable topical clusters with human-reviewed factual citations"],
                    "pricing": {"pro": "$249/mo", "scale": "$599/mo", "enterprise": "$1,499/mo"},
                    "integrations": ["Google Search Console", "WordPress", "Webflow", "Next.js", "Ghost"],
                    "approved_claims": ["Uncovers hidden low-competition, high-intent keywords that generic tools miss"],
                    "forbidden_claims": ["Guarantees #1 Google rank for any keyword in 24 hours"]
                }
            }
        ]

        for p_info in products_data:
            brain_info = p_info.pop("brain")
            prod = Product(
                id=p_info["id"],
                organization_id=org.id,
                name=p_info["name"],
                slug=p_info["slug"],
                category=p_info["category"],
                description=p_info["description"],
                website=p_info["website"],
                status="active"
            )
            session.add(prod)
            await session.flush()

            brain = ProductBrain(
                product_id=prod.id,
                **brain_info
            )
            session.add(brain)
            print(f"  [OK] Product created: {prod.name} with complete ProductBrain")

        # ----------------------------------------------------------------------
        # 3. Product Cross-Sell Relationships
        # ----------------------------------------------------------------------
        print("\n[3/5] Seeding Cross-Product Relationships...")
        relationships_data = [
            ("10000000-0000-0000-0000-000000000001", "10000000-0000-0000-0000-000000000002", "CROSS_SELL", 0.92, "E-commerce tracking high ad spend also needs accurate recurring revenue LTV metrics."),
            ("10000000-0000-0000-0000-000000000001", "10000000-0000-0000-0000-000000000003", "CROSS_SELL", 0.88, "High-volume ad scaling frequently leads to friendly fraud disputes on sudden order spikes."),
            ("10000000-0000-0000-0000-000000000002", "10000000-0000-0000-0000-000000000003", "BUNDLE", 0.85, "Subscription businesses have both failed payments and dispute chargebacks affecting MRR."),
            ("10000000-0000-0000-0000-000000000004", "10000000-0000-0000-0000-000000000005", "CROSS_SELL", 0.75, "High organic traffic leads to high customer question volume that SupportAI automates.")
        ]
        for p_a, p_b, r_type, conf, notes in relationships_data:
            rel = ProductRelationship(
                product_a_id=p_a,
                product_b_id=p_b,
                relationship_type=r_type,
                confidence=conf,
                notes=notes
            )
            session.add(rel)
        print(f"  [OK] {len(relationships_data)} Cross-Product relationships created.")

        # ----------------------------------------------------------------------
        # 4. Seed 15 Monitored Sources & Connections
        # ----------------------------------------------------------------------
        print("\n[4/5] Seeding 15 Monitored Source Platforms...")
        sources_data = [
            ("reddit", "Reddit", "Social & Forums", ["SEARCH", "FETCH", "COMMENTS", "REPLIES", "INCREMENTAL_SYNC", "RATE_LIMIT_AWARE"], "https://reddit.com", 60),
            ("x", "X / Twitter", "Social", ["SEARCH", "FETCH", "RATE_LIMIT_AWARE"], "https://x.com", 50),
            ("linkedin", "LinkedIn", "Professional Social", ["SEARCH", "FETCH", "PUBLIC_ENTITY", "RATE_LIMIT_AWARE"], "https://linkedin.com", 30),
            ("youtube", "YouTube", "Video & Transcripts", ["SEARCH", "FETCH", "COMMENTS", "RATE_LIMIT_AWARE"], "https://youtube.com", 45),
            ("instagram", "Instagram", "Social Media", ["SEARCH", "FETCH", "RATE_LIMIT_AWARE"], "https://instagram.com", 30),
            ("facebook", "Facebook Groups & Pages", "Social Communities", ["SEARCH", "FETCH", "COMMENTS"], "https://facebook.com", 25),
            ("threads", "Threads", "Social", ["SEARCH", "FETCH"], "https://threads.net", 40),
            ("tiktok", "TikTok", "Short Video Trends", ["SEARCH", "FETCH"], "https://tiktok.com", 35),
            ("news", "Global Tech News", "News & Media", ["SEARCH", "FETCH", "INCREMENTAL_SYNC"], "https://news.ycombinator.com", 100),
            ("rss", "Industry RSS Feeds", "Feeds", ["FETCH", "INCREMENTAL_SYNC"], "https://rss.feedspot.com", 120),
            ("forums", "Specialized Web Forums", "Forums", ["SEARCH", "FETCH", "COMMENTS", "REPLIES"], "https://discourse.org", 60),
            ("reviews", "G2 & Trustpilot Reviews", "Review Sites", ["SEARCH", "FETCH", "COMMENTS"], "https://g2.com", 20),
            ("web", "Public Web Pages", "Web Crawler", ["FETCH", "BROWSER_RENDER", "HISTORICAL_SEARCH"], "https://google.com", 100),
            ("search", "Search Engines (SerpAPI)", "Search", ["SEARCH"], "https://serpapi.com", 60),
            ("podcasts", "Marketing Podcasts Transcripts", "Audio Transcripts", ["SEARCH", "FETCH"], "https://listennotes.com", 30),
        ]

        for s_id, s_name, s_plat, s_caps, s_url, s_rate in sources_data:
            src = Source(
                id=s_id,
                name=s_name,
                platform=s_plat,
                description=f"Automated ingestion & monitoring connector for {s_name}",
                capabilities=s_caps,
                base_url=s_url,
                default_rate_limit_per_min=s_rate
            )
            session.add(src)

            # Create default connection for organization
            conn = SourceConnection(
                organization_id=org.id,
                source_id=s_id,
                alias=f"{s_name} Primary Feed",
                credentials_encrypted=encrypt_credential(f"demo_token_for_{s_id}"),
                status="active",
                rate_limit_per_min=s_rate
            )
            session.add(conn)
            await session.flush()

            # Create initial health entry
            health = SourceHealth(
                source_connection_id=conn.id,
                mode="NORMAL",
                items_per_hour=142 if s_id == "reddit" else 65,
                success_rate=0.99
            )
            session.add(health)

        print(f"  [OK] {len(sources_data)} Sources, Connections, and Health monitors created.")

        # ----------------------------------------------------------------------
        # 5. Seed 46 Worker Types & Fleet
        # ----------------------------------------------------------------------
        print("\n[5/5] Seeding Worker Types & Fleet...")
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        worker_types_file = repo_root / "contracts" / "enums" / "worker_type.json"
        with open(worker_types_file, "r", encoding="utf-8") as f:
            wt_raw = json.load(f)
            wt_list = wt_raw["enum"]
            zone_defaults = wt_raw.get("x-zone-defaults", {})

        for wt_name in wt_list:
            wt_role = wt_name.replace("_", " ").title() + " Specialist"
            wt = WorkerType(
                id=wt_name,
                name=wt_name.replace("_", " ").title(),
                role=wt_role,
                description=f"Autonomous AI agent specialized in {wt_role} tasks.",
                default_autonomy_level=3 if "action" in wt_name or "lead" in wt_name else 2,
                default_zone=zone_defaults.get(wt_name, "DISCOVERY_CITY"),
                capabilities=["analyze", "extract", "search"],
                default_budget={"max_time_seconds": 300, "max_llm_calls": 5, "max_pages": 10}
            )
            session.add(wt)

        # Create initial fleet of 20 active workers in various states
        initial_fleet = [
            ("Social Crawler #07", "social_discovery", "DISCOVERING", "DISCOVERY_CITY", "social_crawler_bay", "Reddit", "https://reddit.com/r/saas/comments/xyz123"),
            ("Reddit Monitor #02", "social_discovery", "SEARCHING", "DISCOVERY_CITY", "social_crawler_bay", "Reddit", "https://reddit.com/r/ecommerce"),
            ("Web Discovery #01", "web_discovery", "FETCHING", "DISCOVERY_CITY", "web_crawler_bay", "Web", "https://northbeam.io/blog"),
            ("Deep Researcher #04", "deep_research", "RESEARCHING", "RESEARCH_LAB", "deep_research_pod", "Reddit", "https://reddit.com/r/marketing/attribution"),
            ("Evidence Validator #01", "evidence", "VERIFYING", "RESEARCH_LAB", "evidence_chamber", None, None),
            ("Critic Worker #01", "verification", "VERIFYING", "RESEARCH_LAB", "verification_chamber", None, None),
            ("Content Analyzer #03", "content_analyzer", "ANALYZING", "INTELLIGENCE_LAB", "content_analyzer", None, None),
            ("Problem Detector #02", "problem_detector", "ANALYZING", "INTELLIGENCE_LAB", "problem_detector", None, None),
            ("Portfolio Matcher #01", "product_matcher", "MATCHING", "INTELLIGENCE_LAB", "portfolio_matcher", None, None),
            ("Opportunity Detector #05", "opportunity_detector", "ANALYZING", "INTELLIGENCE_LAB", "opportunity_detector", None, None),
            ("Competitor Watcher #01", "competitor_discovery", "SEARCHING", "COMPETITOR_WAR_ROOM", "pricing_watch", "Web", "https://triplewhale.com/pricing"),
            ("Competitor Analyst #02", "competitor_research", "RESEARCHING", "COMPETITOR_WAR_ROOM", "competitor_monitor", "Web", "https://triplewhale.com/changelog"),
            ("Lead Prospector #01", "lead", "DRAFTING", "ACTION_CENTER", "lead_station", "Reddit", "https://reddit.com/r/saas/comments/abc789"),
            ("Outreach Drafter #03", "outreach_draft", "WAITING_APPROVAL", "ACTION_CENTER", "outreach_station", None, None),
            ("Content Generator #02", "content", "DRAFTING", "ACTION_CENTER", "content_station", None, None),
            ("Outcome Analyst #01", "outcome", "LEARNING", "MEMORY_LEARNING", "feedback_processor", None, None),
            ("Knowledge Graph Worker", "relationship_graph", "ANALYZING", "KNOWLEDGE_CORE", "entity_graph", None, None),
            ("ROASSensor Pod Agent", "product_brain", "IDLE", "PRODUCT_CAMPUS", None, None, None),
            ("RevenueSensor Pod Agent", "product_brain", "IDLE", "PRODUCT_CAMPUS", None, None, None),
            ("Central Supervisor #01", "supervisor", "PLANNING", "SUPERVISOR", "supervisor_console", None, None),
        ]

        for w_name, w_type, w_status, w_zone, w_station, w_source, w_url in initial_fleet:
            worker = Worker(
                organization_id=org.id,
                worker_type_id=w_type,
                name=w_name,
                status=w_status,
                logical_zone=w_zone,
                logical_station=w_station,
                current_source=w_source,
                current_url=w_url,
                autonomy_level=3 if "Drafter" in w_name or "Prospector" in w_name else 2
            )
            session.add(worker)

        print(f"  [OK] 46 Worker Types registered and {len(initial_fleet)} workers initialized.")

        # Commit transaction
        await session.commit()
        print("\n" + "=" * 60)
        print("[SUCCESS] DATABASE SEEDING COMPLETED SUCCESSFULLY.")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(seed_database())
