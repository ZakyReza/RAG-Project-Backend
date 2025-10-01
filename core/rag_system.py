from langchain import hub
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from core.document_processor import DocumentProcessor
from core.memory_manager import AsyncMemoryManager
from config import settings
import asyncio
import mimetypes
import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

import os

logger = logging.getLogger(__name__)

class SimpleRAGSystem:
    def __init__(self):
        # Initialize embeddings based on config
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    
        # Initialize vector store
        self.vectorstore = Chroma(
            persist_directory=str(settings.chroma_persist_dir),
            embedding_function=self.embeddings,
            collection_name=settings.chroma_collection_name
        )
        
        # Initialize LLM
        self.llm = ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature
        )

        # Initialize components
        self.document_processor = DocumentProcessor()
        self.memory_manager = AsyncMemoryManager()
        
    def _get_default_prompt(self):
        """Get a default RAG prompt template WITHOUT history"""
        return ChatPromptTemplate.from_template(
            """You are a helpful assistant that answers questions based on the provided context.
            Use the following context to answer the question. If the answer is not in the context, 
            say "I don't have enough information in the provided context to answer that question."

            Context: {context}

            Question: {question}

            Answer:"""
        )
    
    def _get_rag_prompt_with_history(self):
        """Get RAG prompt template that includes chat history"""
        return ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that answers questions based on the provided context and conversation history.
            Use the following context to answer the question. If the answer is not in the context, 
            say "I don't have enough information in the provided context to answer that question."
            
            Consider the conversation history when formulating your response to maintain continuity.
            
            Context: {context}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
    
    async def get_rag_chain(self, conversation_id: int):
        """Create RAG chain with memory"""
        memory = await self.memory_manager.get_memory(conversation_id, k=5)
        
        try:
            if os.getenv("LANGCHAIN_API_KEY"):
                prompt = hub.pull("rlm/rag-prompt")
                logger.info("Using LangChain hub prompt")
            else:
                #Check if memory has chat history, not if memory==0
                if memory and hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
                    prompt = self._get_rag_prompt_with_history()
                    logger.info("Using local prompt with history")
                else:
                    prompt = self._get_default_prompt()
                    logger.info("Using local default prompt")
                    
        except Exception as e:
            logger.warning(f"Failed to pull prompt from hub: {e}")

            if memory and hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
                prompt = self._get_rag_prompt_with_history()
            else:
                prompt = self._get_default_prompt()
        
        # Create retriever
        retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": settings.retrieval_k}
        )

        def format_docs(docs):
            if not docs:
                return "No relevant documents found."
            return "\n\n".join([doc.page_content for doc in docs])
        
        # Build chain
        if memory and hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
            # Chain with memory
            chain = (
                {
                    "context": retriever | format_docs,
                    "chat_history": lambda x: memory.chat_memory.messages, 
                    "question": RunnablePassthrough()
                }
                | prompt
                | self.llm
                | StrOutputParser()
            )
        else:
            # Chain without memory
            chain = (
                {
                    "context": retriever | format_docs,
                    "question": RunnablePassthrough()
                }
                | prompt
                | self.llm
                | StrOutputParser()
            )
        
        return chain, memory
    
    async def chat(self, conversation_id: int, question: str):
        """Chat with memory and retrieval"""
        chain, memory = await self.get_rag_chain(conversation_id)
        
        # Save user message to memory
        if memory and hasattr(memory, 'chat_memory'):
            memory.chat_memory.add_user_message(question)
        
        # Get response
        response = await asyncio.to_thread(chain.invoke, question)
        
        # Save AI response to memory
        if memory and hasattr(memory, 'chat_memory'):
            memory.chat_memory.add_ai_message(response)
        
        return {
            "answer": response,
            "conversation_id": conversation_id
        }
    
    def _detect_file_type(self, file_path: str) -> str:
        """Detect file type using mimetypes"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "text/plain"
    
    async def add_documents(self, file_paths: list, metadata: dict = None):
        """Add documents to vector store"""
        if metadata is None:
            metadata = {}
            
        all_chunks = []
        
        for file_path in file_paths:
            file_path_str = str(file_path)
            # Determine file type
            file_type = self._detect_file_type(file_path_str)
            
            result = await self.document_processor.process_document(
                file_path_str, 
                file_type, 
                metadata
            )
            
            if result["success"]:
                all_chunks.extend(result["chunks"])
            else:
                logger.error(f"Failed to process {file_path}: {result.get('error')}")
        
        if all_chunks:
            # Add to vectorstore in thread to avoid blocking
            try:
                await asyncio.to_thread(self.vectorstore.add_documents, all_chunks)
                logger.info(f"Successfully added {len(all_chunks)} chunks to vector store")
            except Exception as e:
                logger.error(f"Failed to add documents to vector store: {e}")
                raise e
            
        return len(all_chunks)  
    
    