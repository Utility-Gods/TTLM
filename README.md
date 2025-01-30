# TTLM (Talk to Language Model)

A git-based knowledge assistant that uses RAG (Retrieval Augmented Generation) to help you query your codebase and documentation.

## Quick Start

1. Activate the virtual environment:
   ```bash
   source venv/bin/activate  # Unix/MacOS
   # or
   .\venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

4. Visit http://localhost:8000 in your browser


## License

MIT
