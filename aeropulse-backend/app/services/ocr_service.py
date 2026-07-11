"""
Real OCR extraction using Tesseract (via pytesseract).

Requires the `tesseract-ocr` system package (already installed in the
provided Dockerfile). Extracts a likely flight number and PNR from a
boarding-pass / e-ticket photo so it can be matched against
flight_registry — this is step 3-4 of the ingestion pipeline in the
architecture doc.
"""
import io
import re
import logging
from PIL import Image
import pytesseract

logger = logging.getLogger("aeropulse.ocr")

# Airline flight numbers: 2 letters + 1-4 digits (e.g. AA204, DL1823)
FLIGHT_NUMBER_RE = re.compile(r"\b([A-Z]{2}\d{2,4})\b")
# PNR / booking reference: 6-char code that mixes letters and digits
# (avoids false-matching plain English words like "FLIGHT")
PNR_RE = re.compile(r"\b(?=[A-Z0-9]{6}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])([A-Z0-9]{6})\b")


def extract_text(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "L":
        image = image.convert("L")  # grayscale improves OCR accuracy
    return pytesseract.image_to_string(image)


def extract_flight_and_pnr(image_bytes: bytes) -> dict:
    try:
        raw_text = extract_text(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR failed: %s", exc)
        return {"flight_number": None, "pnr": None, "raw_text": "", "confidence": 0.0}

    upper = raw_text.upper()
    flight_match = FLIGHT_NUMBER_RE.search(upper)
    pnr_match = PNR_RE.search(upper)

    # crude confidence heuristic: did we find a flight-number-shaped token at all
    confidence = 0.85 if flight_match else 0.15

    return {
        "flight_number": flight_match.group(1) if flight_match else None,
        "pnr": pnr_match.group(1) if pnr_match else None,
        "raw_text": raw_text,
        "confidence": confidence,
    }
