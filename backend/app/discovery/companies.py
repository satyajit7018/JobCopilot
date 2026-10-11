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
    # The company's own website, so its logo and "about" never come from a namesake
    # (Tide the bank is tide.co; tide.com sells laundry powder).
    website: str
    # Very large worldwide employers: keep only their jobs in India, so a few thousand
    # postings elsewhere don't slow every search down.
    india_only: bool = False


CAREER_PAGES: List[CareerPage] = [
    # Indian companies, and companies that hire mostly in India
    CareerPage("cred", "Lever", "CRED", "cred.club"),
    CareerPage("groww", "Greenhouse", "Groww", "groww.in"),
    CareerPage("inmobi", "Greenhouse", "InMobi", "inmobi.com"),
    CareerPage("glance", "Greenhouse", "Glance", "glance.com"),
    CareerPage("meesho", "Lever", "Meesho", "meesho.com"),
    CareerPage("paytm", "Lever", "Paytm", "paytm.com"),
    CareerPage("razorpaysoftwareprivatelimited", "Greenhouse", "Razorpay", "razorpay.com"),
    CareerPage("sarvam", "Ashby", "Sarvam AI", "sarvam.ai"),
    CareerPage("fampay", "Lever", "FamPay", "fampay.in"),
    CareerPage("hevodata", "Lever", "Hevo Data", "hevodata.com"),
    CareerPage("mindtickle", "Lever", "Mindtickle", "mindtickle.com"),
    CareerPage("pocketfm", "Lever", "Pocket FM", "pocketfm.com"),
    CareerPage("highradius", "Greenhouse", "HighRadius", "highradius.com"),
    CareerPage("druva", "Greenhouse", "Druva", "druva.com"),
    CareerPage("tekion", "Ashby", "Tekion", "tekion.com"),
    CareerPage("atlan", "Ashby", "Atlan", "atlan.com"),
    CareerPage("spotdraft", "Ashby", "SpotDraft", "spotdraft.com"),
    CareerPage("observeai", "Greenhouse", "Observe.AI", "observe.ai"),
    CareerPage("skyflow", "Ashby", "Skyflow", "skyflow.com"),
    CareerPage("composio", "Ashby", "Composio", "composio.dev"),
    CareerPage("tide", "Greenhouse", "Tide", "tide.co"),
    # Global tech companies
    CareerPage("stripe", "Greenhouse", "Stripe", "stripe.com"),
    CareerPage("brex", "Greenhouse", "Brex", "brex.com"),
    CareerPage("datadog", "Greenhouse", "Datadog", "datadoghq.com"),
    CareerPage("figma", "Greenhouse", "Figma", "figma.com"),
    CareerPage("vercel", "Greenhouse", "Vercel", "vercel.com"),
    CareerPage("linear", "Ashby", "Linear", "linear.app"),
    CareerPage("notion", "Ashby", "Notion", "notion.com"),
    CareerPage("perplexity", "Ashby", "Perplexity", "perplexity.ai"),
    CareerPage("sentry", "Ashby", "Sentry", "sentry.io"),
    CareerPage("supabase", "Ashby", "Supabase", "supabase.com"),
    # Large worldwide employers with big India teams: India jobs only
    CareerPage("databricks", "Greenhouse", "Databricks", "databricks.com", india_only=True),
    CareerPage("mongodb", "Greenhouse", "MongoDB", "mongodb.com", india_only=True),
    CareerPage("okta", "Greenhouse", "Okta", "okta.com", india_only=True),
    CareerPage("zscaler", "Greenhouse", "Zscaler", "zscaler.com", india_only=True),
    CareerPage("rubrik", "Greenhouse", "Rubrik", "rubrik.com", india_only=True),
    CareerPage("gitlab", "Greenhouse", "GitLab", "gitlab.com", india_only=True),
    CareerPage("twilio", "Greenhouse", "Twilio", "twilio.com", india_only=True),
    CareerPage("elastic", "Greenhouse", "Elastic", "elastic.co", india_only=True),
    CareerPage("snowflake", "Ashby", "Snowflake", "snowflake.com", india_only=True),
    CareerPage("coinbase", "Greenhouse", "Coinbase", "coinbase.com", india_only=True),
    CareerPage("agoda", "Greenhouse", "Agoda", "agoda.com", india_only=True),
    CareerPage("flexport", "Greenhouse", "Flexport", "flexport.com", india_only=True),
    CareerPage("samsara", "Greenhouse", "Samsara", "samsara.com", india_only=True),
    CareerPage("airbnb", "Greenhouse", "Airbnb", "airbnb.com", india_only=True),
    CareerPage("amplitude", "Ashby", "Amplitude", "amplitude.com", india_only=True),
    CareerPage("confluent", "Ashby", "Confluent", "confluent.io", india_only=True),
    CareerPage("thoughtworks", "Greenhouse", "Thoughtworks", "thoughtworks.com", india_only=True),
]

BY_SLUG: Dict[str, CareerPage] = {page.slug: page for page in CAREER_PAGES}


def _key(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


WEBSITE_BY_NAME: Dict[str, str] = {_key(page.name): page.website for page in CAREER_PAGES}


def known_website(name: str) -> str:
    """The website of a company on our list, or "" when it isn't one of them."""
    return WEBSITE_BY_NAME.get(_key(name), "")


def in_india(location: str) -> bool:
    place = (location or "").lower()
    return any(name in place for name in INDIA_PLACES)
