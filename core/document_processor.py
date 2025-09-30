import asyncio
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader, UnstructuredFileLoader
from config import settings

class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size, 
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            is_separator_regex=False
        )
    
    async def process_document(self, file_path: str, file_type: str, metadata: dict = None) -> dict:
        """Process a document and return chunks"""
        if metadata is None:
            metadata = {}
            
        try:
            # Select loader based on file type
            loader = self._get_loader(file_path, file_type)
            
            # Load document
            documents = await asyncio.to_thread(loader.load)
            
            # Add metadata
            for doc in documents:
                doc.metadata.update(metadata)
            
            # Split into chunks
            chunks = self.text_splitter.split_documents(documents)
            
            # Calculate approximate tokens
            total_tokens = sum(len(chunk.page_content.split()) for chunk in chunks)
            
            return {
                "success": True,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "total_tokens": total_tokens,
                "message": f"Successfully processed {len(chunks)} chunks"
            }
            
        except Exception as e:
            logging.exception("Error while processing document")
            return {
                "success": False,
                "error": str(e),
                "chunks": [],
                "chunk_count": 0,
                "total_tokens": 0
            }
    
    def _get_loader(self, file_path: str, file_type: str):
        """Get appropriate document loader based on file type"""
        if file_type == "application/pdf":
            return PyPDFLoader(file_path)
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            return Docx2txtLoader(file_path)
        elif file_type == "text/plain":
            return TextLoader(file_path, encoding='utf-8')
        else:
            return UnstructuredFileLoader(file_path)