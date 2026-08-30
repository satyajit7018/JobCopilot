"""
JobCopilot - 64-bit SimHash Deduplication & Entity Normalization Engine
Detects duplicate job listings across multiple ATS boards and portals using
canonical entity normalization and SimHash locality-sensitive hashing.
"""

import re
import hashlib
from typing import List, Dict, Any, Optional
from collections import Counter


class JobDeduplicator:
    """Detects duplicate job postings across portals with entity normalization and 64-bit SimHash."""

    COMPANY_NOISE_REGEX = re.compile(
        r'\b(inc|llc|corp|corporation|ltd|limited|pvt|private|technologies|tech|solutions|systems|labs|co)\b|\(yc.*?\)',
        re.IGNORECASE
    )

    TITLE_SYNONYMS = {
        "swe": "software engineer",
        "sde": "software development engineer",
        "mle": "machine learning engineer",
        "ai/ml": "ai machine learning",
        "fullstack": "full stack",
        "frontend": "front end",
        "backend": "back end"
    }

    @classmethod
    def normalize_company(cls, company_name: str) -> str:
        """Normalizes company names across ATS platforms (e.g. 'Stripe, Inc.' -> 'stripe')."""
        if not company_name:
            return ""
        text = company_name.lower().strip()
        text = cls.COMPANY_NOISE_REGEX.sub('', text)
        text = re.sub(r'[^\w\s]', '', text)
        return ' '.join(text.split())

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """Normalizes job titles (e.g. 'Sr. SWE - Backend (Remote)' -> 'software engineer back end')."""
        if not title:
            return ""
        text = title.lower().strip()
        # Remove parenthetical locations or levels
        text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
        # Remove common prefixes / levels
        text = re.sub(r'\b(sr|senior|junior|jr|lead|principal|staff|associate|mid|level\s*\d+|i{1,3}|iv|v)\b', '', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Apply synonyms
        words = text.split()
        normalized_words = [cls.TITLE_SYNONYMS.get(w, w) for w in words]
        return ' '.join(' '.join(normalized_words).split())

    @classmethod
    def normalize_location(cls, location: str) -> str:
        """Categorizes location into regional/remote buckets."""
        if not location:
            return "remote"
        loc = location.lower()
        if "remote" in loc or "anywhere" in loc or "global" in loc:
            return "remote"
        if any(c in loc for c in ["india", "bangalore", "bengaluru", "hyderabad", "pune", "delhi", "gurgaon", "noida", "mumbai"]):
            return "india"
        if any(c in loc for c in ["usa", "united states", "us", "san francisco", "sf", "seattle", "new york", "ny", "austin"]):
            return "usa"
        if any(c in loc for c in ["uk", "united kingdom", "london", "europe", "germany", "berlin", "amsterdam", "canada", "toronto"]):
            return "eu_uk_canada"
        return "other"

    @classmethod
    def compute_simhash_64(cls, text: str) -> int:
        """Computes 64-bit 2-word shingle SimHash of text for fuzzy duplicate detection."""
        if not text:
            return 0
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 0

        # Build 2-word shingles to preserve phrase locality
        if len(words) >= 2:
            shingles = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        else:
            shingles = words

        counts = Counter(shingles)
        v = [0] * 64

        for shingle, weight in counts.items():
            h = int(hashlib.md5(shingle.encode('utf-8'), usedforsecurity=False).hexdigest()[:16], 16)
            for i in range(64):
                if (h >> i) & 1:
                    v[i] += weight
                else:
                    v[i] -= weight

        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    @classmethod
    def hamming_distance(cls, hash1: int, hash2: int) -> int:
        """Counts the differing bits between two 64-bit hashes."""
        x = (hash1 ^ hash2) & 0xFFFFFFFFFFFFFFFF
        return bin(x).count('1')

    @classmethod
    def generate_fingerprint(cls, company: str, title: str, location: str = "", description: str = "") -> str:
        """Generates standard unique fingerprint combining normalized entities and SimHash prefix."""
        norm_c = cls.normalize_company(company)
        norm_t = cls.normalize_title(title)
        norm_l = cls.normalize_location(location)

        raw = f"{norm_c}:{norm_t}:{norm_l}"
        sha_prefix = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

        if description:
            simhash = cls.compute_simhash_64(description)
            return f"{sha_prefix}_{simhash:016x}"
        return sha_prefix

    @classmethod
    def is_duplicate(
        cls,
        company_a: str, title_a: str, desc_a: str,
        company_b: str, title_b: str, desc_b: str,
        max_hamming_distance: int = 8
    ) -> bool:
        """Checks if two job postings represent the exact same opportunity."""
        # Check normalized company match
        if cls.normalize_company(company_a) != cls.normalize_company(company_b):
            return False

        # Check normalized title match
        if cls.normalize_title(title_a) != cls.normalize_title(title_b):
            return False

        # If descriptions exist, check SimHash similarity
        if desc_a and desc_b:
            hash_a = cls.compute_simhash_64(desc_a)
            hash_b = cls.compute_simhash_64(desc_b)
            return cls.hamming_distance(hash_a, hash_b) <= max_hamming_distance

        # If no descriptions, return True only if company & title matched identically
        return True
