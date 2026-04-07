"""
Ingest lab materials from a GitHub repository.

Clones a repo, finds all markdown files, concatenates them into
a single lab document, and inserts it with an embedding.

Usage:
    cd backend
    python3 -m seed.ingest_github <github_url> [--lab-number 1] [--lab-title "My Lab"]

Examples:
    python3 -m seed.ingest_github https://github.com/user/lab-1 --lab-number 1
    python3 -m seed.ingest_github https://github.com/user/lab-2 --lab-number 2 --lab-title "Architecture Lab"
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import Session, create_engine, select

from app.config import settings
from app.models.models import LabDoc
from app.services.embeddings import EmbeddingService
from app.services.chunker import chunk_lab_content


def clone_and_ingest(repo_url: str, lab_number: int | None = None, lab_title: str | None = None):
    """Clone a GitHub repo and ingest all markdown files as a single lab document."""
    engine = create_engine(settings.sync_database_url)
    svc = EmbeddingService()

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"📦 Cloning {repo_url}...")
        clone_cmd = ["git", "clone", "--depth", "1"]
        clone_cmd += [repo_url, tmpdir]

        result = subprocess.run(clone_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Clone failed: {result.stderr}")
            return

        # Find all .md files
        repo_path = Path(tmpdir)
        md_files = sorted(repo_path.rglob("*.md"))

        # Filter out common non-lab files
        skip_patterns = [
            ".git/", "node_modules/", "__pycache__/", ".venv/",
            "LICENSE", "CONTRIBUTING", "CHANGELOG", "CODE_OF_CONDUCT",
        ]

        relevant_files = []
        for md_file in md_files:
            rel_path = md_file.relative_to(repo_path)
            if any(skip in str(rel_path) for skip in skip_patterns):
                continue
            if len(md_file.read_text().strip()) < 50:
                continue
            relevant_files.append(md_file)

        if not relevant_files:
            print("❌ No suitable markdown files found.")
            return

        # Concatenate all files into a single document
        combined_content = ""
        for md_file in relevant_files:
            content = md_file.read_text()
            rel_path = md_file.relative_to(repo_path)
            combined_content += f"\n\n---\n\n# 📄 {rel_path}\n\n{content}"

        combined_content = combined_content.strip()

        # Determine lab number
        if lab_number is None:
            # Try to extract from repo name or filename
            repo_name = repo_url.rstrip("/").split("/")[-1]
            num_match = re.search(r"lab[-_]?(\d+)", repo_name, re.IGNORECASE)
            lab_number = int(num_match.group(1)) if num_match else 0

        # Determine lab title
        if lab_title is None:
            # Try first heading or repo name
            title_match = re.match(r"^#\s+(.+)", combined_content)
            if title_match:
                lab_title = title_match.group(1).strip()
            else:
                repo_name = repo_url.rstrip("/").split("/")[-1]
                lab_title = repo_name.replace("-", " ").replace("_", " ").title()

        final_title = f"Lab {lab_number}: {lab_title}"

        print(f"📝 Combined {len(relevant_files)} files into one lab document:")
        for f in relevant_files:
            print(f"   - {f.relative_to(repo_path)}")

        # Chunk the combined content
        chunks = chunk_lab_content(combined_content, title=final_title)
        print(f"   📦 Split into {len(chunks)} chunks (sizes: {[len(c) for c in chunks]})")

        with Session(engine) as session:
            # Check for duplicate by lab_number and remove old chunks
            existing = session.exec(select(LabDoc).where(LabDoc.lab_number == lab_number)).all()
            if existing:
                print(f"\n⚠️  Lab {lab_number} already exists ({len(existing)} chunk(s)): {existing[0].title}")
                overwrite = input("Overwrite? (y/N): ").strip().lower()
                if overwrite != "y":
                    print("⏭️  Skipping.")
                    return
                for old_doc in existing:
                    session.delete(old_doc)
                session.flush()

            print(f"\n✨ Generating embeddings for {len(chunks)} chunk(s)...")

            embeddings = svc.embed_many(chunks)

            for chunk_idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
                doc = LabDoc(
                    lab_number=lab_number,
                    title=final_title,
                    content=chunk_content,
                    embedding=embedding,
                    chunk_index=chunk_idx,
                    num_chunks=len(chunks),
                )
                session.add(doc)

            session.commit()

            print(f"✅ Successfully ingested!")
            print(f"   Title: {final_title}")
            print(f"   Content size: {len(combined_content):,} chars")
            print(f"   Chunks created: {len(chunks)}")
            print(f"   Files included: {len(relevant_files)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest lab materials from GitHub")
    parser.add_argument("repo_url", help="GitHub repository URL")
    parser.add_argument("--lab-number", type=int, default=None, help="Lab number (auto-detected from repo name if omitted)")
    parser.add_argument("--lab-title", default=None, help="Lab title (auto-detected from first heading if omitted)")

    args = parser.parse_args()
    clone_and_ingest(args.repo_url, args.lab_number, args.lab_title)
