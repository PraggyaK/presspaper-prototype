PressPaper – Working Prototype

This prototype demonstrates an end-to-end pipeline for verified government information.

What it does:
- Pulls live updates from official GOV.UK publication feeds
- Extracts original government text
- Generates neutral AI summaries
- Stores all content in a local database
- Displays a feed and article view via a web interface

How to run (for demo):
1. Install Python 3.10+
2. Install dependencies:
   pip install streamlit requests beautifulsoup4 openai python-dotenv
3. Run the pipeline:
   python pipeline.py
4. Launch the UI:
   python -m streamlit run app.py

Notes:
- Data is live and sourced directly from GOV.UK
- AI summaries are shown alongside original text for transparency
