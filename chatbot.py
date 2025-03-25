import re
import json
import os
import random
from dotenv import load_dotenv
import pysolr
from groq import Groq

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# if groq_api_keys_str:
#     groq_api_keys = [key.strip() for key in groq_api_keys_str.split(",")]
#     GROQ_API_KEY = random.choice(groq_api_keys)
# else:
#     GROQ_API_KEY = None
#     print("No API key found")

SOLR_URL = os.getenv("SOLR_URL")
SOLR_COLLECTION_NAME = os.getenv("SOLR_COLLECTION_NAME")

# ------------------- Solr Client Initialization -------------------    
def create_solr_client():                               
    return pysolr.Solr(f'{SOLR_URL}{SOLR_COLLECTION_NAME}', always_commit=False, timeout=10)

solr_client = create_solr_client()


# ------------------- Misspelling Correction and Preprocessing -------------------
COMMON_MISSPELLINGS = {
    "vvs1": "VVS1", "vvs2": "VVS2", "vs1": "VS1", "vs2": "VS2", "si1": "SI1", "si2": "SI2",
    "vvs": "VVS1", "vs": "VS1", "si": "SI1",
    "eye clean": "VS2",
    "colorless": "D", "near colorless": "G", "faint yellow": "K",
    "excellent": "EX", "very good": "VG", "good": "GD", "fair": "F", "poor": "P",
    "none": "NON", "faint": "FNT", "medium": "MED", "strong": "STG",
    "round brilliant": "ROUND", "princess cut": "PRINCESS", "emerald cut": "EMERALD",
    "igi certificate": "IGI", "gia certificate": "GIA", "gia cert": "GIA", "igi cert": "IGI",
    "lab": "lab", "laboratory": "lab", "labgrown": "lab", "lab-grown": "lab", "lab grown": "lab",
    "nat": "natural", "naturally": "natural", "mined": "natural", "earth": "natural", 
    "karat": "carat", "carrat": "carat", "karrat": "carat", "carrot": "carat",
    "clarity": "Clarity", "colour": "Color", "kolor": "Color",
    "symetry": "Symmetry", "symmetri": "Symmetry",
    "polished": "Polish", "florescence": "Fluorescence", "flouresence": "Fluorescence",
    "flourescence": "Fluorescence", "floressence": "Fluorescence",
    "usd": "$", "dollars": "$", "dollar": "$", "price": "budget", "cost": "budget",
    "thousand": "1000", "thousands": "1000", "grand": "1000"
}
# ------------------- Price Conversion Utility -------------------
def convert_price_str(price_str):
    """ Converts '10k' -> 10000, '2.5k' -> 2500, and removes commas """
    price_str = price_str.lower().replace(',', '').replace('$', '')
    match = re.match(r'(\d+(?:\.\d+)?)\s*[kK]', price_str)
    if match:
        return int(float(match.group(1)) * 1000)
    return float(price_str)

def correct_misspellings(query):
    corrected_query = query
    for misspelling, correction in COMMON_MISSPELLINGS.items():
        corrected_query = re.sub(r'\b' + re.escape(misspelling) + r'\b', correction, corrected_query, flags=re.IGNORECASE)
    return corrected_query
def preprocess_query(query):
    cleaned_query = query.lower()
    cleaned_query = re.sub(r'\s+', ' ', cleaned_query)
    cleaned_query = cleaned_query.replace('w/', 'with').replace('w/o', 'without')
    cleaned_query = correct_misspellings(cleaned_query)
    # Handle metric conversion (e.g., "5 mm")
    mm_match = re.search(r'(\d+(?:\.\d+)?)\s*mm', cleaned_query)
    if mm_match:
        mm_value = float(mm_match.group(1))
        cleaned_query += f" with dimension {mm_value} millimeters"
    return cleaned_query

# ------------------- Utility: Extract Constraints from Query -------------------
def extract_constraints_from_query(user_query):
    processed_query = preprocess_query(user_query)
    constraints = {}
    query_lower = user_query.lower()
    
    # ----- Diamond Industry Shorthand Terminology -----
    shorthand_mapping = {
        "3x none": {"Cut": "EX", "Polish": "EX", "Symmetry": "EX", "Flo": "NON"},
        "3x": {"Cut": "EX", "Polish": "EX", "Symmetry": "EX"},
        "3ex none": {"Cut": "EX", "Polish": "EX", "Symmetry": "EX", "Flo": "NON"},
        "3ex": {"Cut": "EX", "Polish": "EX", "Symmetry": "EX"},
        "vg+": {"Cut": "VG", "Polish": "EX", "Symmetry": "EX"},
        "g+": {"Cut": "G", "Polish": "VG", "Symmetry": "VG"},
        "triple ex": {"Cut": "EX", "Polish": "EX", "Symmetry": "EX"},
        "triple excellent": {"Cut": "EX", "Polish": "EX", "Symmetry": "EX"},
        "ideal cut": {"Cut": "ID"},
        "super ideal": {"Cut": "ID", "Polish": "EX", "Symmetry": "EX"},
        "hearts and arrows": {"Cut": "ID", "Polish": "EX", "Symmetry": "EX"}
    }
    
    for term, attributes in shorthand_mapping.items():
        if re.search(r'\b' + re.escape(term) + r'\b', query_lower):
            for attr, value in attributes.items():
                constraints[attr] = value
            break
    
    # ----- Style -----
    style_mapping = {
        "labgrown": "lab",
        "lab grown": "lab",
        "lab": "lab",
        "natural": "natural",
        "ntural": "natural",
        "natual": "natural",
        "nat": "natural"
    }
    for key, value in style_mapping.items():
        if key in query_lower:
            constraints["Style"] = value
            break
    
    # (Existing style regex is kept if needed)
    style_match = re.search(r'\b(lab\s*grown|lab|natural)\b', user_query, re.IGNORECASE)
    if style_match and "Style" not in constraints:
        style = style_match.group(1).lower()
        constraints["Style"] = "lab" if "lab" in style else "natural"

    # ----- Carat -----
    carat_value_match = None

    # Check for "less than" related carat constraints
    less_than_carat_patterns = [
        r'\b(?:under|below|less than|max|max price|at most|upto|up to|no more than|within|maximum|not exceeding)\s+(\d+(?:\.\d+)?)(?:\s*)?(?:carat[s]?|ct[s]?|crt|carrat)\b',
    ]
    for pattern in less_than_carat_patterns:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            constraints["CaratHigh"] = float(match.group(1))
            carat_value_match = match
            break

    # Check for "more than" related carat constraints
    more_than_carat_patterns = [
        r'\b(?:more than|above|over|at least|min(?:imum)?|starting at|from)\s+(\d+(?:\.\d+)?)(?:\s*)?(?:carat[s]?|ct[s]?|crt|carrat)\b',
    ]
    for pattern in more_than_carat_patterns:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            constraints["CaratLow"] = float(match.group(1))
            carat_value_match = match
            break

    carat_patterns = [
        # Range pattern: matches "2 ct and 4 ct", "2ct to 4ct", or "2ct-4ct"
        r'(\d+(?:\.\d+)?)(?:\s*)?(?:to|-|and)(?:\s*)?(\d+(?:\.\d+)?)(?:\s*)?(?:carat[s]?|ct[s]?|crt|carrat)\b',
        # Single value pattern: matches "4 ct" or "4ct"
        r'(\d+(?:\.\d+)?)(?:\s*)?(?:carat[s]?|ct[s]?|crt|carrat)\b'
    ]

    if carat_value_match is None:
        for pattern in carat_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                carat_value_match = match
                if match.lastindex >= 2 and re.fullmatch(r'\d+(?:\.\d+)?', match.group(2).strip()):
                    constraints["CaratLow"] = float(match.group(1))
                    constraints["CaratHigh"] = float(match.group(2))
                else:
                    constraints["Carat"] = float(match.group(1))
                break

    # Additional special phrase checks for common carat values
    if carat_value_match is None:
        if "one carat" in query_lower or "1 carat" in query_lower:
            constraints["Carat"] = 1.0
            carat_value_match = re.search(r'\b(?:one|1)\s+carat\b', query_lower, re.IGNORECASE)
        elif "half carat" in query_lower or "0.5 carat" in query_lower or "0.5 ct" in query_lower:
            constraints["Carat"] = 0.5
            carat_value_match = re.search(r'\b(?:half|0\.5)\s+carat(?:s)?|0\.5\s+ct\b', query_lower, re.IGNORECASE)

    # ----- Budget / Price Extraction -----
    price_patterns = [
        (r'\bprice\s+(?:range|btw)(?:\s*between)?\s*(?:\$)?(\d+(?:,\d+)?(?:\.\d+)?(?:[kK])?)(?:\$)?\s*(?:to|and|-)\s*(?:\$)?(\d+(?:,\d+)?(?:\.\d+)?(?:[kK])?)(?:\$)?',
        lambda m: {"BudgetLow": convert_price_str(m.group(1)), "BudgetHigh": convert_price_str(m.group(2))}),
        # Range extraction: e.g. "between $1,000 and $2k"
        (r'\b(?:between|bet|btw|betwen)\s*\$?(\d+(?:,\d+)?[kK]?)\s*(?:and|to|-)\s*\$?(\d+(?:,\d+)?[kK]?)',
        lambda m: {"BudgetLow": convert_price_str(m.group(1)), "BudgetHigh": convert_price_str(m.group(2))}),
        # Approximate price: e.g. "around $1500"
        (r'\b(?:around|roughly|close to|approx|near|nearly|approximately|about|circa)\s*\$?(\d+(?:,\d+)?[kK]?)',
        lambda m: {"BudgetTarget": convert_price_str(m.group(1))}),
        # Unified keyword extraction: e.g. "budget: $2000", "price: $2500", "cost: $3000"
        (r'\b(?:budget|price|cost)[:\s]*\$?(\d+(?:,\d+)?[kK]?)',
        lambda m: {"BudgetMax": convert_price_str(m.group(1))}),
        # Minimum price: e.g. "at least $500", "more than $600", "starting at $700"
        (r'\b(?:more than|above|over|at least|min(?:imum)?|starting at|from)\s*\$?(\d+(?:,\d+)?[kK]?)',
        lambda m: {"BudgetMin": convert_price_str(m.group(1))}),
        # Under price: e.g. "under $1000", "below $900", "not exceeding $800"
        (r'\b(?:under|below|less than|max|max price|at most|upto|up to|no more than|within|maximum|not exceeding)\s*\$?(?P<price>\d+(?:,\d+)?[kK]?)(?!\s*(?:carat|ct|crt|carrat))\b',
        lambda m: {"Budget": convert_price_str(m.group("price")), "BudgetStrict": True}),
        # Fallback: capture any "$" value (used only if nothing else matched)
        (r'\$\s*(\d+(?:,\d+)?[kK]?)',
        lambda m: {"BudgetMax": convert_price_str(m.group(1))})
    ]

    # Process the patterns in order and update constraints with the first successful match.
    for pattern, action in price_patterns:
        price_match = re.search(pattern, query_lower, re.IGNORECASE)
        # Check if this match overlaps with the already found carat value
        if price_match and (carat_value_match is None or (price_match.start() >= carat_value_match.end() or price_match.end() <= carat_value_match.start())):
            constraints.update(action(price_match))
            break

    # Additional fallback: if no pattern matched and we haven't set any budget keys, try again with the raw query.
    if not any(key in constraints for key in ["BudgetLow", "BudgetHigh", "BudgetTarget", "BudgetMax", "BudgetMin", "Budget"]):
        budget_standalone_match = re.search(r'\$\s*(\d+(?:,\d+)?[kK]?)', user_query, re.IGNORECASE)
        if budget_standalone_match and (carat_value_match is None or (budget_standalone_match.start() >= carat_value_match.end() or budget_standalone_match.end() <= carat_value_match.start())):
            constraints["BudgetMax"] = convert_price_str(budget_standalone_match.group(1))


    # ----- Color -----
    color_mapping = {
        "f light blue": "f",
        "g light": "g",
        "j faint green": "j",
        "j very light blue": "j",
        "k faint brown": "k",
        "k faint color": "k",
        "m faint brown": "m",
        "n v light brown": "n",
        "l faint brown": "l",
        "n very light yellow": "n",
        "n very light brown": "n",
        "g light green": "g"
    }
    found_color = False
    for desc, letter in color_mapping.items():
        if re.search(r'\b' + re.escape(desc) + r'\b', query_lower):
            constraints["Color"] = letter
            found_color = True
            break
    if not found_color:
        simple_color_match = re.search(r'\b([defghijklmn])\s*(?:color|grade|gia)\b', user_query, re.IGNORECASE)
        if not simple_color_match:
            simple_color_match = re.search(r'\b(?:color|grade|gia)\s*([defghijklmn])\b', user_query, re.IGNORECASE)
        if simple_color_match:
            constraints["Color"] = simple_color_match.group(1).lower()

    
    # ----- Color Range -----
    color_range_match = re.search(r'\bcolors?\s+(?:between|from|range)?\s+([defghijklmn])\s+(?:to|and|through|[-])\s+([defghijklmn])', query_lower)
    if color_range_match:
        color_ordering = ["D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"]
        start = color_range_match.group(1).upper()
        end = color_range_match.group(2).upper()
        start_idx = color_ordering.index(start)
        end_idx = color_ordering.index(end)
        # Ensure proper order - D is better than N
        if start_idx <= end_idx:
            constraints["ColorRange"] = color_ordering[start_idx:end_idx+1]
        else:
            constraints["ColorRange"] = color_ordering[end_idx:start_idx+1]

    # ----- Clarity -----
    clarity_match = re.search(r'\b(if|vvs1|vvs2|vs1|vs2|si1|si2)\b', user_query, re.IGNORECASE)
    if clarity_match:   
        constraints["Clarity"] = clarity_match.group(1).upper()
    
    # ----- Clarity Range -----
    clarity_range_match = re.search(r'\bclarity\s+(?:between|from|range)?\s+(if|vvs1|vvs2|vs1|vs2|si1|si2)\s+(?:to|and|through|[-])\s+(if|vvs1|vvs2|vs1|vs2|si1|si2)', query_lower)
    if clarity_range_match:
        clarity_ordering = ["IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2"]
        start = clarity_range_match.group(1).upper()
        end = clarity_range_match.group(2).upper()
        start_idx = clarity_ordering.index(start)
        end_idx = clarity_ordering.index(end)
        # Ensure proper order - IF is better than SI2
        if start_idx <= end_idx:
            constraints["ClarityRange"] = clarity_ordering[start_idx:end_idx+1]
        else:
            constraints["ClarityRange"] = clarity_ordering[end_idx:start_idx+1]
    
    # ----- Cut, Polish, Symmetry Quality -----
    quality_mapping = {
        "ex": "EX",
        "excellent": "EX",
        "id": "ID",
        "ideal": "ID",
        "vg": "VG",
        "very good": "VG",
        "good": "GD",
        "gd": "GD",
        "f": "F",
        "p": "P",
        "fr": "FR"
    }
    quality_pattern_cut_polish = r'(?:\b{attr}\b\s*(?:is\s*)?((?:ex|excellent|id|ideal|vg|very good|good|gd|f|p)))|(?:(?:(ex|excellent|id|ideal|vg|very good|good|gd|f|p))\s+\b{attr}\b)'

    quality_pattern_symmetry = r'(?:\bsymmetry\b\s*(?:is\s*)?((?:ex|excellent|id|ideal|vg|very good|good|gd|f|p|fr)))|(?:(?:(ex|excellent|id|ideal|vg|very good|good|gd|f|p|fr))\s+\bsymmetry\b)'

    # If not already set by shorthand notation
    if "Cut" not in constraints:
        cut_regex = quality_pattern_cut_polish.format(attr='cut')
        cut_match = re.search(cut_regex, user_query, re.IGNORECASE)
        if cut_match:
            quality = (cut_match.group(1) or cut_match.group(2)).lower()
            constraints["Cut"] = quality_mapping.get(quality, quality)

    # If not already set by shorthand notation
    if "Polish" not in constraints:
        polish_regex = quality_pattern_cut_polish.format(attr='polish')
        polish_match = re.search(polish_regex, user_query, re.IGNORECASE)
        if polish_match:
            quality = (polish_match.group(1) or polish_match.group(2)).lower()
            constraints["Polish"] = quality_mapping.get(quality, quality)

    # If not already set by shorthand notation
    if "Symmetry" not in constraints:
        symmetry_match = re.search(quality_pattern_symmetry, user_query, re.IGNORECASE)
        if symmetry_match:
            quality = (symmetry_match.group(1) or symmetry_match.group(2)).lower()
            constraints["Symmetry"] = quality_mapping.get(quality, quality)

    # ----- Fluorescence (Flo) -----
    flo_mapping = {
        "no fluorescence": "NON",
        "none": "NON",
        "fnt": "FNT",        
        "faint": "FNT",      
        "medium": "MED",
        "very slight": "VSL",
        "slight": "SLT",
        "strong": "STG",
        "very strong": "VST"
    }
    # Many ifs due to shorthand notation
    if "Flo" not in constraints:  # Don't override if set by shorthand
        for key, value in flo_mapping.items():
            if key in query_lower:
                constraints["Flo"] = value
                break

    # ----- Negative Fluorescence Preferences -----
    if "no fluorescence" in query_lower or "none fluorescence" in query_lower or "without fluorescence" in query_lower:
        constraints["Flo"] = "NON"
    
    # # Check for negative inputs
    # negative_patterns = [
    #     r'\b(?:don\'t|do not|not|no|avoid)\s+(?:want|need|like|show|include)\s+(?:any\s+)?([a-z\s]+)',
    #     r'\b(?:exclude|without|except)\s+([a-z\s]+)'
    # ]

    # for pattern in negative_patterns:
    #     matches = re.finditer(pattern, query_lower)
    #     for match in matches:
    #         feature = match.group(1).strip()
    #         # Map feature to appropriate exclusion
    #         if "fluorescence" in feature or "fluo" in feature:
    #             constraints["ExcludeFlo"] = ["STG", "VST", "MED"]
    #         elif "inclusion" in feature:
    #             constraints["ExcludeClarity"] = ["SI1", "SI2"]
    #         elif "si1" in feature:
    #             constraints["ExcludeClarity"] = ["SI1"]
    #         elif "si2" in feature:
    #             constraints["ExcludeClarity"] = ["SI2"]

    # ----- Lab -----
    lab_options = ['igi', 'gia', 'gcal', 'none', 'gsi', 'hrd', 'sgl', 'other', 'egl', 'ags', 'dbiod']
    for lab in lab_options:
        if re.search(r'\b' + re.escape(lab) + r'\b', query_lower):
            constraints["Lab"] = lab.upper()
            break

    # # ----- GIA Report Number -----
    # report_match = re.search(r'\b(?:gia|report|certificate)\s*(?:number|#|no)?[:\s]*(\d{10})\b', query_lower)
    # if report_match:
    #     report_number = report_match.group(1)
    #     constraints["ReportNumber"] = report_number

    # ----- Shape -----
    shape_options = [
        'cushion modified', 'round-cornered rectangular modified brilliant', 'old european brilliant',
        'butterfly modified brilliant', 'old mine brilliant', 'modified rectangular brilliant', 'cushion brilliant',
        'square emerald', 'european cut', 'square radiant', 'old miner', 'cushion', 'triangular', 'square',
        'old european', 'asscher', 'princess', 'oval', 'round', 'pear', 'emerald', 'marquise', 'radiant',
        'heart', 'baguette', 'octagonal', 'shield', 'hexagonal', 'other', 'half moon', 'rose',
        'trapeze', 'trapezoid', 'trilliant', 'lozenge', 'kite', 'pentagonal', 'tapered baguette',
        'pentagon', 'heptagonal', 'rectangular', 'bullet', 'briollette', 'rhomboid', 'others', 'star',
        'calf', 'nonagonal'
    ]
    shape_options = sorted([s.lower() for s in shape_options], key=len, reverse=True)
    for shape in shape_options:
        if re.search(r'\b' + re.escape(shape) + r'\b', query_lower):
            constraints["Shape"] = shape.upper()
            break

    # # ----- Ratio and Proportions -----
    # ratio_match = re.search(r'\bratio\s*(?:of)?\s*(\d+(?:\.\d+)?)\s*(?::|to)\s*(\d+(?:\.\d+)?)', query_lower)
    # if ratio_match:
    #     ratio_val = float(ratio_match.group(1)) / float(ratio_match.group(2))
    #     constraints["Ratio"] = ratio_val
    #     constraints["RatioTolerance"] = 0.1  # 10% tolerance

    # # ----- Depth Percentage -----
    # depth_match = re.search(r'\bdepth\s*(?:percentage|percent|\%)\s*(?:of)?\s*(\d+(?:\.\d+)?)', query_lower)
    # if depth_match:
    #     depth_val = float(depth_match.group(1))
    #     constraints["DepthPercentage"] = depth_val
    #     constraints["DepthTolerance"] = 1.0  # 1% tolerance

    # # ----- Table Percentage -----
    # table_match = re.search(r'\btable\s*(?:percentage|percent|\%)\s*(?:of)?\s*(\d+(?:\.\d+)?)', query_lower)
    # if table_match:
    #     table_val = float(table_match.group(1))
    #     constraints["TablePercentage"] = table_val
    #     constraints["TableTolerance"] = 1.0  # 1% tolerance

    # ----- Price Ordering Preference (if no explicit budget) -----
    if "Budget" not in constraints:
        if any(keyword in query_lower for keyword in ["cheapest", "lowest price", "affordable", "low budget"]):
            constraints["PriceOrder"] = "asc"
        elif any(keyword in query_lower for keyword in ["most expensive", "highest price", "priciest", "expensive", "high budget"]):
            constraints["PriceOrder"] = "desc"

    return constraints


# ------------------- Direct Solr Search (Skipping Embedding) -------------------
def direct_solr_search(user_query, solr_client, top_k=10):
    """
    Build a Solr query using the extracted constraints and perform a direct search.
    """
    constraints = extract_constraints_from_query(user_query)
    base_query = "*:*"  # Match all documents
    filter_queries = []
    sort_fields = []  # Sorting priorities

    # # Check if there's a report number search (this would override other constraints)
    # if "ReportNumber" in constraints:
    #     report_number = constraints["ReportNumber"]
    #     base_query = f"ReportNumber:{report_number}"
    #     query_params = {
    #         "q": base_query,
    #         "fl": "Carat,Clarity,Color,Cut,Shape,Price,Style,Polish,Symmetry,Lab,Flo,Width,Height,Length,Depth,pdf,image,video",
    #         "rows": top_k
    #     }
    #     try:
    #         results = solr_client.search(**query_params)
    #         return results.docs
    #     except Exception as e:
    #         print(f"Solr search error: {e}")
    #         return []

    # ------------------ Style Filtering ------------------
    if "Style" in constraints:
        style_value = constraints["Style"].lower()
        filter_queries.append(f"Style:({style_value})")

    # ------------------ Carat Filtering ------------------
    if "CaratLow" in constraints and "CaratHigh" in constraints:
        filter_queries.append(f"Carat:[{constraints['CaratLow']} TO {constraints['CaratHigh']}]")
    elif "Carat" in constraints:
        carat_val = constraints["Carat"]
        tolerance = 0.05 * carat_val  # ±5% tolerance
        filter_queries.append(f"Carat:[{carat_val - tolerance} TO {carat_val + tolerance}]")

    # ------------------ Price Filtering & Sorting ------------------
    if "BudgetMax" in constraints:
        budget_max = constraints["BudgetMax"]
        # Define a narrow band: from 90% of budget_max up to the budget_max.
        narrow_lower_bound = max(100, budget_max * 0.9)  # Ensure a reasonable minimum
        filter_queries.append(f"Price:[{narrow_lower_bound} TO {budget_max}]")
        sort_fields.insert(0, f"abs(sub(Price,{budget_max})) asc")

    elif "BudgetMin" in constraints:
        budget_min = constraints["BudgetMin"]
        # Allow a slightly lower floor for flexibility
        relaxed_min = max(0.9 * budget_min, 100)  # Removed the 4000 limit
        filter_queries.append(f"Price:[{relaxed_min} TO *]")
        sort_fields.insert(0, f"abs(sub(Price,{budget_min})) asc")

    elif "BudgetStrict" in constraints and constraints["BudgetStrict"]:
        strict_budget = constraints["Budget"]
        relaxed_max = strict_budget * 1.05  # Allow up to 5% over budget (instead of 10%)
        filter_queries.append(f"Price:[* TO {relaxed_max}]")
        sort_fields.insert(0, f"abs(sub(Price,{strict_budget})) asc")

    elif "BudgetLow" in constraints and "BudgetHigh" in constraints:
        budget_low = constraints["BudgetLow"]
        budget_high = constraints["BudgetHigh"]
        relaxed_high = budget_high * 1.1  # Allow slightly above budget range (10% buffer)
        filter_queries.append(f"Price:[{budget_low} TO {relaxed_high}]")
        target_price = (budget_low + budget_high) / 2
        sort_fields.insert(0, f"abs(sub(Price,{target_price})) asc")

    elif "BudgetTarget" in constraints:
        target_price = constraints["BudgetTarget"]
        tolerance = max(0.15 * target_price, 500)  # Reduced tolerance (±15% or min $500)
        relaxed_high = target_price * 1.1  # Allow up to 10% higher suggestions
        filter_queries.append(f"Price:[{target_price - tolerance} TO {relaxed_high}]")
        sort_fields.insert(0, f"abs(sub(Price,{target_price})) asc")

    elif "Budget" in constraints:
        budget = constraints["Budget"]
        min_price = max(0, 0.5 * budget)  # Allow lower range instead of forcing 1000
        relaxed_max = budget * 1.1  # Allow up to 10% above budget
        filter_queries.append(f"Price:[{min_price} TO {relaxed_max}]")
        sort_fields.insert(0, f"abs(sub(Price,{budget})) asc")

    # Sorting override for cheapest or expensive requests
    if any(word in user_query.lower() for word in ["cheapest", "lowest price", "affordable", "low budget", "least expensive"]):
        constraints["PriceOrder"] = "asc"
    elif any(word in user_query.lower() for word in ["most expensive", "highest price", "priciest", "expensive", "high budget", "max price"]):
        constraints["PriceOrder"] = "desc"


    # ------------------ Clarity Filtering ------------------
    if "Clarity" in constraints:
        clarity_val = constraints["Clarity"]
        filter_queries.append(f"Clarity:({clarity_val.upper()})")

    elif "ClarityRange" in constraints:
        clarity_range = constraints["ClarityRange"]
        filter_queries.append(f"Clarity:({' OR '.join(clarity_range)})")

    # if "ExcludeClarity" in constraints:
    #     exclude_clarity = constraints["ExcludeClarity"]
    #     filter_queries.append(f"-Clarity:({' OR '.join(exclude_clarity)})")

    # ------------------ Color Filtering ------------------
    if "Color" in constraints:
        color_val = constraints["Color"]
        filter_queries.append(f"Color:({color_val.upper()})")
    
    elif "ColorRange" in constraints:
        color_range = constraints["ColorRange"]
        filter_queries.append(f"Color:({' OR '.join(color_range)})")

    # ------------------ Cut, Polish, Symmetry Filtering ------------------
    if "Cut" in constraints:
        cut_val = constraints["Cut"]
        filter_queries.append(f"Cut:({cut_val.upper()})")

    if "Polish" in constraints:
        polish_val = constraints["Polish"]
        filter_queries.append(f"Polish:({polish_val.upper()})")

    if "Symmetry" in constraints:
        symmetry_val = constraints["Symmetry"]
        filter_queries.append(f"Symmetry:({symmetry_val.upper()})")

    # ------------------ Shape Filtering ------------------
    if "Shape" in constraints:
        shape_val = constraints["Shape"].upper()
        filter_queries.append(f"Shape:({shape_val})")

    # ------------------ Fluorescence Filtering ------------------
    if "Flo" in constraints:
        filter_queries.append(f"Flo:({constraints['Flo']})")

    # if "ExcludeFlo" in constraints:
    #     exclude_flo = constraints["ExcludeFlo"]
    #     filter_queries.append(f"-Flo:({' OR '.join(exclude_flo)})")

    # ------------------ Lab Filtering ------------------
    if "Lab" in constraints:
        lab_val = constraints["Lab"]
        filter_queries.append(f"Lab:({lab_val})")

    # # ------------------ Ratio Filtering ------------------
    # if "Ratio" in constraints:
    #     ratio = constraints["Ratio"]
    #     tolerance = constraints.get("RatioTolerance", 0.1)
    #     # Calculate ratio field from dimensions if not directly stored
    #     filter_queries.append(f"Ratio:[{ratio - tolerance} TO {ratio + tolerance}]")

    # ------------------ Solr Query Parameters ------------------
    query_params = {
        "q": base_query,
        "fq": filter_queries,
        "fl": "Carat,Clarity,Color,Cut,Shape,Price,Style,Polish,Symmetry,Lab,Flo,Width,Height,Length,Depth,pdf,image,video",
        "rows": top_k
    }

    # ------------------ Sorting Priorities ------------------
    if any(keyword in user_query.lower() for keyword in ["maximum carat", "max carat", "largest diamond", "biggest diamond"]):
        sort_fields.insert(0, "Carat desc")  # Sort by largest carat first
    
    if "PriceOrder" in constraints:
        if constraints["PriceOrder"] == "asc":
            sort_fields.insert(0, "Price asc")
        else:
            sort_fields.insert(0, "Price desc")

    # Apply sorting if there are sort fields
    if sort_fields:
        query_params["sort"] = ", ".join(sort_fields)

    try:
        results = solr_client.search(**query_params)
        if not results.docs:
            print("No documents found in Solr results.")
        return results.docs
    except Exception as e:
        print(f"Solr search error: {e}")
        return []

# ------------------- Groq Integration -------------------
def generate_groq_response(user_query, relevant_data, client):
    prompt = f"""
You are a friendly, expert diamond consultant with years of experience helping customers find the perfect diamond.
User Query: "{user_query}"
Your response should be personal, warm, and engaging. Provide an expert recommendation based on the customer's query.
Please analyze the following diamond details and give a very concise response. NOT LONGER THAN 3 SENTENCES.
Your response should include: A brief introductory paragraph (one or two sentences) in a conversational tone explaining what you found and why the top pick stands out while comparing the user query with the recommended diamonds. If the recommendations do not exactly match the query (for example, in carat, fluorescence, or price), include a note explaining that exact matches were not available and describe why one of the alternatives might be better.

Below are some diamond details:
{relevant_data}

Make sure the JSON is valid and can be parsed by JavaScript's JSON.parse() function.
"""
    chat_completion = client.chat.completions.create(
        messages=[{"role": "system", "content": prompt}],
        model="llama-3.3-70b-specdec",
        temperature=0.7,
        max_tokens=2000
    )
    return chat_completion.choices[0].message.content

# ------------------- Main Chatbot Logic -------------------
def diamond_chatbot(user_query, solr_client, client):
    if user_query.strip().lower() in ["hi", "hello"]:
        return "Hey there! I'm your diamond guru. Ready to help you find that perfect sparkle? Tell me what you're looking for!"

    constraints = extract_constraints_from_query(user_query)
    
    # -------------------- Debugging --------------------
    # print("Extracted Constraints:", constraints)
    # ---------------------------------------------------
    if not constraints and not any(keyword in user_query.lower() for keyword in ["maximum", "minimum", "lowest", "highest", "largest", "smallest"]):
        return "Hello! I'm your diamond assistant. Please let me know your preferred carat, clarity, color, cut, or budget so I can help you find the perfect diamond."

    docs = direct_solr_search(user_query, solr_client, top_k=100)
    if not docs:
        return "No matching diamonds found. Please try a different query."

    random.shuffle(docs)  # Randomize the order of the retrieved documents

    top_5 = docs[:5]
    relevant_data_list = []
    for doc in top_5:
        diamond_info = {
            "Carat": doc.get("Carat"),
            "Clarity": doc.get("Clarity"),
            "Color": doc.get("Color"),
            "Cut": doc.get("Cut"),
            "Shape": doc.get("Shape"),
            "Price": doc.get("Price"),
            "Style": doc.get("Style"),
            "Polish": doc.get("Polish"),
            "Symmetry": doc.get("Symmetry"),
            "Lab": doc.get("Lab"),
            "Flo": doc.get("Flo"),
            "Length": doc.get("Length"),
            "Height": doc.get("Height"),
            "Width": doc.get("Width"),
            "Depth": doc.get("Depth"),
            "pdf": doc.get("pdf"),
            "image": doc.get("image"),
            "video": doc.get("video")
        }
        relevant_data_list.append(diamond_info)
    relevant_data_json = json.dumps(relevant_data_list, indent=2)

    # Groq response, comment out while debug to prevent api calls!
    groq_response = generate_groq_response(user_query, relevant_data_json, client)
    diamond_data_response = f"<diamond-data>\n{relevant_data_json}\n</diamond-data>"
    final_response = f"{groq_response}\n{diamond_data_response}"
    return final_response

def main(): 
    client = Groq(api_key=GROQ_API_KEY)
    solr_client = create_solr_client()

    while True:
        user_query = input("Hi! How can I help you? : ")
        if user_query.lower() in ["exit", "quit"]:
            print("Thank you for visiting! Have a wonderful day.")
            break

        constraints = extract_constraints_from_query(user_query)
        if "Style" not in constraints:
            style_input = input("Please specify the style (LabGrown or Natural): ")
            user_query += " " + style_input.strip()

        response = diamond_chatbot(user_query, solr_client, client)
        print(response)
        print("\n---\n")

if __name__ == "__main__":
    main()
