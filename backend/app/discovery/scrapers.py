"""
JobCopilot - Search links for job sites we don't read ourselves.

Builds ready-made search links for Naukri, Instahyre, Cuvette, Cutshort, Hirist, Indeed
and Wellfound. JobCopilot does not fetch listings from these sites: discovery only shows
postings it has actually read (see orchestrator.py), never samples.
"""

from typing import Dict, List



class PlatformScrapers:
    """Search-link builder for Indian and global job sites."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html"
    }

    INDIAN_TECH_HUBS = [
        "Bangalore", "Bengaluru", "Hyderabad", "Pune",
        "Gurgaon", "Gurugram", "Noida", "Delhi NCR",
        "Mumbai", "Chennai", "Remote (India)"
    ]

    @classmethod
    def build_targeted_query(
        cls,
        skills: List[str],
        target_title: str = "Software Engineer",
        location: str = "Bangalore"
    ) -> Dict[str, str]:
        """Generates boolean search queries optimized for Indian and global job search engines."""
        top_skills = skills[:4] if skills else ["Python", "FastAPI"]
        skills_clause = " OR ".join([f'"{s}"' for s in top_skills])
        query_string = f'"{target_title}" ({skills_clause})'
        loc_clean = location.lower().replace(" ", "-")

        return {
            "query": query_string,
            "title": target_title,
            "location": location,
            "naukri_url": f"https://www.naukri.com/{target_title.lower().replace(' ', '-')}-jobs-in-{loc_clean}",
            "instahyre_url": f"https://www.instahyre.com/search-jobs/?query={target_title.replace(' ', '+')}&location={location.replace(' ', '+')}",
            "cuvette_url": f"https://cuvette.tech/app/jobs?search={target_title.replace(' ', '+')}",
            "cutshort_url": f"https://cutshort.io/jobs/{target_title.lower().replace(' ', '-')}-jobs-in-{loc_clean}",
            "hirist_url": f"https://www.hirist.tech/k/{target_title.lower().replace(' ', '-')}-jobs-in-{loc_clean}.html",
            "indeed_url": f"https://www.indeed.com/jobs?q={query_string.replace(' ', '+')}&l={location.replace(' ', '+')}",
            "wellfound_url": f"https://wellfound.com/jobs?query={target_title.replace(' ', '+')}&location={location.replace(' ', '+')}"
        }
