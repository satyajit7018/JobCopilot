"""
JobCopilot - Cross-Platform Job Deduplication Engine
Prevents applying multiple times to the same role listed across different portals.
"""

import hashlib
import re


class JobDeduplicator:
    @staticmethod
    def generate_fingerprint(company: str, title: str, location: str = "") -> str:
        def clean(text: str) -> str:
            t = text.lower().strip()
            t = re.sub(r'\(yc.*?\)', '', t)
            t = re.sub(r'[^\w\s]', '', t)
            return ' '.join(t.split())

        c = clean(company)
        t = clean(title)
        l = clean(location)
        raw = f"{c}:{t}:{l}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]
