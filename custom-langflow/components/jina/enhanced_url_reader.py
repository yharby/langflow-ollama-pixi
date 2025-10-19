import re
import requests
from typing import List, Dict, Any, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.helpers.data import safe_convert
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SliderInput, TableInput, SecretStrInput
from langflow.logging.logger import logger
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.services.deps import get_settings_service

# Constants
DEFAULT_TIMEOUT = 30
DEFAULT_FORMAT = "Markdown"  # Changed default to Markdown
JINA_READER_BASE_URL = "https://r.jina.ai/"
# Note: Jina Reader API is free but has rate limits:
# - Without API key: 20 requests per minute
# - With API key: 200 requests per minute
# Get your API key at: https://jina.ai/reader/
URL_REGEX = re.compile(
    r"^(https?:\/\/)?" r"(www\.)?" r"([a-zA-Z0-9.-]+)" r"(\.[a-zA-Z]{2,})?" r"(:\d+)?" r"(\/[^\s]*)?$",
    re.IGNORECASE,
)


class EnhancedURLComponent(Component):
    """A component that loads and parses content from web pages using Jina Reader API.

    This component uses Jina Reader API (https://r.jina.ai/) to:
    - Convert any URL to clean, LLM-friendly markdown text
    - Handle JavaScript-rendered pages automatically
    - Extract main content while ignoring navigation and ads
    - Support PDF extraction from URLs
    - Provide image captions when enabled
    - Handle complex websites with proper UTF-8 encoding

    Free tier: 20 requests/minute (no API key needed)
    With API key: 200 requests/minute
    """

    display_name = "Enhanced URL Reader (Jina)"
    description = "Fetch and extract web content using Jina Reader API with automatic UTF-8 encoding support."
    documentation: str = "https://docs.langflow.org/components-data#url"
    icon = "layout-template"
    name = "EnhancedURLComponent"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Enter one or more URLs to fetch. The content will be extracted using Jina Reader API.",
            is_list=True,
            tool_mode=True,
            placeholder="Enter a URL...",
            list_add_label="Add URL",
            input_types=[],
        ),
        SecretStrInput(
            name="jina_api_key",
            display_name="Jina API Key",
            info="Optional: Provide your Jina API key for higher rate limits (200 requests/minute vs 20 requests/minute for free tier). Get your key at https://jina.ai/reader/",
            required=False,
        ),
        DropdownInput(
            name="format",
            display_name="Output Format",
            info="Choose the output format. 'Markdown' uses Jina Reader for clean markdown. 'JSON' returns structured data.",
            options=["Markdown", "JSON", "Text", "HTML"],
            value=DEFAULT_FORMAT,
            advanced=False,
        ),
        BoolInput(
            name="enable_image_captions",
            display_name="Enable Image Captions",
            info="If enabled, generates captions for images found on the page (may increase latency).",
            value=False,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="no_cache",
            display_name="Bypass Cache",
            info="If enabled, bypasses Jina's cache to get fresh content (cache lifetime is 3600s).",
            value=False,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="streaming_mode",
            display_name="Streaming Mode",
            info="If enabled, uses streaming mode for more complete content on dynamic sites (slower but more complete).",
            value=False,
            required=False,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for the request in seconds.",
            value=DEFAULT_TIMEOUT,
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="target_selector",
            display_name="Target CSS Selector",
            info="Optional: CSS selector to focus on specific part of the page (e.g., '#content', '.article-body').",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="wait_for_selector",
            display_name="Wait for CSS Selector",
            info="Optional: Wait for this CSS selector to appear before extracting content (useful for SPAs).",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="proxy_url",
            display_name="Proxy URL",
            info="Optional: Proxy server URL to use for requests.",
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="include_links_summary",
            display_name="Include Links Summary",
            info="If enabled, includes a summary of all links found on the page.",
            value=False,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="include_images_summary",
            display_name="Include Images Summary",
            info="If enabled, includes a summary of all images found on the page.",
            value=False,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Extracted Pages", name="page_results", method="fetch_content"),
        Output(display_name="Raw Content", name="raw_results", method="fetch_content_as_message", tool_mode=False),
    ]

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validates if the given string matches URL pattern.

        Args:
            url: The URL string to validate

        Returns:
            bool: True if the URL is valid, False otherwise
        """
        return bool(URL_REGEX.match(url))

    def ensure_url(self, url: str) -> str:
        """Ensures the given string is a valid URL.

        Args:
            url: The URL string to validate and normalize

        Returns:
            str: The normalized URL

        Raises:
            ValueError: If the URL is invalid
        """
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if not self.validate_url(url):
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)

        return url

    def _build_jina_headers(self) -> Dict[str, str]:
        """Build headers for Jina Reader API request.

        Returns:
            Dict[str, str]: Headers dictionary for the request
        """
        headers = {}
        
        # Add API key if provided - following the pattern from Bing Search component
        if self.jina_api_key:
            headers["Authorization"] = f"Bearer {self.jina_api_key}"
        
        # Set response format
        if self.format == "JSON":
            headers["Accept"] = "application/json"
        elif self.streaming_mode:
            headers["Accept"] = "text/event-stream"
        else:
            headers["Accept"] = "text/plain"
        
        # Enable image captions
        if self.enable_image_captions:
            headers["x-with-generated-alt"] = "true"
        
        # Bypass cache
        if self.no_cache:
            headers["x-no-cache"] = "true"
        
        # Set timeout
        if self.timeout:
            headers["x-timeout"] = str(self.timeout)
        
        # Target selector
        if self.target_selector:
            headers["x-target-selector"] = self.target_selector
        
        # Wait for selector
        if self.wait_for_selector:
            headers["x-wait-for-selector"] = self.wait_for_selector
        
        # Proxy URL
        if self.proxy_url:
            headers["x-proxy-url"] = self.proxy_url
        
        # Include links summary
        if self.include_links_summary:
            headers["x-with-links-summary"] = "true"
        
        # Include images summary
        if self.include_images_summary:
            headers["x-with-images-summary"] = "true"
        
        # Add user agent
        headers["User-Agent"] = get_settings_service().settings.user_agent
        
        return headers

    def _fetch_with_jina_reader(self, url: str) -> Dict[str, Any]:
        """Fetch content from URL using Jina Reader API.

        Args:
            url: The URL to fetch

        Returns:
            Dict[str, Any]: Dictionary containing the fetched content and metadata
        """
        # Check if URL already starts with Jina Reader base URL to avoid duplication
        if url.startswith(JINA_READER_BASE_URL):
            jina_url = url
        else:
            jina_url = f"{JINA_READER_BASE_URL}{url}"

        headers = self._build_jina_headers()
        
        try:
            logger.debug(f"Fetching URL with Jina Reader: {jina_url}")
            
            response = requests.get(
                jina_url,
                headers=headers,
                timeout=self.timeout if self.timeout else DEFAULT_TIMEOUT
            )
            response.raise_for_status()

            # Always ensure UTF-8 encoding for proper handling of Arabic, Chinese, and other non-Latin text
            response.encoding = response.apparent_encoding or 'utf-8'

            # Handle different response formats
            if self.format == "JSON":
                try:
                    data = response.json()
                    return {
                        "text": data.get("content", ""),
                        "url": data.get("url", url),
                        "title": data.get("title", "")
                    }
                except (ValueError, requests.exceptions.JSONDecodeError) as e:
                    # If JSON parsing fails, treat as text
                    logger.warning(f"Failed to parse JSON response, falling back to text: {e}")
                    return {
                        "text": response.text,
                        "url": url,
                        "title": ""
                    }
            elif self.streaming_mode:
                # For streaming mode, we'll collect all chunks
                # In a real implementation, you might want to process chunks differently
                content = response.text
                # Split by newlines to get the last complete chunk
                chunks = content.strip().split('\n')
                final_content = chunks[-1] if chunks else ""
                
                return {
                    "text": final_content,
                    "url": url,
                    "title": ""
                }
            else:
                # Default markdown/text response
                return {
                    "text": response.text,
                    "url": url,
                    "title": ""
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL with Jina Reader: {e}")
            raise ValueError(f"Failed to fetch {url} with Jina Reader: {e}")

    def fetch_url_contents(self) -> List[Dict[str, Any]]:
        """Load documents from the configured URLs.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing the fetched content

        Raises:
            ValueError: If no valid URLs are provided or if there's an error loading documents
        """
        try:
            # Validate and deduplicate URLs
            urls = list({self.ensure_url(url) for url in self.urls if url.strip()})
            
            if not urls:
                msg = "No valid URLs provided."
                raise ValueError(msg)
            
            all_docs = []
            
            for url in urls:
                logger.debug(f"Processing URL: {url}")

                try:
                    # Always use Jina Reader API (the purpose of this component)
                    doc_data = self._fetch_with_jina_reader(url)

                    # Clean and add the document
                    doc_data["text"] = safe_convert(doc_data["text"], clean_data=True)
                    all_docs.append(doc_data)
                    
                    logger.debug(f"Successfully processed {url}")
                    
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    if not all_docs:  # Only fail if no documents have been successfully loaded
                        raise
                    continue
            
            if not all_docs:
                msg = "No documents were successfully loaded from any URL"
                raise ValueError(msg)
            
            return all_docs
            
        except Exception as e:
            error_msg = str(e)
            msg = f"Error loading documents: {error_msg}"
            logger.exception(msg)
            raise ValueError(msg) from e

    def fetch_content(self) -> DataFrame:
        """Convert the documents to a DataFrame."""
        return DataFrame(data=self.fetch_url_contents())

    def fetch_content_as_message(self) -> Message:
        """Convert the documents to a Message."""
        url_contents = self.fetch_url_contents()
        
        # Combine all text content
        combined_text = "\n\n---\n\n".join([
            f"**Source:** {doc['url']}\n**Title:** {doc.get('title', 'N/A')}\n\n{doc['text']}"
            for doc in url_contents
        ])
        
        return Message(
            text=combined_text,
            data={"documents": url_contents}
        )