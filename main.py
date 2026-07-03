"""
Main entry point for the Real Estate AI Sales Agent.

Usage:
    python main.py parse                 Parse ALL PDFs in data_samples/
    python main.py parse <file.pdf>      Parse a single PDF file
    python main.py chat                  Start the interactive sales agent
    python main.py web                   Start the Mos3ad web UI
"""

import sys
import os

# Fix Windows console encoding for emoji/unicode output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

# Load environment at startup
load_dotenv()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "parse":
        from src.parser import parse_pdf_to_db, parse_all_pdfs

        if len(sys.argv) >= 3:
            # Parse a specific file
            pdf_path = sys.argv[2]
            if not os.path.exists(pdf_path):
                print(f"❌ File not found: {pdf_path}")
                sys.exit(1)
            print(f"📄 Parsing single file: {pdf_path}")
            parse_pdf_to_db(pdf_path)
        else:
            # Parse all PDFs in data_samples/
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_samples")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
                print(f"📁 Created data_samples/ directory. Please add PDF files and run again.")
                sys.exit(1)
            parse_all_pdfs(data_dir)

    elif command == "chat":
        from src.agent import start_chat
        start_chat()

    elif command == "web":
        import uvicorn
        print("\n🏛️  Starting Mos3ad Elite Concierge Web UI...")
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
