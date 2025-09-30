import aiofiles
import magic
from pathlib import Path
from fastapi import UploadFile, HTTPException
import hashlib
import uuid
from typing import Dict, Any


class FileHandler:
    def __init__(self):
        self.temp_dir = Path("./temp_uploads")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Supported file types with their extensions
        self.allowed_types = {
            'application/pdf': 'pdf',
            'text/plain': 'txt',
            'text/markdown': 'md',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'application/msword': 'doc'
        }
        
        self.max_file_size = 50 * 1024 * 1024  # 50MB limit
    
    async def save_upload_file(self, file: UploadFile) -> Dict[str, Any]:
        """Save uploaded file and return file info with validation"""
        
        # Validate file type
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {list(self.allowed_types.values())}"
            )
        
        # Generate unique filename to avoid conflicts
        file_extension = self.allowed_types[file.content_type]
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = self.temp_dir / unique_filename
        
        try:
            # Read file content
            content = await file.read()
            
            # Validate file size
            if len(content) > self.max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {self.max_file_size // (1024*1024)}MB"
                )
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            # Verify file type using magic
            try:
                actual_mime_type = magic.from_file(str(file_path), mime=True)
                if actual_mime_type not in self.allowed_types:
                    print(f"Warning: Magic detected {actual_mime_type}, but using original {file.content_type}")
                    actual_mime_type = file.content_type
            except Exception as magic_error:
                print(f"Magic detection failed: {magic_error}, using content_type: {file.content_type}")
                actual_mime_type = file.content_type
            
            # Calculate file hash
            file_hash = hashlib.md5(content).hexdigest()
            
            file_info = {
                "path": str(file_path),
                "original_filename": file.filename,
                "mime_type": actual_mime_type,
                "size": len(content),
                "hash": file_hash,
                "extension": file_extension
            }
            
            return file_info
            
        except HTTPException:
            if file_path.exists():
                self.cleanup_file(str(file_path))
            raise
        except Exception as e:
            # Clean up on error
            if file_path.exists():
                self.cleanup_file(str(file_path))
            print(f"Full error details: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
    def cleanup_file(self, file_path: str) -> bool:
        """Safely remove a file"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                return True
        except Exception as e:
            print(f"Warning: Could not delete file {file_path}: {str(e)}")
        return False
    
    def validate_file_size(self, file_size: int) -> bool:
        """Check if file size is within limits"""
        return file_size <= self.max_file_size
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get information about a file"""
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        stat = path.stat()
        return {
            "path": str(file_path),
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "exists": True
        }
    
    async def process_multiple_files(self, files: list[UploadFile]) -> Dict[str, Any]:
        """Process multiple files concurrently"""
        import asyncio
        
        tasks = [self.save_upload_file(file) for file in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_files = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({
                    "filename": files[i].filename,
                    "error": str(result)
                })
            else:
                processed_files.append(result)
        
        return {
            "processed_files": processed_files,
            "errors": errors,
            "total_processed": len(processed_files)
        }
    
    def get_supported_formats(self) -> Dict[str, str]:
        """Return supported file formats"""
        return self.allowed_types.copy()

# Global instance
file_handler = FileHandler()

# Convenience functions for easy imports
async def save_upload_file(file: UploadFile) -> Dict[str, Any]:
    return await file_handler.save_upload_file(file)

def cleanup_file(file_path: str) -> bool:
    return file_handler.cleanup_file(file_path)

def get_supported_formats() -> Dict[str, str]:
    return file_handler.get_supported_formats()
