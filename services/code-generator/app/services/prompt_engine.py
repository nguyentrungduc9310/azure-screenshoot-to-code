"""
Prompt Engineering Service
Manages prompt templates and generation for different code stacks
"""
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionContentPartParam
from app.core.config import CodeStack

class InputMode(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    IMPORT = "import"

class GenerationType(str, Enum):
    CREATE = "create"
    UPDATE = "update"

@dataclass
class PromptRequest:
    """Request for prompt generation"""
    image_data_url: Optional[str] = None
    result_image_data_url: Optional[str] = None
    code_stack: CodeStack = CodeStack.HTML_TAILWIND
    input_mode: InputMode = InputMode.IMAGE
    generation_type: GenerationType = GenerationType.CREATE
    history: List[str] = None
    imported_code: Optional[str] = None
    additional_instructions: Optional[str] = None

class PromptEngine:
    """Manages prompt templates and generation for code generation"""
    
    def __init__(self):
        self.system_prompts = self._initialize_system_prompts()
        self.imported_code_prompts = self._initialize_imported_code_prompts()
    
    def _initialize_system_prompts(self) -> Dict[CodeStack, str]:
        """Initialize system prompts for different code stacks"""
        return {
            CodeStack.HTML_TAILWIND: """
You are an expert Tailwind developer
You take screenshots of a reference web page from the user, and then build single page apps 
using Tailwind, HTML and JS.
You might also be given a screenshot(The second image) of a web page that you have already built, and asked to
update it to look more like the reference image(The first image).

- Make sure the app looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.

In terms of libraries,

- Use this script to include Tailwind: <script src="https://cdn.tailwindcss.com"></script>
- You can use Google Fonts
- Font Awesome for icons: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css"></link>

Return only the full code in <html></html> tags.
Do not include markdown "```" or "```html" at the start or end.
""",
            
            CodeStack.HTML_CSS: """
You are an expert CSS developer
You take screenshots of a reference web page from the user, and then build single page apps 
using CSS, HTML and JS.
You might also be given a screenshot(The second image) of a web page that you have already built, and asked to
update it to look more like the reference image(The first image).

- Make sure the app looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.

In terms of libraries,

- You can use Google Fonts
- Font Awesome for icons: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css"></link>

Return only the full code in <html></html> tags.
Do not include markdown "```" or "```html" at the start or end.
""",
            
            CodeStack.REACT_TAILWIND: """
You are an expert React/Tailwind developer
You take screenshots of a reference web page from the user, and then build single page apps 
using React and Tailwind CSS.
You might also be given a screenshot(The second image) of a web page that you have already built, and asked to
update it to look more like the reference image(The first image).

- Make sure the app looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.

In terms of libraries,

- Use these script to include React so that it can run on a standalone page:
    <script src="https://unpkg.com/react@18.0.0/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18.0.0/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.js"></script>
- Use this script to include Tailwind: <script src="https://cdn.tailwindcss.com"></script>
- You can use Google Fonts
- Font Awesome for icons: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css"></link>

Return only the full code in <html></html> tags.
Do not include markdown "```" or "```html" at the start or end.
""",
            
            CodeStack.VUE_TAILWIND: """
You are an expert Vue/Tailwind developer
You take screenshots of a reference web page from the user, and then build single page apps 
using Vue and Tailwind CSS.
You might also be given a screenshot(The second image) of a web page that you have already built, and asked to
update it to look more like the reference image(The first image).

- Make sure the app looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.
- Use Vue using the global build like so:

<div id="app">{{ message }}</div>
<script>
  const { createApp, ref } = Vue
  createApp({
    setup() {
      const message = ref('Hello vue!')
      return {
        message
      }
    }
  }).mount('#app')
</script>

In terms of libraries,

- Use these script to include Vue so that it can run on a standalone page:
  <script src="https://registry.npmmirror.com/vue/3.3.11/files/dist/vue.global.js"></script>
- Use this script to include Tailwind: <script src="https://cdn.tailwindcss.com"></script>
- You can use Google Fonts
- Font Awesome for icons: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css"></link>

Return only the full code in <html></html> tags.
Do not include markdown "```" or "```html" at the start or end.
The return result must only include the code.
""",
            
            CodeStack.BOOTSTRAP: """
You are an expert Bootstrap developer
You take screenshots of a reference web page from the user, and then build single page apps 
using Bootstrap, HTML and JS.
You might also be given a screenshot(The second image) of a web page that you have already built, and asked to
update it to look more like the reference image(The first image).

- Make sure the app looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.

In terms of libraries,

- Use this script to include Bootstrap: <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN" crossorigin="anonymous">
- You can use Google Fonts
- Font Awesome for icons: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css"></link>

Return only the full code in <html></html> tags.
Do not include markdown "```" or "```html" at the start or end.
""",
            
            CodeStack.IONIC_TAILWIND: """
You are an expert Ionic/Tailwind developer
You take screenshots of a reference web page from the user, and then build single page apps 
using Ionic and Tailwind CSS.
You might also be given a screenshot(The second image) of a web page that you have already built, and asked to
update it to look more like the reference image(The first image).

- Make sure the app looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.

In terms of libraries,

- Use these script to include Ionic so that it can run on a standalone page:
    <script type="module" src="https://cdn.jsdelivr.net/npm/@ionic/core/dist/ionic/ionic.esm.js"></script>
    <script nomodule src="https://cdn.jsdelivr.net/npm/@ionic/core/dist/ionic/ionic.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@ionic/core/css/ionic.bundle.css" />
- Use this script to include Tailwind: <script src="https://cdn.tailwindcss.com"></script>
- You can use Google Fonts
- ionicons for icons, add the following <script > tags near the end of the page, right before the closing </body> tag:
    <script type="module">
        import ionicons from 'https://cdn.jsdelivr.net/npm/ionicons/+esm'
    </script>
    <script nomodule src="https://cdn.jsdelivr.net/npm/ionicons/dist/esm/ionicons.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/ionicons/dist/collection/components/icon/icon.min.css" rel="stylesheet">

Return only the full code in <html></html> tags.
Do not include markdown "```" or "```html" at the start or end.
""",
            
            CodeStack.SVG: """
You are an expert at building SVGs.
You take screenshots of a reference web page from the user, and then build a SVG that looks exactly like the screenshot.

- Make sure the SVG looks exactly like the screenshot.
- Pay close attention to background color, text color, font size, font family, 
padding, margin, border, etc. Match the colors and sizes exactly.
- Use the exact text from the screenshot.
- Do not add comments in the code such as "<!-- Add other navigation links as needed -->" and "<!-- ... other news items ... -->" in place of writing the full code. WRITE THE FULL CODE.
- Repeat elements as needed to match the screenshot. For example, if there are 15 items, the code should have 15 items. DO NOT LEAVE comments like "<!-- Repeat for each news item -->" or bad things will happen.
- For images, use placeholder images from https://placehold.co and include a detailed description of the image in the alt text so that an image generation AI can generate the image later.
- You can use Google Fonts

Return only the full code in <svg></svg> tags.
Do not include markdown "```" or "```svg" at the start or end.
"""
        }
    
    def _initialize_imported_code_prompts(self) -> Dict[CodeStack, str]:
        """Initialize prompts for imported code modifications"""
        base_prompt = """
You are an expert developer. A user will provide you with low-fidelity wireframes, then you will return a single html file that uses the specified framework.
You will make sure the app looks exactly like the wireframes.
Do not leave any placeholders in the code. Make sure to include all the elements from the wireframes.
Make sure the styling adheres to the provided framework.
"""
        
        framework_specific = {
            CodeStack.HTML_TAILWIND: base_prompt + "\nUse Tailwind CSS for styling.",
            CodeStack.HTML_CSS: base_prompt + "\nUse vanilla CSS for styling.",
            CodeStack.REACT_TAILWIND: base_prompt + "\nUse React components with Tailwind CSS.",
            CodeStack.VUE_TAILWIND: base_prompt + "\nUse Vue.js components with Tailwind CSS.",
            CodeStack.BOOTSTRAP: base_prompt + "\nUse Bootstrap for styling and layout.",
            CodeStack.IONIC_TAILWIND: base_prompt + "\nUse Ionic components with Tailwind CSS.",
            CodeStack.SVG: base_prompt + "\nGenerate SVG code that matches the wireframe."
        }
        
        return framework_specific
    
    def generate_prompt(self, request: PromptRequest) -> List[ChatCompletionMessageParam]:
        """Generate complete prompt messages for code generation"""
        
        if request.input_mode == InputMode.IMPORT and request.imported_code:
            return self._generate_imported_code_prompt(request)
        else:
            return self._generate_screenshot_prompt(request)
    
    def _generate_screenshot_prompt(self, request: PromptRequest) -> List[ChatCompletionMessageParam]:
        """Generate prompt for screenshot-based code generation"""
        system_content = self.system_prompts[request.code_stack]
        
        # Add additional instructions if provided
        if request.additional_instructions:
            system_content += f"\n\nAdditional instructions: {request.additional_instructions}"
        
        user_prompt = self._get_user_prompt(request.code_stack)
        
        # Build user content with image(s)
        user_content: List[ChatCompletionContentPartParam] = []
        
        # Add main image
        if request.image_data_url:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": request.image_data_url, "detail": "high"}
            })
        
        # Add result image if provided (for updates)
        if request.result_image_data_url:
            user_content.append({
                "type": "image_url", 
                "image_url": {"url": request.result_image_data_url, "detail": "high"}
            })
        
        # Add text prompt
        user_content.append({
            "type": "text",
            "text": user_prompt
        })
        
        messages = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user", 
                "content": user_content
            }
        ]
        
        # Add conversation history for updates
        if request.generation_type == GenerationType.UPDATE and request.history:
            for index, text in enumerate(request.history):
                role = "assistant" if index % 2 == 0 else "user"
                messages.append({
                    "role": role,
                    "content": text
                })
        
        return messages
    
    def _generate_imported_code_prompt(self, request: PromptRequest) -> List[ChatCompletionMessageParam]:
        """Generate prompt for imported code modifications"""
        system_content = self.imported_code_prompts[request.code_stack]
        
        # Add additional instructions if provided
        if request.additional_instructions:
            system_content += f"\n\nAdditional instructions: {request.additional_instructions}"
        
        code_type = "app" if request.code_stack != CodeStack.SVG else "SVG"
        user_content = f"Here is the code of the {code_type}: {request.imported_code}"
        
        messages = [
            {
                "role": "system",
                "content": system_content + "\n " + user_content
            }
        ]
        
        # Add conversation history
        if request.history:
            for index, text in enumerate(request.history[1:]):  # Skip the imported code
                role = "user" if index % 2 == 0 else "assistant"
                messages.append({
                    "role": role,
                    "content": text
                })
        
        return messages
    
    def _get_user_prompt(self, stack: CodeStack) -> str:
        """Get user prompt based on code stack"""
        if stack == CodeStack.SVG:
            return "Generate code for a SVG that looks exactly like this."
        else:
            return "Generate code for a web page that looks exactly like this."
    
    def validate_request(self, request: PromptRequest) -> List[str]:
        """Validate prompt request and return list of issues"""
        issues = []
        
        # Check code stack support
        if request.code_stack not in self.system_prompts:
            issues.append(f"Unsupported code stack: {request.code_stack.value}")
        
        # Check input requirements
        if request.input_mode == InputMode.IMPORT:
            if not request.imported_code:
                issues.append("Imported code is required for import mode")
        else:
            if not request.image_data_url:
                issues.append("Image data URL is required for image mode")
        
        # Check image format
        if request.image_data_url and not request.image_data_url.startswith("data:image/"):
            issues.append("Invalid image data URL format")
        
        if request.result_image_data_url and not request.result_image_data_url.startswith("data:image/"):
            issues.append("Invalid result image data URL format")
        
        return issues
    
    def get_supported_stacks(self) -> List[CodeStack]:
        """Get list of supported code stacks"""
        return list(self.system_prompts.keys())
    
    def get_stack_description(self, stack: CodeStack) -> str:
        """Get description for a code stack"""
        descriptions = {
            CodeStack.HTML_TAILWIND: "HTML with Tailwind CSS - Modern utility-first CSS framework",
            CodeStack.HTML_CSS: "HTML with vanilla CSS - Traditional CSS styling",
            CodeStack.REACT_TAILWIND: "React with Tailwind CSS - Component-based UI with utility CSS",
            CodeStack.VUE_TAILWIND: "Vue.js with Tailwind CSS - Progressive framework with utility CSS",
            CodeStack.BOOTSTRAP: "HTML with Bootstrap - Component-based CSS framework",
            CodeStack.IONIC_TAILWIND: "Ionic with Tailwind CSS - Mobile-first components with utility CSS",
            CodeStack.SVG: "SVG - Scalable Vector Graphics"
        }
        return descriptions.get(stack, f"Code generation for {stack.value}")
    
    def extract_html_content(self, generated_code: str) -> str:
        """Extract HTML content from generated code, removing markdown formatting"""
        import re
        
        # Remove markdown code blocks
        code = re.sub(r'^```(?:html|xml|svg)?\s*\n?', '', generated_code, flags=re.MULTILINE)
        code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)
        
        # Clean up any extra whitespace
        code = code.strip()
        
        return code