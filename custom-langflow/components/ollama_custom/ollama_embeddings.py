from typing import Any
from urllib.parse import urljoin
import asyncio

import httpx
from langchain_ollama import OllamaEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.base.models.ollama_constants import OLLAMA_EMBEDDING_MODELS, URL_LIST
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.logging import logger

HTTP_STATUS_OK = 200


class OllamaEmbeddingsComponent(LCModelComponent):
    display_name: str = "Ollama Embeddings"
    description: str = "Generate embeddings using Ollama models."
    documentation = "https://python.langchain.com/docs/integrations/text_embedding/ollama"
    icon = "Ollama"
    name = "OllamaEmbeddings"

    # Define constants for JSON keys (matching ChatOllama)
    JSON_MODELS_KEY = "models"
    JSON_NAME_KEY = "name"
    JSON_CAPABILITIES_KEY = "capabilities"
    EMBEDDING_CAPABILITY = "embedding"

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Ollama Model",
            value="",
            options=[],
            real_time_refresh=True,
            refresh_button=True,
            combobox=True,
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Ollama Base URL",
            value="",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            output = OllamaEmbeddings(model=self.model_name, base_url=self.base_url)
        except Exception as e:
            msg = (
                "Unable to connect to the Ollama API. "
                "Please verify the base URL, ensure the relevant Ollama model is pulled, and try again."
            )
            raise ValueError(msg) from e
        return output

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name in {"base_url", "model_name"} and not await self.is_valid_ollama_url(field_value):
            # Check if any URL in the list is valid
            valid_url = ""
            for url in URL_LIST:
                if await self.is_valid_ollama_url(url):
                    valid_url = url
                    break
            build_config["base_url"]["value"] = valid_url
        if field_name in {"model_name", "base_url"}:
            if await self.is_valid_ollama_url(self.base_url):
                build_config["model_name"]["options"] = await self.get_model(self.base_url)
            elif await self.is_valid_ollama_url(build_config["base_url"].get("value", "")):
                build_config["model_name"]["options"] = await self.get_model(build_config["base_url"].get("value", ""))
            else:
                build_config["model_name"]["options"] = []

        return build_config

    async def get_model(self, base_url_value: str) -> list[str]:
        """Get the embedding model names from Ollama by checking their capabilities."""
        model_ids = []
        try:
            # Normalize the base URL
            base_url = base_url_value.rstrip("/") + "/"
            
            # Ollama REST API endpoints
            tags_url = urljoin(base_url, "api/tags")
            show_url = urljoin(base_url, "api/show")
            
            async with httpx.AsyncClient() as client:
                # Fetch all available models
                tags_response = await client.get(tags_url)
                tags_response.raise_for_status()
                models = tags_response.json()
                if asyncio.iscoroutine(models):
                    models = await models
                
                await logger.adebug(f"Available models for embeddings: {models}")
                
                # First, try to filter by checking capabilities
                capability_checked_models = []
                fallback_models = []
                
                for model in models.get(self.JSON_MODELS_KEY, []):
                    model_name = model.get(self.JSON_NAME_KEY, "")
                    if not model_name:
                        continue
                        
                    # Try to check capabilities
                    try:
                        payload = {"model": model_name}
                        show_response = await client.post(show_url, json=payload, timeout=5.0)
                        
                        if show_response.status_code == HTTP_STATUS_OK:
                            json_data = show_response.json()
                            if asyncio.iscoroutine(json_data):
                                json_data = await json_data
                            
                            capabilities = json_data.get(self.JSON_CAPABILITIES_KEY, [])
                            await logger.adebug(f"Model: {model_name}, Capabilities: {capabilities}")
                            
                            # Check if model has embedding capability
                            if self.EMBEDDING_CAPABILITY in capabilities:
                                capability_checked_models.append(model_name)
                        else:
                            # If we can't check capabilities, fall back to name-based detection
                            fallback_models.append(model_name)
                            
                    except Exception as e:
                        # If checking capabilities fails, add to fallback list
                        await logger.adebug(f"Could not check capabilities for {model_name}: {e}")
                        fallback_models.append(model_name)
                
                # If we found models with embedding capability, use those
                if capability_checked_models:
                    model_ids = capability_checked_models
                else:
                    # Fall back to name-based detection or show all models
                    await logger.adebug("No models with embedding capability found, using fallback detection")
                    
                    # Common embedding model indicators
                    embedding_indicators = [
                        'embed', 'embedding', 'e5', 'bge', 'gte', 
                        'instructor', 'sentence', 'similarity', 
                        'retrieval', 'vector', 'encode', 'nomic'
                    ]
                    
                    # Try to identify embedding models by name
                    for model_name in fallback_models:
                        lower_name = model_name.lower()
                        
                        # Check against known embedding models from constants
                        is_known_embedding = any(
                            lower_name.startswith(known.lower()) 
                            for known in OLLAMA_EMBEDDING_MODELS
                        )
                        
                        # Check for embedding indicators in the name
                        has_indicator = any(
                            indicator in lower_name 
                            for indicator in embedding_indicators
                        )
                        
                        if is_known_embedding or has_indicator:
                            model_ids.append(model_name)
                    
                    # If still no models found, return all models and let user choose
                    if not model_ids:
                        await logger.adebug("No embedding models identified, returning all models")
                        model_ids = fallback_models

        except (ImportError, ValueError, httpx.RequestError) as e:
            msg = "Could not get model names from Ollama."
            raise ValueError(msg) from e

        return model_ids

    async def is_valid_ollama_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                return (await client.get(f"{url}/api/tags")).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False