import re
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

class JobDeduplicator:
    """
    Handles URL canonicalization and composite SHA-256 fingerprint generation
    to eliminate duplicate listings across job platforms.
    """
    
    # Common tracking parameters used by recruitment platforms
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gh_jid", "trkid", "sc_channel", "rb_clickid", "ref", "source"
    }

    @classmethod
    def canonicalize_url(cls, url: str) -> str:
        """
        Strips tracking parameters, lowercases hostnames, and normalizes URLs.
        Example:
        'HTTP://Jobs.Amazon.com/pv/123/?utm_source=linkedin&ref=foo'
        -> 'https://jobs.amazon.com/pv/123'
        """
        parsed = urlparse(url.strip())
        
        # Enforce https protocol and lowercase hostname
        scheme = "https"
        netloc = parsed.netloc.lower()
        
        # Strip trailing slashes from path
        path = parsed.path.rstrip("/")
        
        # Filter out tracking query parameters
        query_pairs = parse_qsl(parsed.query)
        filtered_query = [
            (k, v) for k, v in query_pairs 
            if k.lower() not in cls.TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_query)
        
        return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Removes special characters, extra whitespace, and converts to lowercase.
        """
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'[\W_]+', ' ', text) # Replace non-alphanumeric chars with space
        return re.sub(r'\s+', ' ', text).strip()

    @classmethod
    def generate_fingerprint(cls, company: str, title: str, location: str) -> str:
        """
        Creates a composite SHA-256 fingerprint for deduplicating cross-posted listings.
        Fingerprint = SHA256(norm_company + '|' + norm_title + '|' + norm_location)
        """
        norm_company = cls.normalize_text(company)
        norm_title = cls.normalize_text(title)
        norm_location = cls.normalize_text(location)
        
        raw_composite = f"{norm_company}|{norm_title}|{norm_location}"
        return hashlib.sha256(raw_composite.encode("utf-8")).hexdigest()


dedup_engine = JobDeduplicator()