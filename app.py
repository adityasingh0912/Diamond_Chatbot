from flask import Flask, render_template, request, jsonify
import re
import json
import os
from chatbot import diamond_chatbot, create_solr_client, extract_constraints_from_query
from groq import Groq
from dotenv import load_dotenv

def convert_markdown_to_html(text):
    """
    Convert markdown bold (text) into HTML <strong>text</strong>.
    """
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Initialize Groq client and Solr client
client = Groq()
solr_client = create_solr_client()

def generate_expert_analysis(user_query, diamond_data):
    """
    Generate expert analysis using Groq.
    """
    # Guard against empty diamond data
    if not diamond_data or len(diamond_data) == 0:
        return None
    
    # Convert diamond data to readable string format
    diamond_str = "\n".join([str(diamond) for diamond in diamond_data])
    
    prompt = f"""
    You are a diamond expert with years of experience in the industry.
    Based on the user query and the diamonds found, provide a brief 2-3 line expert recommendation.
    Please highlight the important attributes such as Carat, Clarity, Color, Cut, etc.
    Focus on what makes these particular diamonds a good match for the customer's needs.
    Be concise but insightful.
    
    User Query: {user_query}
    
    Diamonds Found:
    {diamond_str}
    
    Your expert analysis (2-3 lines only):
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}],
            model="llama-3.3-70b-specdec",
            temperature=0.7,
            max_tokens=250
        )
        analysis = chat_completion.choices[0].message.content
        
        # Wrap the analysis in our special tags for styling
        return f"<expert-analysis>{analysis}</expert-analysis>"
    except Exception as e:
        print(f"Error generating expert analysis: {e}")
        return "<expert-analysis>These diamonds match your criteria and offer excellent value. Consider factors like Cut quality and Color which significantly impact a diamond's brilliance.</expert-analysis>"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_query = data.get('message', '').strip()

        if not user_query:
            return jsonify({
                'response': "I'm your diamond assistant. How can I help you find the perfect diamond today?"
            })

        constraints = extract_constraints_from_query(user_query)
        ordering_keywords = ["maximum", "minimum", "lowest", "highest", "largest", "smallest", "cheapest", "lowest price", "affordable", "low budget", "most expensive", "highest price", "priciest", "expensive", "high budget"]
        if ("Style" not in constraints and 
            user_query.lower() not in ["hi", "hello"] and 
            (len(constraints) > 0 or any(keyword in user_query.lower() for keyword in ordering_keywords))):
            return jsonify({
                'response': "Would you prefer a lab-grown or natural diamond? Lab-grown diamonds are eco-friendly and more affordable, while natural diamonds are mined from the earth and traditionally valued.",
                'needs_style': True
            })

        response = diamond_chatbot(user_query, solr_client, client)
        if not response:
            response = "I'm having trouble understanding your request. Could you please provide more details about the diamond you're looking for?"

        # Extract the diamond-data block from the Groq response
        diamond_data_match = re.search(r'<diamond-data>([\s\S]*?)</diamond-data>', response)
        diamond_data = None
        if diamond_data_match:
            try:
                diamond_data = json.loads(diamond_data_match.group(1))
            except json.JSONDecodeError:
                print("Error decoding diamond data JSON")

        # Generate expert analysis ONLY if we have valid diamond data
        expert_recommendation_html = None
        if diamond_data:
            expert_recommendation = generate_expert_analysis(user_query, diamond_data)
            expert_recommendation_html = convert_markdown_to_html(expert_recommendation)

        # IMPORTANT: Do not append the expert analysis to the response text!
        # Instead, return it separately.
        response_html = convert_markdown_to_html(response)

        return jsonify({
            'response': response_html,
            'expert_recommendation': expert_recommendation_html
        })

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({
            'response': "I apologize, but I encountered an error. Please try your request again."
        }), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5505)