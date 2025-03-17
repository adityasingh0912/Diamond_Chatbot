# 💎 Gemma: AI Chatbot for Diamond Marketplace  

Welcome to **Gemma**, an AI-powered chatbot designed to assist users in finding the perfect diamond based on their preferences. This chatbot integrates advanced **natural language processing (NLP)** and **machine learning** techniques to provide personalized recommendations.  

---

## 🚀 Features  

✔ **Interactive Chatbot** – Ask questions about diamonds, and get tailored recommendations.  
✔ **AI-Powered Search** – Uses **Solr-based search** for high-efficiency results.  
✔ **Expert Analysis** – Provides professional insights on selected diamonds.  
✔ **User-Friendly Interface** – A clean and intuitive web-based UI for seamless interaction.  
✔ **Real-Time Data** – Supports dynamic and continuously updated diamond data.  

---

## 📂 Project Structure  

```
Gemma/
│── app.py                    # Flask application entry point
│── chatbot.py                 # Chatbot logic and recommendation engine
│── templates/
│   ├── index.html             # Web-based chat interface
│── requirements.txt            # Required dependencies
│── README.md                   # Project documentation
│── .gitignore                  # Git ignored files
```

---

## 🛠 Installation & Setup  

### 1️⃣ Clone the Repository  
```sh
git clone https://github.com/adityasingh0912/Diamond_Chatbot.git
cd Diamond_chatbot
```

### 2️⃣ Create a Virtual Environment (Optional but Recommended)  
```sh
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate     # On Windows
```

### 3️⃣ Install Dependencies  
```sh
pip install -r requirements.txt
```

### 4️⃣ Configure Solr and API Keys  
- **Set up Solr**: Add your own diamond dataset to Solr and configure the Solr core.  
- **Set Solr API URL**: Ensure you have the correct Solr API URL to access the indexed data.  
- **Create a `.env` file** in the root directory and add the following:  
```sh
SOLR_URL=your_solr_url_here
GROQ_API_KEY=your_groq_api_key_here
```
Replace `your_solr_url_here` with your actual Solr API endpoint and `your_groq_api_key_here` with your Groq API key.

### 5️⃣ Run the Application  
```sh
python app.py
```

The chatbot will be available at:  
🔗 `http://127.0.0.1:5500/`  

---

## 📝 Usage Instructions  

1. **Open the Web Interface** – Visit the running URL in your browser.  
2. **Ask Questions** – Type queries like "Find me a 1-carat round diamond" in the chat.  
3. **Get Recommendations** – The chatbot will return the best-matching diamonds presented as cards along with expert insights.  

---

## 🤖 How It Works  

- **Data Storage**: Stores and retrieves diamond data from **Solr**, making it efficient for large datasets (14 lakh+ records).  
- **Solr-Based Search**: Uses Solr's powerful search and filtering capabilities, which are more efficient for large, frequently updated datasets.  
- **AI-Powered Response Formatting**: Uses **Llama-Verse** to format responses into structured JSON for displaying diamond details as cards.  
- **Real-Time Updates**: Ensures up-to-date search results without requiring reprocessing embeddings.  

---

## ⚡ Key Technologies Used  

- **Flask**: Web framework for Python  
- **Apache Solr**: High-performance search engine for storing and retrieving diamond data  
- **Llama-Verse**: AI model for converting Solr query results into structured JSON  
- **Groq API**: AI-based chatbot response generation  

---

By using **Solr**, **Llama-Verse**, and **Groq AI**, Gemma provides a **fast, scalable, and AI-driven** search experience for diamond buyers! 💎✨

