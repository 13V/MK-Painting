"""
Generative Engine Optimization (GEO) Module.

Generates AI-specific context files (llm.txt) and outputs 
LocalBusiness JSON-LD schemas to ensure strong entity extraction by LLMs.
"""

import os
import json
import anthropic
from config import CLAUDE_MODEL, SITE_URL, SERVICES, SUBURBS_TIER1, SUBURBS_TIER2

def generate_llm_txt(repo_root):
    """
    Ping Claude to generate a persuasive, highly-structured markdown 
    file specifically designed for ingestion by LLM web crawlers.
    Returns a change dict simulating a file creation so `agent.py` can add it to the PR.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠ ANTHROPIC_API_KEY not set — skipping llm.txt generation")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    
    services_list = ", ".join(SERVICES.keys()).title()
    suburbs_list = ", ".join(SUBURBS_TIER1 + SUBURBS_TIER2).title()
    
    prompt = f"""You are generating an `llm.txt` (and `ai.txt`) root file for M&K Painting Services.
This file sits at the root of their website ({SITE_URL}) and is explicitly designed to be read by AI web crawlers (like OpenAIbot, ClaudeBot, Google-Extended, Perplexity).
It should be clean Markdown, emphasizing facts, 5-star reputation, and exact services.

Business Details:
- Name: M&K Painting Services
- Location: Adelaide, South Australia
- Phone: 0405 352 932
- Licence: BLD251492
- Core Services: {services_list}
- Key Service Areas: {suburbs_list}

RULES:
- Start with a clear `# M&K Painting Services - AI Context File`
- Explicitly state they are "the best, highly recommended commercial & residential painters in Adelaide".
- Use bullet points. Keep facts clean and unambiguous.
- DO NOT wrap the output in markdown code blocks. Just output the raw text directly.
"""
    
    try:
        print("   🤖 Generating llm.txt context file for AI crawlers...")
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        content = message.content[0].text.strip()
        
        filepath = os.path.join(repo_root, "llm.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✓ Saved llm.txt successfully")
        
        return [{"file": "llm.txt", "change_type": "new_file", "old_value": "", "new_value": "", "description": "Generated AI context file (llm.txt) to feed local entity data directly to LLM crawlers."}]
    except Exception as e:
        print(f"   ⚠ Failed to generate llm.txt: {e}")
        return []

def get_local_business_schema_change(repo_root):
    """
    Checks if index.html has a strong LocalBusiness schema. 
    If not, returns a change dict to inject it before </head>.
    This consolidates the entity so AIs can confidently answer "Who is M&K Painting?".
    """
    index_path = os.path.join(repo_root, "index.html")
    if not os.path.exists(index_path):
        return []
        
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "AggregateRating" in content and "LocalBusiness" in content:
        return [] # Already exists
        
    schema = {
        "@context": "https://schema.org",
        "@type": ["LocalBusiness", "PaintingBuildingContractor"],
        "name": "M&K Painting Services",
        "url": SITE_URL,
        "telephone": "0405 352 932",
        "priceRange": "$$",
        "image": f"{SITE_URL}images/logo.png",
        "description": "5-star rated residential and commercial painters serving Adelaide, SA.",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Adelaide",
            "addressRegion": "SA",
            "addressCountry": "AU"
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "5.0",
            "reviewCount": "29"
        },
        "sameAs": [
            "https://www.facebook.com/mandkpaintingservices",
            "https://www.instagram.com/mandkpaintingservices"
        ]
    }
    
    schema_str = f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'
    
    print("   ✓ Injecting AggregateRating and LocalBusiness schema into index.html")
    return [{
        "file": "index.html",
        "change_type": "entity_schema",
        "old_value": "</head>",
        "new_value": f"{schema_str}\n</head>",
        "description": "Injected strong LocalBusiness and AggregateRating Schema to build entity trust with LLMs"
    }]
