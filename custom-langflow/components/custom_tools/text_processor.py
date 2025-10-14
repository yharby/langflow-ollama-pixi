from langflow.custom import Component
from langflow.io import MessageTextInput, DropdownInput, Output
from langflow.schema import Message


class TextProcessorComponent(Component):
    """
    A text processing component in the AI Tools folder.
    Demonstrates professional component organization.
    """
    
    display_name = "Text Processor"
    description = "Process and transform text with various operations"
    icon = "cpu"  # Professional icon for AI tools
    name = "TextProcessor"
    documentation = "https://docs.langflow.org/components-custom-components"
    
    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="Text to process",
            value="",
            placeholder="Enter text to process..."
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            info="Choose text processing operation",
            options=["uppercase", "lowercase", "title_case", "reverse", "word_count"],
            value="uppercase"
        )
    ]
    
    outputs = [
        Output(
            display_name="Processed Text",
            name="processed_text",
            method="process_text"
        )
    ]
    
    def process_text(self) -> Message:
        """
        Process the input text based on the selected operation.
        
        Returns:
            Message: Processed text result
        """
        try:
            text = getattr(self, 'input_text', '').strip()
            operation = getattr(self, 'operation', 'uppercase')
            
            if not text:
                return Message(text="Please provide input text to process.")
            
            # Process text based on operation
            if operation == "uppercase":
                result = text.upper()
            elif operation == "lowercase":
                result = text.lower()
            elif operation == "title_case":
                result = text.title()
            elif operation == "reverse":
                result = text[::-1]
            elif operation == "word_count":
                word_count = len(text.split())
                result = f"Word count: {word_count}\nCharacter count: {len(text)}\nOriginal text: {text}"
            else:
                result = text
            
            # Set status
            self.status = f"Applied {operation} operation to text"
            
            return Message(text=result)
            
        except Exception as e:
            error_msg = f"Error processing text: {str(e)}"
            self.status = error_msg
            return Message(text=error_msg)