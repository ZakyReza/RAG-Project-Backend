from langchain.memory import ConversationBufferWindowMemory
from typing import Dict
import asyncio


class AsyncMemoryManager:
    def __init__(self):
        self.memories: Dict[int, ConversationBufferWindowMemory] = {}
        self._lock = asyncio.Lock()  # async-safe lock

    async def get_memory(self, conversation_id: int, k: int = 5):
        async with self._lock:
            if conversation_id not in self.memories:
                self.memories[conversation_id] = ConversationBufferWindowMemory(
                    k=k,
                    return_messages=True
                )
            return self.memories[conversation_id]

    async def clear_memory(self, conversation_id: int):
        async with self._lock:
            self.memories.pop(conversation_id, None)

    async def clear_all(self):
        async with self._lock:
            self.memories.clear()