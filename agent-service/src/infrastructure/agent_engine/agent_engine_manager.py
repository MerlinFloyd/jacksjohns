"""
Agent Engine Manager - handles creation and management of Agent Engine instances.

Agent Engine (ReasoningEngine) provides Sessions and Memory Bank services.
This manager handles the lifecycle of the Agent Engine instance.
"""

import logging
from typing import Any

import vertexai
from vertexai.preview import reasoning_engines

logger = logging.getLogger(__name__)


class AgentEngineManager:
    """
    Manages the Agent Engine instance lifecycle.
    
    Agent Engine instances are created via the SDK and provide:
    - Sessions: Conversation history management
    - Memory Bank: Long-term memory storage
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        agent_engine_id: str | None = None,
    ):
        """
        Initialize the Agent Engine Manager.
        
        Args:
            project_id: GCP project ID
            location: GCP region
            agent_engine_id: Existing Agent Engine ID (optional)
        """
        self.project_id = project_id
        self.location = location
        self._agent_engine_id = agent_engine_id
        self._client: vertexai.Client | None = None
        self._initialized = False
        
    def _ensure_initialized(self) -> None:
        """Initialize Vertex AI client if not already done."""
        if not self._initialized:
            vertexai.init(project=self.project_id, location=self.location)
            self._client = vertexai.Client(
                project=self.project_id,
                location=self.location,
            )
            self._initialized = True
            logger.info(
                f"AgentEngineManager initialized for project={self.project_id}, "
                f"location={self.location}"
            )
    
    @property
    def agent_engine_id(self) -> str | None:
        """Get the current Agent Engine ID."""
        return self._agent_engine_id
    
    @property
    def agent_engine_resource_name(self) -> str | None:
        """Get the full resource name for the Agent Engine."""
        if not self._agent_engine_id:
            return None
        return f"projects/{self.project_id}/locations/{self.location}/reasoningEngines/{self._agent_engine_id}"
    
    async def get_or_create_agent_engine(
        self,
        display_name: str = "jacksjohns-bot-engine",
        description: str = "Agent Engine for Jack's Johns Discord Bot - provides Sessions and Memory Bank",
    ) -> str:
        """
        Get existing or create a new Agent Engine instance.
        
        Args:
            display_name: Display name for new engine
            description: Description for new engine
            
        Returns:
            Agent Engine ID (just the ID part, not full resource name)
        """
        self._ensure_initialized()
        
        # If we already have an ID, verify it exists
        if self._agent_engine_id:
            try:
                engine = self._client.agent_engines.get(
                    name=self.agent_engine_resource_name
                )
                logger.info(f"Using existing Agent Engine: {self._agent_engine_id}")
                return self._agent_engine_id
            except Exception as e:
                logger.warning(
                    f"Agent Engine {self._agent_engine_id} not found: {e}. "
                    "Will create new one."
                )
                self._agent_engine_id = None
        
        # Create new Agent Engine
        logger.info("Creating new Agent Engine instance...")
        
        try:
            # Create Agent Engine with default configuration
            # This provides Sessions and Memory Bank services
            engine = self._client.agent_engines.create(
                display_name=display_name,
                description=description,
            )
            
            # Extract the ID from the resource name
            # Format: projects/{project}/locations/{location}/reasoningEngines/{id}
            resource_name = engine.api_resource.name
            self._agent_engine_id = resource_name.split("/")[-1]
            
            logger.info(f"Created Agent Engine: {self._agent_engine_id}")
            logger.info(f"Full resource name: {resource_name}")
            
            return self._agent_engine_id
            
        except Exception as e:
            logger.error(f"Failed to create Agent Engine: {e}")
            raise
    
    async def delete_agent_engine(self) -> bool:
        """
        Delete the current Agent Engine instance.
        
        Returns:
            True if deleted, False if no engine was configured
        """
        if not self._agent_engine_id:
            logger.warning("No Agent Engine ID configured")
            return False
            
        self._ensure_initialized()
        
        try:
            self._client.agent_engines.delete(
                name=self.agent_engine_resource_name,
                force=True,  # Delete even if it has sessions/memories
            )
            logger.info(f"Deleted Agent Engine: {self._agent_engine_id}")
            self._agent_engine_id = None
            return True
        except Exception as e:
            logger.error(f"Failed to delete Agent Engine: {e}")
            raise
    
    def get_client(self) -> vertexai.Client:
        """Get the Vertex AI client."""
        self._ensure_initialized()
        return self._client
