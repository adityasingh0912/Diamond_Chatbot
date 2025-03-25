# Gemma v2: Advanced Diamond Marketplace Chatbot

Welcome to **Gemma v2** – the next-generation version of our AI-powered diamond assistant. This branch brings major improvements including enhanced search capabilities, multimedia support, and a refined user interface. Please note that **Gemma v2** is designed to work with a local Solr instance (`diamond_core`) and requires additional setup steps compared to the main branch. It is not a quick clone-and-run version from GitHub.

---

## 🚀 Key Enhancements in v2

- **Local Solr Integration:**  
  Gemma v2 uses a local Solr server with a dedicated `diamond_core` for efficient, high-performance diamond data searches.

- **Multimedia Support:**  
  Enhanced UI with support for images, videos, and PDF certificates that provide richer diamond details and expert insights.

- **Improved Chatbot Functionality:**  
  Advanced natural language processing and refined recommendation logic are implemented through major code improvements in the chatbot engine.

- **Enhanced User Interface:**  
  Updated styling and responsive design improvements to provide an optimal experience on both desktop and mobile devices.

---

## 🛠 Installation & Setup for v2

### Prerequisites

- **Local Solr Server:**  
  Install and configure Apache Solr, then create a core named `diamond_core`. Ensure that your Solr instance is running (e.g., on `http://localhost:8983/solr/diamond_core`).

- **Diamond Data & Multimedia:**  
  Prepare your diamond dataset along with associated images, videos, and PDFs. The v2 branch expects these multimedia files to be available locally (or via designated URLs).

### Setup Instructions

1. **Clone the Repository and Switch to the v2 Branch:**

   ```sh
   git clone https://github.com/yourusername/Gemma.git
   cd Gemma
   git checkout v2
   ```

2. **Create a Virtual Environment (Optional but Recommended):**

   ```sh
   python -m venv venv
   source venv/bin/activate   # On macOS/Linux
   venv\Scripts\activate      # On Windows
   ```

3. **Install Dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**

   Create a `.env` file in the root directory with at least the following keys:
   ```sh
   GROQ_API_KEY=your_groq_api_key_here
   SOLR_URL=http://localhost:8983/solr/
   SOLR_COLLECTION_NAME=diamond_core
   ```

5. **Update Solr with Diamond Data:**

   Use the provided `solr_update.py` script to upload your diamond dataset along with multimedia references to your local Solr instance:
   ```sh
   python solr_update.py
   ```

6. **Run the Application:**

   ```sh
   python app.py
   ```
   Gemma v2 will be available at:  
   🔗 `http://127.0.0.1:5500/`

---

## 📝 Usage Instructions

1. **Launch the Web Interface:**  
   Open your browser and navigate to the running URL.

2. **Interact with the Chatbot:**  
   Ask questions such as "Show me a 1 carat round diamond" and receive personalized recommendations complete with multimedia details.

3. **View Diamond Details:**  
   Click on diamond cards to view an enhanced modal displaying images, looping videos, and certificate PDFs.

---

## 🤖 How It Works

- **Local Solr Integration:**  
  Gemma v2 uses a local Solr core (`diamond_core`) for efficient indexing and retrieval of diamond records.

- **Advanced Data Processing:**  
  Diamond data is processed and enriched with multimedia links, and vector embeddings are updated to work with Solr’s search capabilities.

- **AI-Powered Insights:**  
  Leverages Groq AI for generating expert recommendations based on user queries and diamond attributes.

- **Responsive Design:**  
  Updated HTML, CSS, and JavaScript ensure a seamless experience across devices.

---

## ⚡ Key Technologies Used

- **Flask:** Python web framework powering the application.
- **Apache Solr:** Local Solr core for high-performance diamond data retrieval.
- **FAISS & SentenceTransformer:** For advanced similarity search and NLP-based query processing.
- **Groq API:** For natural language processing and expert analysis.
- **Multimedia Integration:** Support for images, videos, and PDF certificates in diamond details.

---

## 📂 Project Structure (v2 Branch)

```
Gemma/
│── app.py                    # Flask application entry point
│── chatbot.py                # Enhanced chatbot logic and recommendation engine
│── solr_update.py            # Script to update Solr with diamond data and multimedia
│── templates/
│   ├── index.html            # Web-based chat interface with multimedia support
│── static/
│   ├── script.js             # Frontend JavaScript with multimedia modal handling
│   ├── style.css             # Updated CSS with responsive design
│── diamonds.csv              # Raw diamond dataset
│── diamond_dataframe.csv     # Processed diamond data with multimedia references
│── requirements.txt          # Required dependencies
│── README.md                 # This README file for v2 branch
│── .gitignore                # Git ignored files
```

---

## ℹ️ Important Notice

**Gemma v2** is intended for advanced users with access to a local Solr setup and proper multimedia resources. If you are looking for a quick-start clone-and-run version, please refer to the main branch.

---
