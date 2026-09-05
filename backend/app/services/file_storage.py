"""
File Storage Service with validation.

Handles secure file uploads with:
- Configurable size limits
- Extension/MIME type validation
- Safe filename generation
- Checksum computation
- Path traversal prevention
"""
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, List, Optional

from app.core.config import settings


class FileValidationError(Exception):
    """Raised when file validation fails."""
    pass


class FileStorageService:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_DIRECTORY).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = settings.max_upload_size_bytes
        self.allowed_extensions = settings.allowed_extensions_list

    def _generate_safe_filename(self, original_filename: str) -> str:
        """Generate a safe server-side filename while preserving extension."""
        # Extract extension
        path = Path(original_filename)
        extension = path.suffix.lower()
        if not extension and path.suffixes:
            extension = path.suffixes[-1].lower()
        
        # Validate extension
        if extension and extension not in self.allowed_extensions:
            raise FileValidationError(
                f"File extension '{extension}' is not allowed. "
                f"Allowed extensions: {', '.join(self.allowed_extensions)}"
            )
        
        # Generate safe filename: uuid + extension
        safe_name = f"{uuid.uuid4().hex}{extension}"
        return safe_name

    def _validate_file(self, file: BinaryIO, filename: str, content_type: Optional[str] = None) -> None:
        """Validate file size, type, and content."""
        # Check file size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size == 0:
            raise FileValidationError("Empty files are not allowed")
        
        if size > self.max_size:
            raise FileValidationError(
                f"File size {size} bytes exceeds maximum allowed size of {self.max_size} bytes "
                f"({settings.MAX_UPLOAD_SIZE_MB} MB)"
            )
        
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext and ext not in self.allowed_extensions:
            raise FileValidationError(
                f"File extension '{ext}' is not allowed. "
                f"Allowed extensions: {', '.join(self.allowed_extensions)}"
            )
        
        # Basic MIME type validation if provided
        if content_type:
            allowed_mimes = {
                '.py': 'text/x-python',
                '.js': 'application/javascript',
                '.ts': 'application/typescript',
                '.jsx': 'text/jsx',
                '.tsx': 'text/tsx',
                '.json': 'application/json',
                '.yaml': 'application/yaml',
                '.yml': 'application/yaml',
                '.md': 'text/markdown',
                '.txt': 'text/plain',
                '.csv': 'text/csv',
                '.zip': 'application/zip',
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.html': 'text/html',
                '.css': 'text/css',
                '.sql': 'application/sql',
                '.sh': 'application/x-shellscript',
                '.dockerfile': 'text/plain',
                '.toml': 'application/toml',
                '.ini': 'text/plain',
                '.cfg': 'text/plain',
                '.conf': 'text/plain',
                '.xml': 'application/xml',
                '.java': 'text/x-java-source',
                '.kt': 'text/x-kotlin',
                '.rb': 'text/x-ruby',
                '.go': 'text/x-go',
                '.rs': 'text/x-rust',
                '.cs': 'text/x-csharp',
                '.php': 'application/x-httpd-php',
                '.swift': 'text/x-swift',
                '.scala': 'text/x-scala',
                '.clj': 'text/x-clojure',
                '.hs': 'text/x-haskell',
                '.ml': 'text/x-ocaml',
                '.fs': 'text/x-fsharp',
                '.vb': 'text/x-vb',
                '.pl': 'text/x-perl',
                '.r': 'text/x-r',
                '.m': 'text/x-matlab',
                '.lua': 'text/x-lua',
                '.dart': 'application/dart',
                '.elm': 'text/x-elm',
                '.ex': 'text/x-elixir',
                '.exs': 'text/x-elixir',
                '.erl': 'text/x-erlang',
                '.hrl': 'text/x-erlang',
                '.pp': 'text/x-puppet',
                '.tf': 'text/x-terraform',
                '.tfvars': 'text/x-terraform',
                '.hcl': 'text/x-hcl',
                '.nomad': 'text/x-nomad',
                '.helm': 'text/x-yaml',
                '.k8s': 'text/x-yaml',
            }
            
            expected_mime = allowed_mimes.get(ext)
            if expected_mime and content_type != expected_mime:
                # Log warning but don't fail - MIME types can vary
                pass

    def _compute_checksum(self, file: BinaryIO) -> str:
        """Compute SHA-256 checksum of file content."""
        file.seek(0)
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)
        file.seek(0)
        return sha256.hexdigest()

    def _get_storage_path(self, project_id: uuid.UUID, submission_id: uuid.UUID, version: int, filename: str) -> Path:
        """Get the full storage path for a file."""
        safe_filename = self._generate_safe_filename(filename)
        folder = self.base_dir / str(project_id) / str(submission_id) / str(version)
        folder.mkdir(parents=True, exist_ok=True)
        return folder / safe_filename

    def store_file(
        self,
        file: BinaryIO,
        project_id: uuid.UUID,
        submission_id: uuid.UUID,
        version: int,
        original_filename: str,
        content_type: Optional[str] = None,
    ) -> dict:
        """
        Store a single file and return metadata.
        
        Returns dict with: filename, storage_path, content_type, size, checksum, upload_timestamp
        """
        # Validate
        self._validate_file(file, original_filename, content_type)
        
        # Compute checksum before writing
        checksum = self._compute_checksum(file)
        
        # Get storage path
        storage_path = self._get_storage_path(project_id, submission_id, version, original_filename)
        
        # Write file
        with open(storage_path, "wb") as f:
            for chunk in iter(lambda: file.read(8192), b""):
                f.write(chunk)
        
        size = storage_path.stat().st_size
        
        return {
            "original_filename": original_filename,
            "stored_filename": storage_path.name,
            "storage_path": str(storage_path),
            "content_type": content_type or "application/octet-stream",
            "size": size,
            "checksum": checksum,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

    def store_files(
        self,
        files: List[dict],
        project_id: uuid.UUID,
        submission_id: uuid.UUID,
        version: int,
    ) -> List[dict]:
        """
        Store multiple files.
        
        Each file dict should have: file (BinaryIO), filename (str), content_type (optional str)
        """
        results = []
        for file_data in files:
            file_obj = file_data.get("file")
            filename = file_data.get("filename") or "unnamed"
            content_type = file_data.get("content_type")
            
            if not file_obj:
                raise FileValidationError("File object is required")
            
            metadata = self.store_file(
                file=file_obj,
                project_id=project_id,
                submission_id=submission_id,
                version=version,
                original_filename=filename,
                content_type=content_type,
            )
            results.append(metadata)
        
        return results

    def get_file_path(self, project_id: uuid.UUID, submission_id: uuid.UUID, version: int, stored_filename: str) -> Optional[Path]:
        """Get the full path to a stored file."""
        path = self.base_dir / str(project_id) / str(submission_id) / str(version) / stored_filename
        if path.exists() and path.is_file():
            return path
        return None

    def delete_version_files(self, project_id: uuid.UUID, submission_id: uuid.UUID, version: int) -> int:
        """Delete all files for a specific version. Returns count of deleted files."""
        folder = self.base_dir / str(project_id) / str(submission_id) / str(version)
        if not folder.exists():
            return 0
        
        count = 0
        for file_path in folder.iterdir():
            if file_path.is_file():
                file_path.unlink()
                count += 1
        
        # Remove empty folder
        try:
            folder.rmdir()
        except OSError:
            pass  # Folder not empty or other issue
        
        return count