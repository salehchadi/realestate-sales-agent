"""
Parser module for Real Estate AI Sales Agent.

Uses Gemini VLM (Vision-Language Model) to extract structured data from
real estate PDF brochures (payment plans, floorplans) into Pydantic models.
"""

import os
import glob
import time
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

from src import database

# Load environment variables
load_dotenv()


# ---------------------------------------------------------------------------
# Pydantic Data Contract
# ---------------------------------------------------------------------------

class UnitOffer(BaseModel):
    """Strict schema for a single real estate unit offer extracted from a PDF."""

    project_name: str = Field(
        description="Exact compound/project name, e.g. 'Hacienda Ras El Hekma'"
    )
    developer_name: str = Field(
        description="Developer company name, e.g. 'Palm Hills Development'"
    )
    location: str = Field(
        description="Main geographic location in English, e.g. 'North Coast', '6th of October City'"
    )
    unit_type: str = Field(
        description="Type of unit: 'Villa', 'Chalet', or 'Apartment'"
    )
    bedrooms: str = Field(
        description="Bedroom configuration, e.g. '1B', '2B', '3B + Nanny'"
    )
    unit_area_sqm: float = Field(
        default=0,
        description="Smallest unit area in square meters. 0 if not shown in the document."
    )
    starting_price: float = Field(
        default=0,
        description="Absolute minimum total price in EGP. 0 if not shown."
    )
    down_payment_pct: float = Field(
        default=0,
        description="Down payment percentage, e.g. 10.0 for 10%"
    )
    installment_years: int = Field(
        default=0,
        description="Number of installment years for the payment plan"
    )
    delivery_year: int = Field(
        default=0,
        description="Expected delivery year (4-digit). Use current year if 'Ready to Move'."
    )
    payment_plan_summary: str = Field(
        default="",
        description="One-line summary of the payment plan, e.g. '10% down payment, 8 years installments'"
    )


# ---------------------------------------------------------------------------
# VLM Extraction Pipeline
# ---------------------------------------------------------------------------

PARSER_SYSTEM_PROMPT = """
You are a meticulous Real Estate Data Engineer specializing in Egyptian 
real estate. Your job is to extract structured financial data from payment 
plan brochure PDFs.

CRITICAL EXTRACTION RULES:
1. **project_name**: The FULL compound/project name (e.g., "Hacienda Ras El Hekma", 
   "Badya", "Palm Parks"). This is NOT the developer name. Look for the main 
   title/branding on the brochure. Common abbreviations: HRH = Hacienda Ras El Hekma,
   VDLC = Village D'El Comte, PHNC = Palm Hills New Cairo.
2. **developer_name**: The company that built it (e.g., "Palm Hills Development", 
   "Emaar Misr"). Usually shown in a logo or footer.
3. **location**: The geographic area in Egypt. Common locations:
   - North Coast (Sahel) for beach/resort projects
   - New Cairo / 6th of October City / Sheikh Zayed for urban projects
   - Ain Sokhna for Red Sea projects
4. **unit_type**: Must be one of: "Villa", "Chalet", "Apartment", "Townhouse", 
   "Twin House", "Penthouse", "Duplex". Infer from context, layout images, 
   or the filename hint.
5. **bedrooms**: e.g., "1B", "2B", "3B", "3B + Nanny", "4B". 
   Look for bedroom count in the document or filename hint.
6. **starting_price**: The LOWEST total unit price in EGP shown in any table.
7. **down_payment_pct**: The down payment percentage.
8. **installment_years**: Number of years for installment payments.
9. **delivery_year**: Expected delivery year (4-digit). Use 2026 if "Ready".
10. **payment_plan_summary**: One concise line, e.g., "10% down, 8 years installments".
11. **unit_area_sqm**: Smallest unit area in sqm. 0 if not shown.

IMPORTANT: The filename hint provided contains encoded information about the 
project, bedrooms, and payment duration. Use it to supplement what you see in 
the PDF if the PDF alone is ambiguous.

Translate all Arabic text to English. Never leave fields empty if you can infer them.
"""


def _get_client() -> genai.Client:
    """Initialize and return a Gemini API client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("❌ GEMINI_API_KEY not found in .env file!")
    return genai.Client(api_key=api_key)


def parse_pdf(pdf_path: str) -> UnitOffer:
    """
    Parse a single PDF brochure and extract structured data using Gemini VLM.
    Includes automatic retry with backoff for rate limit (429) errors.
    
    Args:
        pdf_path: Path to the PDF file.
        
    Returns:
        A UnitOffer Pydantic model with the extracted data.
    """
    import re

    client = _get_client()
    max_retries = 3

    print(f"  📤 Uploading: {os.path.basename(pdf_path)}...")
    uploaded_file = client.files.upload(file=pdf_path)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  🤖 Extracting data with Gemini VLM... (attempt {attempt}/{max_retries})")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded_file.uri,
                                mime_type=uploaded_file.mime_type,
                            ),
                            types.Part.from_text(
                                text=f"Extract all structured data from this real estate payment plan brochure. "
                                     f"Filename hint: {os.path.basename(pdf_path)}"
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=PARSER_SYSTEM_PROMPT,
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=UnitOffer,
                ),
            )

            # Parse the structured response
            offer = response.parsed
            print(f"  ✅ Extracted: {offer.project_name} — {offer.unit_type} {offer.bedrooms}")
            return offer

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                # Extract retry delay from error message if available
                retry_match = re.search(r'retry in (\d+(?:\.\d+)?)s', error_str, re.IGNORECASE)
                if retry_match:
                    wait_time = int(float(retry_match.group(1))) + 5  # Add 5s buffer
                else:
                    wait_time = 15 * (2 ** (attempt - 1))  # Exponential: 15, 30, 60

                if attempt < max_retries:
                    print(f"  ⏳ Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Rate limit exceeded after {max_retries} retries for {os.path.basename(pdf_path)}"
                    ) from e
            else:
                raise  # Non-rate-limit errors are raised immediately


def parse_pdf_to_db(pdf_path: str) -> None:
    """Parse a single PDF and save the result to the database."""
    offer = parse_pdf(pdf_path)
    database.upsert_unit(offer)


def parse_all_pdfs(directory: str) -> None:
    """
    Parse all PDF files in a directory and save results to the database.
    
    Args:
        directory: Path to the directory containing PDF files.
    """
    pdf_files = glob.glob(os.path.join(directory, "**", "*.pdf"), recursive=True)

    if not pdf_files:
        print(f"⚠️  No PDF files found in: {directory}")
        return

    print(f"📂 Found {len(pdf_files)} PDF(s) in: {directory}")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {os.path.basename(pdf_path)}")
        try:
            parse_pdf_to_db(pdf_path)
            success_count += 1
        except Exception as e:
            print(f"  ❌ Error processing {os.path.basename(pdf_path)}: {e}")
            fail_count += 1

        # Longer delay between PDFs to respect free tier rate limits
        if i < len(pdf_files):
            time.sleep(10)

    print("\n" + "=" * 60)
    print(f"✅ Done! {success_count} succeeded, {fail_count} failed out of {len(pdf_files)} PDFs.")

