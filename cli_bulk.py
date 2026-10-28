#!/usr/bin/env python3
"""
Bulk Certificate Generator CLI
Generates certificates for multiple participants from CSV.
Features: progress tracking, resume capability, ZIP output with manifest.
"""

import csv
import io
import json
import os
import sys
import argparse
import zipfile
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from main import (
    load_config, load_participants, fill_certificate_pdf, ordinal,
    DATA_DIR, TEMPLATES_DIR
)

CONFIG = load_config()
EVENT_SHORT = CONFIG.get("event_short_name", "Event").replace(" ", "_").replace("'", "")

# ── Checkpoint file for resume capability ─────────────────────────────────────
CHECKPOINT_FILE = DATA_DIR / ".bulk_checkpoint.json"

def load_checkpoint() -> Dict:
    """Load checkpoint data for resume."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"completed": [], "failed": [], "total": 0, "started_at": None}

def save_checkpoint(checkpoint: Dict):
    """Save checkpoint data."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)

def clear_checkpoint():
    """Clear checkpoint file."""
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

def generate_single_certificate(name: str, team_name: str, position: int, cert_type: str) -> io.BytesIO:
    """Generate a single certificate PDF."""
    position_label = ordinal(position) if position <= 3 else None
    return fill_certificate_pdf(name, team_name, position_label, cert_type)

def generate_certificates_bulk(
    csv_path: Path,
    output_dir: Path,
    max_workers: int = 4,
    skip_existing: bool = True,
    resume: bool = False
) -> Dict:
    """
    Generate certificates in bulk from CSV.
    Returns dict with stats.
    """
    # Load participants from CSV
    participants = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get("email", "").strip().lower()
            if not email:
                continue
            pos_str = row.get("team_place", "").strip()
            try:
                position = int(float(pos_str)) if pos_str else 99
            except ValueError:
                position = 99
            
            participants.append({
                "email": email,
                "name": row.get("certificate_name", "").strip() or row.get("member_name", "").strip(),
                "team_name": row.get("team_name", "").strip(),
                "position": position,
                "cert_type": "winner" if position <= 3 else "participation",
            })
    
    total = len(participants)
    if total == 0:
        print("❌ No valid participants found in CSV")
        return {"success": 0, "failed": 0, "skipped": 0, "total": 0}
    
    print(f"📋 Found {total} participants to process")
    
    # Load checkpoint if resuming
    checkpoint = {"completed": [], "failed": [], "total": total, "started_at": datetime.now().isoformat()}
    if resume:
        checkpoint = load_checkpoint()
        if checkpoint.get("total") != total:
            print("⚠️  CSV changed since last run, starting fresh")
            checkpoint = {"completed": [], "failed": [], "total": total, "started_at": datetime.now().isoformat()}
        else:
            completed = set(checkpoint.get("completed", []))
            failed = set(checkpoint.get("failed", []))
            print(f"📂 Resuming: {len(completed)} completed, {len(failed)} failed")
    
    # Prepare output
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    completed = set(checkpoint.get("completed", []))
    failed = set(checkpoint.get("failed", []))
    
    start_time = time.time()
    
    for idx, participant in enumerate(participants, 1):
        email = participant["email"]
        
        # Skip if already completed
        if email in completed and skip_existing:
            skipped_count += 1
            progress = (idx / total) * 100
            print(f"  [{idx}/{total}] ⏭️  Skipping {participant['name']} ({email}) - already done ({progress:.1f}%)")
            continue
        
        # Skip if failed before and we're not retrying
        if email in failed and not resume:
            skipped_count += 1
            print(f"  [{idx}/{total}] ⏭️  Skipping {participant['name']} ({email}) - previously failed")
            continue
        
        try:
            # Generate certificate
            pdf_buffer = generate_single_certificate(
                participant["name"],
                participant["team_name"],
                participant["position"],
                participant["cert_type"]
            )
            
            # Save PDF
            safe_name = "".join(c if c.isalnum() else "_" for c in participant["name"])
            filename = f"{EVENT_SHORT}_{safe_name}_certificate.pdf"
            pdf_path = output_dir / filename
            
            pdf_buffer.seek(0)
            with open(pdf_path, "wb") as f:
                f.write(pdf_buffer.read())
            
            # Add to manifest
            manifest.append({
                "email": email,
                "name": participant["name"],
                "team_name": participant["team_name"],
                "position": participant["position"],
                "cert_type": participant["cert_type"],
                "filename": filename,
                "generated_at": datetime.now().isoformat(),
            })
            
            completed.add(email)
            success_count += 1
            
            # Progress
            progress = (idx / total) * 100
            elapsed = time.time() - start_time
            eta = (elapsed / idx) * (total - idx) if idx > 0 else 0
            print(f"  [{idx}/{total}] ✅ {participant['name']} ({email}) - {progress:.1f}% - ETA: {eta:.0f}s")
            
            # Save checkpoint every 10 certificates
            if idx % 10 == 0:
                checkpoint["completed"] = list(completed)
                checkpoint["failed"] = list(failed)
                save_checkpoint(checkpoint)
                
        except Exception as e:
            failed.add(email)
            failed_count += 1
            print(f"  [{idx}/{total}] ❌ {participant['name']} ({email}) - Error: {e}")
            
            # Save checkpoint on failure
            checkpoint["completed"] = list(completed)
            checkpoint["failed"] = list(failed)
            save_checkpoint(checkpoint)
    
    # Save manifest
    manifest_path = output_dir / "manifest.csv"
    if manifest:
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["email", "name", "team_name", "position", "cert_type", "filename", "generated_at"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(manifest)
    
    # Final checkpoint
    checkpoint["completed"] = list(completed)
    checkpoint["failed"] = list(failed)
    save_checkpoint(checkpoint)
    
    elapsed = time.time() - start_time
    print(f"\n✨ Bulk generation complete!")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print(f"   ⏱️  Time: {elapsed:.1f}s")
    print(f"   📁 Output: {output_dir}")
    print(f"   📋 Manifest: {manifest_path}")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": total,
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
    }

def create_zip_archive(output_dir: Path, zip_path: Path) -> Path:
    """Create ZIP archive of generated certificates."""
    print(f"📦 Creating ZIP archive: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(output_dir)
                zf.write(file_path, arcname)
    print(f"✅ ZIP created: {zip_path}")
    return zip_path

def main():
    parser = argparse.ArgumentParser(
        description="Bulk Certificate Generator for WEC CTF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate certificates from CSV
  python cli_bulk.py --csv data/participants.csv --output ./certs/
  
  # With ZIP output
  python cli_bulk.py --csv data/participants.csv --output ./certs/ --zip
  
  # Resume interrupted generation
  python cli_bulk.py --csv data/participants.csv --output ./certs/ --resume
  
  # Clear checkpoint and start fresh
  python cli_bulk.py --csv data/participants.csv --output ./certs/ --no-resume
        """
    )
    
    parser.add_argument(
        "--csv", 
        required=True, 
        type=Path,
        help="Path to participants CSV file"
    )
    parser.add_argument(
        "--output", 
        required=True, 
        type=Path,
        help="Output directory for certificates"
    )
    parser.add_argument(
        "--zip", 
        action="store_true",
        help="Create ZIP archive of all certificates"
    )
    parser.add_argument(
        "--zip-path", 
        type=Path,
        help="Custom ZIP output path (default: output_dir.zip)"
    )
    parser.add_argument(
        "--max-workers", 
        type=int, 
        default=4,
        help="Maximum concurrent workers (default: 4)"
    )
    parser.add_argument(
        "--resume", 
        action="store_true",
        help="Resume from checkpoint"
    )
    parser.add_argument(
        "--no-resume", 
        action="store_true",
        help="Clear checkpoint and start fresh"
    )
    parser.add_argument(
        "--skip-existing", 
        action="store_true",
        default=True,
        help="Skip already generated certificates (default: True)"
    )
    parser.add_argument(
        "--no-skip", 
        action="store_true",
        help="Regenerate all certificates"
    )
    
    args = parser.parse_args()
    
    # Handle resume flags
    if args.no_resume:
        clear_checkpoint()
        resume = False
    else:
        resume = args.resume
    
    skip_existing = args.skip_existing and not args.no_skip
    
    # Validate CSV
    if not args.csv.exists():
        print(f"❌ CSV file not found: {args.csv}")
        sys.exit(1)
    
    # Run bulk generation
    result = generate_certificates_bulk(
        csv_path=args.csv,
        output_dir=args.output,
        max_workers=args.max_workers,
        skip_existing=skip_existing,
        resume=resume
    )
    
    # Create ZIP if requested
    if args.zip:
        zip_path = args.zip_path or Path(f"{args.output}.zip")
        create_zip_archive(args.output, zip_path)
    
    # Exit with error code if any failures
    if result["failed"] > 0:
        print(f"\n⚠️  {result['failed']} certificates failed to generate")
        sys.exit(1)
    else:
        print(f"\n🎉 All {result['success']} certificates generated successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
