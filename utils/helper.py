import asyncio
import re
import urllib.parse
from urllib.parse import quote
import hashlib
def check_platform_sync(url: str):
    patterns = {
        "tiktok": r"(https?://)?(www\.)?(vm\.)?tiktok\.com/",
        "instagram": r"(https?://)?(www\.)?instagram\.com/",
        "youtube": r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/",
        "facebook": r"(https?://)?(www\.)?(facebook\.com|fb\.watch)/"
    }

    for platform, pattern in patterns.items():
        if re.search(pattern, url):
            return platform
    return None


async def check_platform(url: str):
    return await asyncio.to_thread(check_platform_sync, url)


def generate_internal_id_sync(title: str) -> str:
    """
    Generates a stable, unique internal ID for an anime title without requiring a database.
    
    The ID combines a 2-3 letter title prefix and a 4-digit numerical suffix derived 
    from the title's hash, satisfying the format OP0322 or NR7981.
    
    Example: 
    "One Piece" -> "OP1379"
    "Naruto Shippuden" -> "NS7562"
    
    Args:
        title: The clean title of the anime (e.g., "Attack on Titan").
        
    Returns:
        A unique, clean string ID consisting of letters and exactly 4 digits.
    """
    if not title:
        return "DEF0000"

    prefix = "".join([word[0] for word in title.split() if word]).upper()[:3]
    if not prefix:
        prefix = "DEF"
    slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "")
    hash_digest = hashlib.sha256(slug.encode('utf-8')).hexdigest()
    hash_int = int(hash_digest, 16)
    modulus = 10000
    unique_number = hash_int % modulus
    padded_number = str(unique_number).zfill(4)
    return f"{prefix}{padded_number}"

async def generate_internal_id(title):
    return await asyncio.to_thread(generate_internal_id_sync,title)

def encodeURIComponent_sync(s):
    return quote(s, safe="~()*!.'")

async def encodeURIComponent(s):
    return await asyncio.to_thread(encodeURIComponent_sync,s)

def deobfuscate(packed_code):
    # 1. Extract the arguments from the eval(function(...)...) call
    pattern = r'eval\(function\(.*?\)\{(.*?)\}\("(.*?)",(\d+),"(.*?)",(\d+),(\d+),(\d+)\)\)'
    match = re.search(pattern, packed_code, re.S)

    if not match:
        print("No match found")
        return None

    func_body, payload, p1, delimiter, p2, p3, p4 = match.groups()

    p1 = int(p1)
    p2 = int(p2)
    p3 = int(p3)
    p4 = int(p4)

    # 2. Base conversion function (same logic as _0xe46c in JS)
    def base_convert(zq, Pt, lS):
        g = list("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/")
        h = g[:Pt]
        i = g[:lS]

        # Convert reversed encoded string → integer
        j = 0
        for power, char in enumerate(reversed(zq)):
            if char in h:
                j += h.index(char) * (Pt ** power)

        # Convert integer to base-lS
        if j == 0:
            return "0"

        result = ""
        while j > 0:
            result = i[j % lS] + result
            j //= lS

        return result

    XP = ""
    Qz = list(delimiter)
    
    i = 0
    length = len(payload)

    # 3. Loop through payload and decode chunks
    while i < length:
        s = ""

        # build chunk until hitting the separator character
        while i < length and payload[i] != Qz[p3]:
            s += payload[i]
            i += 1

        # skip delimiter
        i += 1

        if s:
            # Replace each delimiter symbol with its index
            for idx, symbol in enumerate(Qz):
                s = s.replace(symbol, str(idx))

            # Convert chunk and append the decoded character
            char_code = int(base_convert(s, p3, 10)) - p2
            XP += chr(char_code)

    # 4. Decode unicode
    return urllib.parse.unquote(XP)


def extract_info(js_code):
    # 1. Extract embed URL
    embed_match = re.search(r"var\s+url\s*=\s*['\"]([^'\"]+)['\"]", js_code)
    embed_url = embed_match.group(1) if embed_match else None

    # 2. Extract kwik link from <form action="">
    kwik_match = re.search(r'<form[^>]+action=["\']([^"\']+)', js_code)
    kwik_url = kwik_match.group(1) if kwik_match else None

    # 3. Extract _token value
    token_match = re.search(r'name="_token"\s+value=["\']([^"\']+)', js_code)
    token = token_match.group(1) if token_match else None

    # 4. Extract file size: (109.91 MB)
    size_match = re.search(r'\(([\d\.]+\s*[KMGT]?B)\)', js_code)
    size = size_match.group(1) if size_match else None

    return {
        "embed_url": embed_url,
        "kwik_url": kwik_url,
        "token": token,
        "size": size
    }

