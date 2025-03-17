import re
import json
import os
from dotenv import load_dotenv
import pysolr
from groq import Groq

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SOLR_URL = os.getenv("SOLR_URL", "http://192.168.1.11:8983/solr/")
SOLR_COLLECTION_NAME = os.getenv("SOLR_COLLECTION_NAME", "diamond_core")

# ------------------- Solr Client Initialization -------------------
def create_solr_client():
    return pysolr.Solr(f'{SOLR_URL}{SOLR_COLLECTION_NAME}', always_commit=False, timeout=10)

solr_client = create_solr_client()

def convert_price_str(price_str):
    """ Converts '10k' -> 10000, '2.5k' -> 2500, and removes commas """
    price_str = price_str.lower().replace(',', '')  # Remove commas (e.g., "10,000" -> "10000")
    match = re.match(r'(\d+(?:\.\d+)?)\s*[kK]', price_str)  # Match "10k" or "2.5k"
    if match:
        return int(float(match.group(1)) * 1000)  # Convert to integer dollars
    return float(price_str)  # Otherwise, return as number

# ------------------- Utility: Extract Constraints from Query -------------------
def extract_constraints_from_query(user_query):
    constraints = {}
    query_lower = user_query.lower()
    
    # ----- Style -----
    style_mapping = {
        "labgrown": "lab",
        "lab grown": "lab",
        "lab": "lab",
        "natural": "natural",
        "ntural": "natural",
        "natual": "natural"
    }
    for key, value in style_mapping.items():
        if key in query_lower:
            constraints["Style"] = value
            break
    # (Existing style regex is kept if needed)
    style_match = re.search(r'\b(lab\s*grown|lab|natural)\b', user_query, re.IGNORECASE)
    if style_match:
        style = style_match.group(1).lower()
        constraints["Style"] = "lab" if "lab" in style else "natural"

    # ----- Carat -----
    # Capture carat range (e.g., "1.5 to 2 carats" or "1.5-2 ct")
    carat_range_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:-?\s*carat[s]?|-?\s*ct[s]?|-?\s*crt|-?\s*carrat)\b', user_query, re.IGNORECASE)
    if carat_range_match:
        constraints["CaratLow"] = float(carat_range_match.group(1))
        constraints["CaratHigh"] = float(carat_range_match.group(2))
    else:
        # Capture single carat values (e.g., "2.5 carats", "3 ct", "3-carat")
        carat_match = re.search(r'(\d+(?:\.\d+)?)\s*(-?\s*carat[s]?|-?\s*ct[s]?|-?\s*crt|-?\s*carrat|-?\s*point[s]?|-?\s*pt)\b', user_query, re.IGNORECASE)
        if carat_match:
            constraints["Carat"] = float(carat_match.group(1))
    
    # ----- Budget / Price Range -----
    price_range_match = re.search(
        r'\b(?:between|bet|btw|betwen)\s*\$?(\d+(?:,\d+)?[kK]?)\s*(?:and|to|-)\s*\$?(\d+(?:,\d+)?[kK]?)',
        user_query, re.IGNORECASE)
    if price_range_match:
        constraints["BudgetLow"] = convert_price_str(price_range_match.group(1))
        constraints["BudgetHigh"] = convert_price_str(price_range_match.group(2))
    else:
        # Include "roughly" in the approximate price pattern.
        approx_price_match = re.search(
            r'\b(?:around|roughly|close to|approx|near|nearly|approximately)\s*\$?(\d+(?:,\d+)?[kK]?)',
            user_query, re.IGNORECASE)
        if approx_price_match:
            constraints["BudgetTarget"] = convert_price_str(approx_price_match.group(1))
        
        # Unified extraction for phrases like "budget:" or "price:"
        keyword_match = re.search(
            r'\b(?:budget|price)[:\s]*\$?(\d+(?:,\d+)?[kK]?)',
            user_query, re.IGNORECASE)
        if keyword_match:
            constraints["BudgetMax"] = convert_price_str(keyword_match.group(1))
            # Remove any fallback Budget key to avoid conflicts.
            constraints.pop("Budget", None)
        else:
            # Capture phrases like "min $3000" or "above $5000"
            min_price_match = re.search(
                r'\b(?:more than|above|over|at least|min(?:imum)?)\s*\$?(\d+(?:,\d+)?[kK]?)',
                user_query, re.IGNORECASE)
            if min_price_match:
                constraints["BudgetMin"] = convert_price_str(min_price_match.group(1))
            
            # Capture phrases like "under $10k" or "less than $5000"
            under_match = re.search(
                r'\b(?:under|below|less than|max|max price|at most|upto|up to)\s*\$?(\d+(?:,\d+)?[kK]?)',
                user_query, re.IGNORECASE)
            if under_match:
                constraints["Budget"] = convert_price_str(under_match.group(1))
                constraints["BudgetStrict"] = True
            else:
                # Fallback: only capture numbers with a "$" (to avoid catching carat values)
                budget_standalone_match = re.search(r'\$\s*(\d+(?:,\d+)?[kK]?)', user_query, re.IGNORECASE)
                if budget_standalone_match and "BudgetMax" not in constraints and "Budget" not in constraints:
                    constraints["BudgetMax"] = convert_price_str(budget_standalone_match.group(1))


    under_match = re.search(r'\b(?:under|below|less than)\s*\$?(\d+(?:,\d+)?[kK]?)', query_lower, re.IGNORECASE)
    if under_match:
        price_str = under_match.group(1).replace(',', '')
        constraints["Budget"] = convert_price_str(price_str)
        constraints["BudgetStrict"] = True

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
        simple_color_match = re.search(r'\b([defghijklmn])(?:\s*grade|\s*color|\s*gia)?\b', user_query, re.IGNORECASE)
        if simple_color_match:
            constraints["Color"] = simple_color_match.group(1).lower()

    clarity_match = re.search(r'\b(if|vvs1|vvs2|vs1|vs2|si1|si2)\b', user_query, re.IGNORECASE)
    if clarity_match:
        constraints["Clarity"] = clarity_match.group(1).upper()
    
    quality_mapping = {
        "ex": "ex",
        "excellent": "ex",
        "id": "id",
        "ideal": "id",
        "vg": "vg",
        "very good": "vg",
        "good": "vg",
        "gd": "gd",
        "f": "f",
        "p": "p",
        "fr": "fr"
    }
    quality_pattern_cut_polish = r'(?:{attr}\s*(?:is\s*)?((?:ex|excellent|id|ideal|vg|very good|good|gd|f|p)))|(?:(?:(ex|excellent|id|ideal|vg|very good|good|gd|f|p))\s*{attr})'
    quality_pattern_symmetry = r'(?:symmetry\s*(?:is\s*)?((?:ex|excellent|id|ideal|vg|very good|good|gd|f|p|fr)))|(?:(?:(ex|excellent|id|ideal|vg|very good|good|gd|f|p|fr))\s*symmetry)'

    cut_regex = quality_pattern_cut_polish.format(attr='cut')
    cut_match = re.search(cut_regex, user_query, re.IGNORECASE)
    if cut_match:
        quality = (cut_match.group(1) or cut_match.group(2)).lower()
        constraints["Cut"] = quality_mapping.get(quality, quality)

    polish_regex = quality_pattern_cut_polish.format(attr='polish')
    polish_match = re.search(polish_regex, user_query, re.IGNORECASE)
    if polish_match:
        quality = (polish_match.group(1) or polish_match.group(2)).lower()
        constraints["Polish"] = quality_mapping.get(quality, quality)

    symmetry_match = re.search(quality_pattern_symmetry, user_query, re.IGNORECASE)
    if symmetry_match:
        quality = (symmetry_match.group(1) or symmetry_match.group(2)).lower()
        constraints["Symmetry"] = quality_mapping.get(quality, quality)

    # ----- Fluorescence (Flo) -----
    flo_mapping = {
        "no fluorescence": "non",
        "none": "non",
        "faint": "fnt",
        "medium": "med",
        "very slight": "vsl",
        "slight": "slt",
        "strong": "stg",
        "very strong": "vst"
    }
    for key, value in flo_mapping.items():
        if key in query_lower:
            constraints["Flo"] = value
            break

    # ----- Lab -----
    lab_options = ['igi', 'gia', 'gcal', 'none', 'gsi', 'hrd', 'sgl', 'other', 'egl', 'ags', 'dbiod']
    for lab in lab_options:
        if re.search(r'\b' + re.escape(lab) + r'\b', query_lower):
            constraints["Lab"] = lab
            break

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
            constraints["Shape"] = shape
            break

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

    # ------------------ Style Filtering ------------------
    if "Style" in constraints:
        style_value = constraints["Style"].lower()
        filter_queries.append(f"Style:({style_value})")

    # ------------------ Carat Filtering ------------------
    if "Carat" in constraints:
        carat_val = constraints["Carat"]
        tolerance = 0.05 * carat_val  # ±5% tolerance
        filter_queries.append(f"Carat:[{carat_val - tolerance} TO {carat_val + tolerance}]")
    if "CaratLow" in constraints and "CaratHigh" in constraints:
        filter_queries.append(f"Carat:[{constraints['CaratLow']} TO {constraints['CaratHigh']}]")

    # ------------------ Price Filtering & Sorting ------------------
    if "BudgetMax" in constraints:
        budget_max = constraints["BudgetMax"]
        min_price = max(0.7 * budget_max, 5000)  # Avoid very cheap diamonds
        relaxed_max = budget_max * 1.15  # Allow up to 15% higher-priced suggestions
        filter_queries.append(f"Price:[{min_price} TO {relaxed_max}]")
        sort_fields.insert(0, f"abs(sub(Price,{budget_max})) asc")  # Prioritize closest to budget

    elif "BudgetMin" in constraints:
        budget_min = constraints["BudgetMin"]
        relaxed_min = max(0.9 * budget_min, 4000)  # Allow 10% lower-priced options
        filter_queries.append(f"Price:[{relaxed_min} TO *]")
        sort_fields.insert(0, f"abs(sub(Price,{budget_min})) asc")  # Prioritize closest to budget

    elif "BudgetStrict" in constraints and constraints["BudgetStrict"]:
        strict_budget = constraints["Budget"]
        relaxed_max = strict_budget * 1.1  # Allow up to 10% over budget
        filter_queries.append(f"Price:[* TO {relaxed_max}]")
        sort_fields.insert(0, f"abs(sub(Price,{strict_budget})) asc")  # Prioritize closest to budget

    elif "BudgetLow" in constraints and "BudgetHigh" in constraints:
        budget_low = constraints["BudgetLow"]
        budget_high = constraints["BudgetHigh"]
        relaxed_high = budget_high * 1.15  # Allow slightly above budget range
        filter_queries.append(f"Price:[{budget_low} TO {relaxed_high}]")
        target_price = (budget_low + budget_high) / 2
        sort_fields.insert(0, f"abs(sub(Price,{target_price})) asc")  # Prioritize closest to budget range

    elif "BudgetTarget" in constraints:
        target_price = constraints["BudgetTarget"]
        tolerance = max(0.15 * target_price, 1000)  # ±15% or at least ±$1000
        relaxed_high = target_price * 1.15  # Allow up to 15% higher suggestions
        filter_queries.append(f"Price:[{target_price - tolerance} TO {relaxed_high}]")
        sort_fields.insert(0, f"abs(sub(Price,{target_price})) asc")  # Prioritize closest to target

    elif "Budget" in constraints:
        budget = constraints["Budget"]
        min_price = max(0.5 * budget, 1000)  # Ensure a reasonable minimum price
        relaxed_max = budget * 1.15  # Allow up to 15% above budget
        filter_queries.append(f"Price:[{min_price} TO {relaxed_max}]")
        sort_fields.insert(0, f"abs(sub(Price,{budget})) asc")  # Prioritize closest to budget

    # ------------------ Clarity Filtering ------------------
    if "Clarity" in constraints:
        clarity_val = constraints["Clarity"]
        filter_queries.append(f"Clarity:({clarity_val.upper()})")

    # ------------------ Color Filtering ------------------
    if "Color" in constraints:
        color_val = constraints["Color"]
        filter_queries.append(f"Color:({color_val.upper()})")

    # ------------------ Cut Filtering ------------------
    if "Cut" in constraints:
        cut_val = constraints["Cut"]
        filter_queries.append(f"Cut:({cut_val.upper()})")

    # ------------------ Shape Filtering ------------------
    if "Shape" in constraints:
        shape_val = constraints["Shape"].upper()
        filter_queries.append(f"Shape:({shape_val})")

    # ------------------ Solr Query Parameters ------------------
    query_params = {
        "q": base_query,
        "fq": filter_queries,
        "fl": "Carat,Clarity,Color,Cut,Shape,Price,Style,Polish,Symmetry,Lab,Flo,Width,Height,Length,Depth,pdf,image,video",
        "rows": top_k
    }

    # ------------------ Sorting Priorities ------------------
    if "Carat" in constraints:
        target_carat = constraints["Carat"]
        sort_fields.append(f"abs(sub(Carat,{target_carat})) asc")  # Sort closest to desired carat

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
Your response should be personal, warm, and engaging. Provide an expert recommendation based on the customer's query.

Please analyze the following diamond details and produce a JSON response that includes the top matching diamonds.
Your response should include:
1. A brief introductory paragraph (one or two sentences) in a conversational tone explaining what you found and why the top pick stands out.
2. A special marker <diamond-data> immediately followed by a valid JSON array of diamond objects.
3. Close with </diamond-data>.

Each diamond object must include the following attributes:
- Carat
- Clarity
- Color
- Cut
- Shape
- Price
- Style
- Polish
- Symmetry
- Lab
- Flo
- Length
- Height
- Width
- Depth
- pdf
- image
- video

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

def groq_response(user_query, diamond_data, groq_client):
    prompt = f"""
You are a friendly, expert diamond consultant with years of experience helping customers find the perfect diamond.
Your response should be personal, warm, and engaging. Based on the customer's query and the diamond data provided, please do the following:
1. Begin with an introductory paragraph that states how many diamonds were found for the query (e.g., "Found 3 Diamonds for '3 carat'").
2. Provide a brief expert recommendation tailored for a 3-carat diamond—mentioning attributes like cut, color, and clarity.
3. List each diamond recommendation on separate lines. For each diamond, display:
   - Carat (e.g., "3.01 Carat")
   - Clarity (e.g., "Clarity: SI1" or "Clarity: N/A" if not available)
   - Color (e.g., "Color: G")
   - Cut (e.g., "Cut: Excellent")
   - Polish (or "N/A")
   - Symmetry (or "N/A")
   - Style (or "N/A")
   - Price (formatted as currency, e.g., "$15,999")
4. End each recommendation with "View Details".
5. Enclose the list of diamond recommendations between the tags <diamond-data> and </diamond-data>.

Customer Query: "{user_query}"

Here is the diamond data in JSON for reference:
{diamond_data}

Please produce the final output as plain text following the above instructions.
"""
    response = groq_client.chat.completions.create(
        messages=[{"role": "system", "content": prompt}],
        model="qwen-2.5-32b",
        temperature=0.7,
        max_tokens=1500
    )
    return response.choices[0].message.content


# ------------------- Main Chatbot Logic -------------------
def diamond_chatbot(user_query, solr_client, client):
    if user_query.strip().lower() in ["hi", "hello"]:
        return "Hey there! I'm your diamond guru 😎. Ready to help you find that perfect sparkle? Tell me what you're looking for!"

    constraints = extract_constraints_from_query(user_query)
    if not constraints and not any(keyword in user_query.lower() for keyword in ["maximum", "minimum", "lowest", "highest", "largest", "smallest"]):
        return "Hello! I'm your diamond assistant. Please let me know your preferred carat, clarity, color, cut, or budget so I can help you find the perfect diamond."

    docs = direct_solr_search(user_query, solr_client, top_k=10)
    if not docs:
        return "No matching diamonds found. Please try a different query."

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

    groq_response = generate_groq_response(user_query, relevant_data_json, client)
    return groq_response

def main():
    client = Groq()
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
