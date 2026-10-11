"""
JobCopilot - The company career pages discovery reads.

Every entry was checked against the live board before it was added: the slug is the
company's public board on that platform. A slug that isn't listed here can still be passed
to discovery by hand; it is then tried on all three platforms.
"""

from typing import Dict, List, NamedTuple

INDIA_PLACES = (
    "india", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "gurgaon", "gurugram",
    "noida", "delhi", "chennai", "kolkata", "ahmedabad", "jaipur", "kochi", "indore",
)


class CareerPage(NamedTuple):
    slug: str
    platform: str  # "Greenhouse" | "Lever" | "Ashby"
    name: str
    # Very large worldwide employers: keep only their jobs in India, so a few thousand
    # postings elsewhere don't slow every search down.
    india_only: bool = False


CAREER_PAGES: List[CareerPage] = [
    # Indian companies, and companies that hire mostly in India
    CareerPage("cred", "Lever", "CRED"),
    CareerPage("groww", "Greenhouse", "Groww"),
    CareerPage("inmobi", "Greenhouse", "InMobi"),
    CareerPage("glance", "Greenhouse", "Glance"),
    CareerPage("meesho", "Lever", "Meesho"),
    CareerPage("paytm", "Lever", "Paytm"),
    CareerPage("razorpaysoftwareprivatelimited", "Greenhouse", "Razorpay"),
    CareerPage("sarvam", "Ashby", "Sarvam AI"),
    CareerPage("fampay", "Lever", "FamPay"),
    CareerPage("hevodata", "Lever", "Hevo Data"),
    CareerPage("mindtickle", "Lever", "Mindtickle"),
    CareerPage("pocketfm", "Lever", "Pocket FM"),
    CareerPage("highradius", "Greenhouse", "HighRadius"),
    CareerPage("druva", "Greenhouse", "Druva"),
    CareerPage("tekion", "Ashby", "Tekion"),
    CareerPage("atlan", "Ashby", "Atlan"),
    CareerPage("spotdraft", "Ashby", "SpotDraft"),
    CareerPage("observeai", "Greenhouse", "Observe.AI"),
    CareerPage("skyflow", "Ashby", "Skyflow"),
    CareerPage("composio", "Ashby", "Composio"),
    CareerPage("tide", "Greenhouse", "Tide"),
    # Global tech companies
    CareerPage("stripe", "Greenhouse", "Stripe"),
    CareerPage("brex", "Greenhouse", "Brex"),
    CareerPage("datadog", "Greenhouse", "Datadog"),
    CareerPage("figma", "Greenhouse", "Figma"),
    CareerPage("vercel", "Greenhouse", "Vercel"),
    CareerPage("linear", "Ashby", "Linear"),
    CareerPage("notion", "Ashby", "Notion"),
    CareerPage("perplexity", "Ashby", "Perplexity"),
    CareerPage("sentry", "Ashby", "Sentry"),
    CareerPage("supabase", "Ashby", "Supabase"),
    # Large worldwide employers with big India teams: India jobs only
    CareerPage("databricks", "Greenhouse", "Databricks", india_only=True),
    CareerPage("mongodb", "Greenhouse", "MongoDB", india_only=True),
    CareerPage("okta", "Greenhouse", "Okta", india_only=True),
    CareerPage("zscaler", "Greenhouse", "Zscaler", india_only=True),
    CareerPage("rubrik", "Greenhouse", "Rubrik", india_only=True),
    CareerPage("gitlab", "Greenhouse", "GitLab", india_only=True),
    CareerPage("twilio", "Greenhouse", "Twilio", india_only=True),
    CareerPage("elastic", "Greenhouse", "Elastic", india_only=True),
    CareerPage("snowflake", "Ashby", "Snowflake", india_only=True),
    CareerPage("coinbase", "Greenhouse", "Coinbase", india_only=True),
    CareerPage("agoda", "Greenhouse", "Agoda", india_only=True),
    CareerPage("flexport", "Greenhouse", "Flexport", india_only=True),
    CareerPage("samsara", "Greenhouse", "Samsara", india_only=True),
    CareerPage("airbnb", "Greenhouse", "Airbnb", india_only=True),
    CareerPage("amplitude", "Ashby", "Amplitude", india_only=True),
    CareerPage("confluent", "Ashby", "Confluent", india_only=True),
    CareerPage("thoughtworks", "Greenhouse", "Thoughtworks", india_only=True),
]

BY_SLUG: Dict[str, CareerPage] = {page.slug: page for page in CAREER_PAGES}


def in_india(location: str) -> bool:
    place = (location or "").lower()
    return any(name in place for name in INDIA_PLACES)
