import redis.asyncio as redis
import json
import logging
from typing import Dict, Optional

class RedisQueue:
    def __init__(self, redis_client: redis.Redis, incoming_key: str, outgoing_key: str):
        self.redis_client = redis_client
        self.incoming_key = incoming_key
        self.outgoing_key = outgoing_key

    async def push_incoming(self, message: Dict):
        """Push a message to the incoming queue (from User to Bot)"""
        try:
            await self.redis_client.rpush(self.incoming_key, json.dumps(message))
        except Exception as e:
            logging.error(f"Error pushing to incoming queue: {e}")

    async def pop_incoming(self, timeout: int = 5) -> Optional[Dict]:
        """Pop a message from the incoming queue (Bot Logic consumes this)"""
        try:
            # blpop returns a tuple (key, value) or None
            item = await self.redis_client.blpop(self.incoming_key, timeout=timeout)
            if item:
                return json.loads(item[1])
        except Exception as e:
            logging.error(f"Error popping from incoming queue: {e}")
        return None

    async def push_outgoing(self, message: Dict):
        """Push a message to the outgoing queue (from Bot Logic to User)"""
        try:
            await self.redis_client.rpush(self.outgoing_key, json.dumps(message))
        except Exception as e:
            logging.error(f"Error pushing to outgoing queue: {e}")

    async def pop_outgoing(self, timeout: int = 5) -> Optional[Dict]:
        """Pop a message from the outgoing queue (Sender Service consumes this)"""
        try:
            item = await self.redis_client.blpop(self.outgoing_key, timeout=timeout)
            if item:
                return json.loads(item[1])
        except Exception as e:
            logging.error(f"Error popping from outgoing queue: {e}")
        return None
