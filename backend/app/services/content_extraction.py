"""
File Content Extraction Service.

Extracts text content from various file formats for AI review.
Supports: .py, .java, .js, .ts, .jsx, .tsx, .html, .css, .json, .yaml, .yml, .sql, .md, .txt, .zip
"""
import io
import json
import zipfile
import yaml
from pathlib import Path
from typing import List, Optional

# Supported text-based extensions
TEXT_EXTENSIONS = {
    '.py', '.java', '.js', '.ts', '.jsx', '.tsx',
    '.html', '.css', '.json', '.yaml', '.yml', '.sql',
    '.md', '.txt', '.toml', '.ini', '.cfg', '.conf',
    '.xml', '.kt', '.rb', '.go', '.rs', '.cs', '.php',
    '.swift', '.scala', '.clj', '.hs', '.ml', '.fs',
    '.vb', '.pl', '.r', '.m', '.lua', '.dart', '.elm',
    '.ex', '.exs', '.erl', '.hrl', '.pp', '.tf', '.tfvars',
    '.hcl', '.nomad', '.helm', '.k8s', '.sh', '.dockerfile',
}

# Extensions that might need special handling
CODE_EXTENSIONS = TEXT_EXTENSIONS - {'.md', '.txt', '.json', '.yaml', '.yml', '.xml', '.toml', '.ini', '.cfg', '.conf'}


class ContentExtractionError(Exception):
    """Raised when content extraction fails."""
    pass


def is_text_file(filename: str) -> bool:
    """Check if file is a supported text-based file."""
    return Path(filename).suffix.lower() in TEXT_EXTENSIONS


def is_code_file(filename: str) -> bool:
    """Check if file is a code file (vs documentation/config)."""
    return Path(filename).suffix.lower() in CODE_EXTENSIONS


def extract_text_content(file_bytes: bytes, filename: str) -> str:
    """
    Extract text content from a file based on its extension.
    
    Args:
        file_bytes: Raw file bytes
        filename: Original filename (used for extension detection)
        
    Returns:
        Extracted text content
        
    Raises:
        ContentExtractionError: If extraction fails
    """
    ext = Path(filename).suffix.lower()
    
    if ext == '.json':
        return _extract_json(file_bytes, filename)
    elif ext in ('.yaml', '.yml'):
        return _extract_yaml(file_bytes, filename)
    elif ext == '.zip':
        return _extract_zip(file_bytes, filename)
    else:
        # All other text files: decode as UTF-8
        return _extract_plain_text(file_bytes, filename)


def _extract_plain_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from file bytes."""
    try:
        return file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        # Try latin-1 as fallback
        try:
            return file_bytes.decode('latin-1')
        except UnicodeDecodeError:
            raise ContentExtractionError(f"Cannot decode {filename} as text. File may be binary.")


def _extract_json(file_bytes: bytes, filename: str) -> str:
    """Extract and pretty-print JSON content."""
    text = _extract_plain_text(file_bytes, filename)
    try:
        data = json.loads(text)
        return json.dumps(data, indent=2)
    except json.JSONDecodeError as e:
        raise ContentExtractionError(f"Invalid JSON in {filename}: {e}")


def _extract_yaml(file_bytes: bytes, filename: str) -> str:
    """Extract and format YAML content."""
    text = _extract_plain_text(file_bytes, filename)
    try:
        data = yaml.safe_load(text)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    except yaml.YAMLError as e:
        raise ContentExtractionError(f"Invalid YAML in {filename}: {e}")


def _extract_zip(file_bytes: bytes, filename: str) -> str:
    """
    Safely extract contents from ZIP file.
    
    - Prevents path traversal
    - Ignores unsafe files (executables, hidden files, etc.)
    - Extracts only supported source files
    - Returns structured project context
    """
    results = []
    total_files = 0
    extracted_files = 0
    
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
            # Security: Check for zip bombs and path traversal
            for info in zf.infolist():
                total_files += 1
                
                # Skip directories
                if info.is_dir():
                    continue
                
                # Prevent path traversal
                safe_name = _sanitize_zip_path(info.filename)
                if safe_name is None:
                    results.append(f"[SKIPPED - Path traversal attempt]: {info.filename}")
                    continue
                
                # Skip unsafe files
                if _is_unsafe_file(safe_name):
                    results.append(f"[SKIPPED - Unsafe file type]: {safe_name}")
                    continue
                
                # Skip hidden files
                if any(part.startswith('.') for part in Path(safe_name).parts):
                    results.append(f"[SKIPPED - Hidden file]: {safe_name}")
                    continue
                
                # Skip very large files (> 1MB per file)
                if info.file_size > 1024 * 1024:
                    results.append(f"[SKIPPED - File too large ({info.file_size} bytes)]: {safe_name}")
                    continue
                
                # Only extract supported text files
                if not is_text_file(safe_name):
                    results.append(f"[SKIPPED - Unsupported format]: {safe_name}")
                    continue
                
                try:
                    content = zf.read(info.filename)
                    extracted_content = extract_text_content(content, safe_name)
                    results.append(f"=== FILE: {safe_name} ===\n{extracted_content}\n")
                    extracted_files += 1
                except ContentExtractionError as e:
                    results.append(f"[ERROR extracting {safe_name}]: {e}")
                except Exception as e:
                    results.append(f"[ERROR reading {safe_name}]: {e}")
            
            # Build summary
            summary = [
                f"ZIP Archive: {filename}",
                f"Total entries: {total_files}",
                f"Extracted files: {extracted_files}",
                f"Skipped: {total_files - extracted_files}",
                "",
                "CONTENTS:",
                ""
            ]
            
            return "\n".join(summary) + "\n".join(results)
            
    except zipfile.BadZipFile:
        raise ContentExtractionError(f"Invalid or corrupted ZIP file: {filename}")
    except Exception as e:
        raise ContentExtractionError(f"Failed to process ZIP file {filename}: {e}")


def _sanitize_zip_path(filename: str) -> Optional[str]:
    """
    Sanitize zip entry path to prevent path traversal.
    
    Returns None if path is unsafe.
    """
    # Normalize path
    try:
        path = Path(filename).resolve()
    except Exception:
        return None
    
    # Check for path traversal
    parts = Path(filename).parts
    if any(part in ('..', '') for part in parts):
        return None
    
    # Ensure it's a relative path (no absolute paths)
    if Path(filename).is_absolute():
        return None
    
    return filename


def _is_unsafe_file(filename: str) -> bool:
    """Check if file is potentially unsafe (executable, script, etc.)."""
    unsafe_extensions = {
        '.exe', '.dll', '.so', '.dylib', '.bin', '.o', '.obj',
        '.class', '.jar', '.war', '.ear', '.pyc', '.pyo',
        '.bat', '.cmd', '.ps1', '.vbs', '.scr', '.msi',
        '.app', '.deb', '.rpm', '.apk', '.ipa',
    }
    ext = Path(filename).suffix.lower()
    return ext in unsafe_extensions


def build_submission_context(stored_files: List[dict]) -> str:
    """
    Build a structured context string from submission files for AI review.
    
    Args:
        stored_files: List of file metadata from SubmissionVersion.files
        
    Returns:
        Formatted context string with all file contents
    """
    if not stored_files:
        return "No files submitted."
    
    parts = [
        f"SUBMISSION CONTEXT - {len(stored_files)} file(s)",
        "=" * 50,
        ""
    ]
    
    for file_meta in stored_files:
        original = file_meta.get('original_filename', 'unknown')
        stored = file_meta.get('stored_filename', '')
        size = file_meta.get('size', 0)
        content_type = file_meta.get('content_type', '')
        
        # Note: Actual content extraction would need the file from storage
        # This builds a reference context; actual content is extracted at review time
        parts.append(f"FILE: {original}")
        parts.append(f"  Stored as: {stored}")
        parts.append(f"  Size: {size} bytes")
        parts.append(f"  Type: {content_type}")
        parts.append("")
    
    parts.append("NOTE: Full file contents will be extracted and analyzed during review.")
    
    return "\n".join(parts)


def extract_all_submission_files(
    file_metas: List[dict], 
    storage_service
) -> str:
    """
    Extract content from all files in a submission.
    
    Args:
        file_metas: List of file metadata dicts with storage_path
        storage_service: FileStorageService instance to retrieve files
        
    Returns:
        Combined extracted content for AI review
    """
    parts = [
        f"SUBMISSION FILES ({len(file_metas)} total)",
        "=" * 60,
        ""
    ]
    
    for file_meta in file_metas:
        original = file_meta.get('original_filename', 'unknown')
        stored = file_meta.get('stored_filename', '')
        storage_path = file_meta.get('storage_path', '')
        
        if not storage_path:
            parts.append(f"[NO STORAGE PATH]: {original}")
            continue
        
        file_path = Path(storage_path)
        if not file_path.exists():
            parts.append(f"[FILE NOT FOUND]: {original} at {storage_path}")
            continue
        
        try:
            content = file_path.read_bytes()
            extracted = extract_text_content(content, original)
            
            parts.append(f"=== FILE: {original} ===")
            parts.append(f"Path: {storage_path}")
            parts.append(f"Size: {file_meta.get('size', 0)} bytes")
            parts.append(f"Checksum: {file_meta.get('checksum', 'N/A')}")
            parts.append("")
            parts.append(extracted)
            parts.append("")
            parts.append("-" * 40)
            parts.append("")
            
        except ContentExtractionError as e:
            parts.append(f"[EXTRACTION ERROR - {original}]: {e}")
            parts.append("")
            parts.append("-" * 40)
            parts.append("")
        except Exception as e:
            parts.append(f"[UNEXPECTED ERROR - {original}]: {e}")
            parts.append("")
            parts.append("-" * 40)
            parts.append("")
    
    return "\n".join(parts)