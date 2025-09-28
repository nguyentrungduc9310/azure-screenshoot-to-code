"""
Rich Response Formatter
Advanced adaptive card generation with syntax highlighting and interactive elements
"""
import re
import json
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        """Mock correlation ID function"""
        import uuid
        return str(uuid.uuid4())[:8]


class ResponseTheme(Enum):
    """Response theme variations"""
    DEFAULT = "default"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PREMIUM = "premium"


class CodeLanguage(Enum):
    """Supported code languages for syntax highlighting"""
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    JSX = "jsx"
    TSX = "tsx"
    VUE = "vue"
    PYTHON = "python"
    JSON = "json"
    SCSS = "scss"
    LESS = "less"


@dataclass
class CodeBlock:
    """Code block with syntax highlighting"""
    filename: str
    content: str
    language: CodeLanguage
    line_numbers: bool = True
    collapsible: bool = False
    max_lines: Optional[int] = None
    
    def truncate_for_display(self, max_lines: int = 20) -> str:
        """Truncate code for display in cards"""
        lines = self.content.split('\n')
        if len(lines) <= max_lines:
            return self.content
        
        return '\n'.join(lines[:max_lines]) + f'\n... ({len(lines) - max_lines} more lines)'
    
    def get_language_icon(self) -> str:
        """Get emoji icon for language"""
        icons = {
            CodeLanguage.JAVASCRIPT: "🟨",
            CodeLanguage.TYPESCRIPT: "🔷", 
            CodeLanguage.HTML: "🌐",
            CodeLanguage.CSS: "🎨",
            CodeLanguage.JSX: "⚛️",
            CodeLanguage.TSX: "⚛️",
            CodeLanguage.VUE: "💚",
            CodeLanguage.PYTHON: "🐍",
            CodeLanguage.JSON: "📋",
            CodeLanguage.SCSS: "💜",
            CodeLanguage.LESS: "🔵"
        }
        return icons.get(self.language, "📄")


@dataclass
class InteractiveAction:
    """Interactive action for adaptive cards"""
    id: str
    title: str
    action_type: str  # Submit, OpenUrl, ShowCard, etc.
    data: Dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None
    icon: Optional[str] = None
    style: str = "default"  # default, positive, destructive
    is_primary: bool = False


@dataclass
class ProgressIndicator:
    """Progress indicator for multi-step operations"""
    current_step: int
    total_steps: int
    step_title: str
    step_description: Optional[str] = None
    estimated_time_remaining: Optional[int] = None  # seconds


class RichResponseFormatter:
    """Advanced response formatter with rich adaptive cards"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        self.theme_colors = {
            ResponseTheme.DEFAULT: {"primary": "#0078D4", "accent": "#6264A7"},
            ResponseTheme.SUCCESS: {"primary": "#107C10", "accent": "#16C60C"},
            ResponseTheme.ERROR: {"primary": "#D13438", "accent": "#F7630C"},
            ResponseTheme.WARNING: {"primary": "#F7630C", "accent": "#FFB900"},
            ResponseTheme.INFO: {"primary": "#0078D4", "accent": "#40E0D0"},
            ResponseTheme.PREMIUM: {"primary": "#8B5CF6", "accent": "#A78BFA"}
        }
    
    def create_code_generation_response(
        self,
        code_blocks: List[CodeBlock],
        framework: str,
        processing_time_ms: float,
        theme: ResponseTheme = ResponseTheme.SUCCESS,
        user_preferences: Optional[Dict[str, Any]] = None,
        preview_url: Optional[str] = None,
        actions: Optional[List[InteractiveAction]] = None
    ) -> Dict[str, Any]:
        """Create rich code generation response with syntax highlighting"""
        
        correlation_id = get_correlation_id()
        user_prefs = user_preferences or {}
        communication_style = user_prefs.get("communication_style", "detailed")
        
        # Header section
        header_text = f"✨ {framework.upper()} Code Generated!"
        if communication_style == "concise":
            header_text = f"✅ {framework.upper()} Ready!"
        
        body_elements = [
            {
                "type": "TextBlock",
                "text": header_text,
                "weight": "Bolder",
                "size": "Large",
                "color": "Good"
            }
        ]
        
        # Performance indicator
        if communication_style == "detailed":
            body_elements.append({
                "type": "TextBlock",
                "text": f"⚡ Generated in {processing_time_ms:.0f}ms | Files: {len(code_blocks)}",
                "size": "Small",
                "color": "Accent",
                "spacing": "None"
            })
        
        # Add separator
        body_elements.append({
            "type": "TextBlock",
            "text": "",
            "separator": True
        })
        
        # Code blocks with syntax highlighting
        for i, code_block in enumerate(code_blocks):
            # File header
            body_elements.append({
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": code_block.get_language_icon(),
                                "size": "Medium"
                            }
                        ]
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"**{code_block.filename}**",
                                "weight": "Bolder",
                                "size": "Medium"
                            }
                        ]
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"{len(code_block.content.split())} lines",
                                "size": "Small",
                                "color": "Accent"
                            }
                        ]
                    }
                ]
            })
            
            # Code content with syntax highlighting simulation
            display_content = code_block.truncate_for_display(
                max_lines=code_block.max_lines or (10 if communication_style == "concise" else 25)
            )
            
            # Enhanced code block with background
            body_elements.append({
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": display_content,
                        "fontType": "Monospace",
                        "wrap": True,
                        "size": "Small"
                    }
                ],
                "spacing": "Medium" if i == 0 else "Small"
            })
            
            # Add collapsible indicator if truncated
            if len(code_block.content.split('\n')) > (code_block.max_lines or 25):
                body_elements.append({
                    "type": "TextBlock",
                    "text": f"📄 View complete file ({len(code_block.content.split())} total lines)",
                    "size": "Small",
                    "color": "Accent",
                    "spacing": "None"
                })
        
        # Preview section
        if preview_url:
            body_elements.extend([
                {
                    "type": "TextBlock",
                    "text": "",
                    "separator": True
                },
                {
                    "type": "TextBlock",
                    "text": "🌐 **Live Preview Available**",
                    "weight": "Bolder",
                    "size": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "Your code is ready to view in a live environment",
                    "wrap": True,
                    "size": "Small"
                }
            ])
        
        # Create actions
        card_actions = []
        
        # Default actions
        default_actions = [
            InteractiveAction(
                id="regenerate",
                title="🔄 Regenerate",
                action_type="Action.Submit",
                data={"action": "regenerateCode", "correlation_id": correlation_id},
                icon="🔄"
            ),
            InteractiveAction(
                id="download",
                title="💾 Download Files",
                action_type="Action.Submit", 
                data={"action": "downloadCode", "correlation_id": correlation_id},
                icon="💾",
                style="positive"
            )
        ]
        
        # Add preview action if available
        if preview_url:
            default_actions.insert(1, InteractiveAction(
                id="preview",
                title="👀 Live Preview",
                action_type="Action.OpenUrl",
                url=preview_url,
                icon="👀",
                is_primary=True
            ))
        
        # Add custom actions
        all_actions = default_actions + (actions or [])
        
        # Convert actions to adaptive card format
        for action in all_actions:
            card_action = {
                "type": action.action_type,
                "title": action.title,
                "id": action.id
            }
            
            if action.action_type == "Action.Submit":
                card_action["data"] = action.data
            elif action.action_type == "Action.OpenUrl":
                card_action["url"] = action.url
            
            if action.style != "default":
                card_action["style"] = action.style
            
            card_actions.append(card_action)
        
        # Create the adaptive card
        adaptive_card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": body_elements,
            "actions": card_actions,
            "metadata": {
                "correlation_id": correlation_id,
                "theme": theme.value,
                "framework": framework,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "code_blocks_count": len(code_blocks)
            }
        }
        
        return adaptive_card
    
    def create_framework_selection_response(
        self,
        image_url: str,
        user_preferences: Optional[Dict[str, Any]] = None,
        theme: ResponseTheme = ResponseTheme.DEFAULT,
        available_frameworks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create enhanced framework selection response"""
        
        user_prefs = user_preferences or {}
        preferred_framework = user_prefs.get("preferred_framework", "react")
        communication_style = user_prefs.get("communication_style", "detailed")
        experience_level = user_prefs.get("experience_level", "beginner")
        
        # Adaptive greeting based on user profile
        if experience_level == "advanced":
            greeting = "🎯 Ready to generate code from your screenshot"
        elif experience_level == "intermediate": 
            greeting = "🎨 Great screenshot! Let's convert it to code"
        else:
            greeting = "📸 Perfect! I can see your screenshot clearly"
        
        if communication_style == "concise":
            greeting = "🎨 Screenshot received! Choose framework:"
        
        # Framework configurations with enhanced metadata
        frameworks = [
            {
                "key": "react",
                "title": "⚛️ React",
                "description": "Modern React with hooks and TypeScript support",
                "features": ["Hooks", "TypeScript", "Responsive", "Accessible"],
                "difficulty": "intermediate",
                "popularity": 95
            },
            {
                "key": "html", 
                "title": "🌐 HTML/CSS",
                "description": "Clean HTML5 with modern CSS and responsive design",
                "features": ["HTML5", "CSS3", "Responsive", "Cross-browser"],
                "difficulty": "beginner",
                "popularity": 85
            },
            {
                "key": "vue",
                "title": "💚 Vue.js",
                "description": "Vue 3 with Composition API and modern tooling",
                "features": ["Composition API", "TypeScript", "Reactive", "Lightweight"],
                "difficulty": "beginner",
                "popularity": 75
            },
            {
                "key": "angular",
                "title": "🅰️ Angular",
                "description": "Angular with TypeScript and Material Design",
                "features": ["TypeScript", "Material UI", "Enterprise", "Scalable"],
                "difficulty": "advanced",
                "popularity": 65
            },
            {
                "key": "svelte",
                "title": "🧡 Svelte",
                "description": "Svelte with SvelteKit for optimal performance",
                "features": ["Compiled", "No runtime", "Fast", "Minimal"],
                "difficulty": "intermediate",
                "popularity": 70
            }
        ]
        
        # Filter frameworks if specified
        if available_frameworks:
            frameworks = [fw for fw in frameworks if fw["key"] in available_frameworks]
        
        # Sort by user preference and popularity
        def framework_score(fw):
            score = fw["popularity"]
            if fw["key"] == preferred_framework:
                score += 50  # Boost preferred framework
            if experience_level == "beginner" and fw["difficulty"] == "beginner":
                score += 20
            elif experience_level == "advanced" and fw["difficulty"] == "advanced":
                score += 15
            return score
        
        frameworks.sort(key=framework_score, reverse=True)
        
        # Build card body
        body_elements = [
            {
                "type": "TextBlock",
                "text": greeting,
                "weight": "Bolder",
                "size": "Large"
            }
        ]
        
        # Add recommendation explanation for detailed style
        if communication_style == "detailed":
            body_elements.append({
                "type": "TextBlock",
                "text": f"Based on your preferences, I recommend **{preferred_framework.upper()}**. Choose your preferred framework below:",
                "wrap": True,
                "size": "Default"
            })
        
        # Add image preview
        body_elements.extend([
            {
                "type": "Image",
                "url": image_url,
                "size": "Large" if communication_style == "detailed" else "Medium",
                "altText": "Screenshot to convert",
                "spacing": "Medium"
            },
            {
                "type": "TextBlock",
                "text": "",
                "separator": True
            }
        ])
        
        # Framework selection with enhanced cards
        if communication_style == "detailed":
            # Detailed framework cards
            for fw in frameworks[:3]:  # Show top 3 in detail
                is_recommended = fw["key"] == preferred_framework
                
                framework_card = {
                    "type": "Container",
                    "style": "emphasis" if is_recommended else "default",
                    "items": [
                        {
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "type": "Column",
                                    "width": "auto",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": fw["title"],
                                            "weight": "Bolder",
                                            "size": "Medium"
                                        }
                                    ]
                                },
                                {
                                    "type": "Column",
                                    "width": "stretch",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": "⭐ Recommended" if is_recommended else f"Popularity: {fw['popularity']}%",
                                            "size": "Small",
                                            "color": "Good" if is_recommended else "Accent",
                                            "horizontalAlignment": "Right"
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": fw["description"],
                            "wrap": True,
                            "size": "Small",
                            "spacing": "None"
                        },
                        {
                            "type": "TextBlock",
                            "text": " • ".join(fw["features"]),
                            "size": "Small",
                            "color": "Accent",
                            "spacing": "Small"
                        }
                    ],
                    "selectAction": {
                        "type": "Action.Submit",
                        "data": {
                            "action": "generateCode",
                            "framework": fw["key"],
                            "imageUrl": image_url,
                            "is_recommended": is_recommended
                        }
                    },
                    "spacing": "Medium"
                }
                
                body_elements.append(framework_card)
        
        # Action buttons for all frameworks
        card_actions = []
        for fw in frameworks:
            is_recommended = fw["key"] == preferred_framework
            title = fw["title"]
            if is_recommended:
                title += " ⭐"
            
            card_actions.append({
                "type": "Action.Submit",
                "title": title,
                "data": {
                    "action": "generateCode",
                    "framework": fw["key"],
                    "imageUrl": image_url,
                    "is_recommended": is_recommended
                },
                "style": "positive" if is_recommended else "default"
            })
        
        # Create adaptive card
        adaptive_card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": body_elements,
            "actions": card_actions,
            "metadata": {
                "correlation_id": get_correlation_id(),
                "theme": theme.value,
                "preferred_framework": preferred_framework,
                "communication_style": communication_style,
                "experience_level": experience_level
            }
        }
        
        return adaptive_card
    
    def create_progress_response(
        self,
        progress: ProgressIndicator,
        message: str,
        theme: ResponseTheme = ResponseTheme.INFO
    ) -> Dict[str, Any]:
        """Create progress indicator response"""
        
        # Calculate progress percentage
        progress_percent = (progress.current_step / progress.total_steps) * 100
        
        # Create progress bar visualization
        progress_blocks = int(progress_percent / 10)  # 10 blocks total
        progress_bar = "█" * progress_blocks + "░" * (10 - progress_blocks)
        
        body_elements = [
            {
                "type": "TextBlock",
                "text": f"🔄 {message}",
                "weight": "Bolder",
                "size": "Medium"
            },
            {
                "type": "TextBlock",
                "text": f"Step {progress.current_step} of {progress.total_steps}: {progress.step_title}",
                "size": "Default",
                "spacing": "Small"
            },
            {
                "type": "TextBlock",
                "text": f"`{progress_bar}` {progress_percent:.0f}%",
                "fontType": "Monospace",
                "size": "Small",
                "color": "Accent",
                "spacing": "Small"
            }
        ]
        
        # Add step description if available
        if progress.step_description:
            body_elements.append({
                "type": "TextBlock",
                "text": progress.step_description,
                "size": "Small",
                "wrap": True,
                "spacing": "Small"
            })
        
        # Add estimated time if available
        if progress.estimated_time_remaining:
            if progress.estimated_time_remaining < 60:
                time_text = f"~{progress.estimated_time_remaining}s remaining"
            else:
                minutes = progress.estimated_time_remaining // 60
                time_text = f"~{minutes}m remaining"
            
            body_elements.append({
                "type": "TextBlock",
                "text": f"⏱️ {time_text}",
                "size": "Small",
                "color": "Accent",
                "spacing": "Small"
            })
        
        adaptive_card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": body_elements,
            "metadata": {
                "correlation_id": get_correlation_id(),
                "theme": theme.value,
                "progress_percent": progress_percent,
                "current_step": progress.current_step,
                "total_steps": progress.total_steps
            }
        }
        
        return adaptive_card
    
    def create_error_response(
        self,
        error_message: str,
        error_code: Optional[str] = None,
        recovery_actions: Optional[List[InteractiveAction]] = None,
        theme: ResponseTheme = ResponseTheme.ERROR
    ) -> Dict[str, Any]:
        """Create enhanced error response with recovery options"""
        
        correlation_id = get_correlation_id()
        
        body_elements = [
            {
                "type": "TextBlock",
                "text": "❌ Something went wrong",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Attention"
            },
            {
                "type": "TextBlock",
                "text": error_message,
                "wrap": True,
                "size": "Default",
                "spacing": "Medium"
            }
        ]
        
        # Add error code if provided
        if error_code:
            body_elements.append({
                "type": "TextBlock",
                "text": f"Error Code: `{error_code}`",
                "fontType": "Monospace",
                "size": "Small",
                "color": "Accent",
                "spacing": "Small"
            })
        
        # Add correlation ID for support
        body_elements.extend([
            {
                "type": "TextBlock",
                "text": "",
                "separator": True
            },
            {
                "type": "TextBlock",
                "text": f"💡 **Need help?** Reference ID: `{correlation_id}`",
                "size": "Small",
                "color": "Accent"
            }
        ])
        
        # Create recovery actions
        card_actions = []
        
        # Default recovery actions
        default_actions = [
            InteractiveAction(
                id="retry",
                title="🔄 Try Again",
                action_type="Action.Submit",
                data={"action": "retry", "correlation_id": correlation_id},
                style="positive"
            ),
            InteractiveAction(
                id="help",
                title="❓ Get Help",
                action_type="Action.Submit",
                data={"action": "getHelp", "error_code": error_code, "correlation_id": correlation_id}
            )
        ]
        
        # Add custom recovery actions
        all_actions = (recovery_actions or []) + default_actions
        
        # Convert to adaptive card format
        for action in all_actions:
            card_action = {
                "type": action.action_type,
                "title": action.title,
                "id": action.id,
                "data": action.data
            }
            
            if action.style != "default":
                card_action["style"] = action.style
            
            card_actions.append(card_action)
        
        adaptive_card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": body_elements,
            "actions": card_actions,
            "metadata": {
                "correlation_id": correlation_id,
                "theme": theme.value,
                "error_code": error_code,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return adaptive_card
    
    def create_welcome_response(
        self,
        user_name: str,
        user_preferences: Optional[Dict[str, Any]] = None,
        theme: ResponseTheme = ResponseTheme.DEFAULT,
        show_features: bool = True
    ) -> Dict[str, Any]:
        """Create personalized welcome response"""
        
        user_prefs = user_preferences or {}
        communication_style = user_prefs.get("communication_style", "detailed")
        experience_level = user_prefs.get("experience_level", "beginner")
        
        # Personalized greeting
        if experience_level == "advanced":
            greeting = f"👋 Welcome back, {user_name}!"
            subtitle = "Ready to convert your next screenshot to production-ready code?"
        elif experience_level == "intermediate":
            greeting = f"🎨 Hi {user_name}!"
            subtitle = "I'm your Screenshot-to-Code assistant. Let's build something great!"
        else:
            greeting = f"✨ Hello {user_name}!"
            subtitle = "I'm here to help you convert UI screenshots into working code!"
        
        if communication_style == "concise":
            subtitle = "Upload a screenshot to start generating code! 📸"
        
        body_elements = [
            {
                "type": "TextBlock",
                "text": greeting,
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": subtitle,
                "wrap": True,
                "size": "Default",
                "spacing": "Small"
            }
        ]
        
        # Add features section for detailed communication style
        if show_features and communication_style == "detailed":
            body_elements.extend([
                {
                    "type": "TextBlock",
                    "text": "",
                    "separator": True
                },
                {
                    "type": "TextBlock",
                    "text": "🚀 **What I can do:**",
                    "weight": "Bolder",
                    "size": "Medium"
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {
                            "title": "⚛️ React Components",
                            "value": "Modern React with hooks and TypeScript"
                        },
                        {
                            "title": "🌐 HTML/CSS",
                            "value": "Clean, responsive web pages"
                        },
                        {
                            "title": "💚 Vue.js",
                            "value": "Vue 3 with Composition API"
                        },
                        {
                            "title": "🎨 Responsive Design",
                            "value": "Mobile-first, accessible layouts"
                        }
                    ]
                }
            ])
        
        # Quick start actions
        card_actions = [
            {
                "type": "Action.Submit",
                "title": "📸 Upload Screenshot",
                "data": {"action": "promptUpload"},
                "style": "positive"
            }
        ]
        
        # Add experience-level appropriate actions
        if experience_level in ["intermediate", "advanced"]:
            card_actions.extend([
                {
                    "type": "Action.Submit",
                    "title": "⚙️ Settings",
                    "data": {"action": "showSettings"}
                },
                {
                    "type": "Action.Submit",
                    "title": "📚 Examples",
                    "data": {"action": "showExamples"}
                }
            ])
        else:
            card_actions.append({
                "type": "Action.Submit",
                "title": "❓ How it works",
                "data": {"action": "showHelp"}
            })
        
        adaptive_card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": body_elements,
            "actions": card_actions,
            "metadata": {
                "correlation_id": get_correlation_id(),
                "theme": theme.value,
                "user_name": user_name,
                "communication_style": communication_style,
                "experience_level": experience_level
            }
        }
        
        return adaptive_card


# Global formatter instance
_rich_formatter: Optional[RichResponseFormatter] = None


def get_rich_formatter() -> RichResponseFormatter:
    """Get rich response formatter instance"""
    global _rich_formatter
    if _rich_formatter is None:
        _rich_formatter = RichResponseFormatter()
    return _rich_formatter


def detect_code_language(filename: str) -> CodeLanguage:
    """Detect code language from filename"""
    extension_map = {
        '.js': CodeLanguage.JAVASCRIPT,
        '.jsx': CodeLanguage.JSX,
        '.ts': CodeLanguage.TYPESCRIPT,
        '.tsx': CodeLanguage.TSX,
        '.html': CodeLanguage.HTML,
        '.css': CodeLanguage.CSS,
        '.scss': CodeLanguage.SCSS,
        '.less': CodeLanguage.LESS,
        '.vue': CodeLanguage.VUE,
        '.py': CodeLanguage.PYTHON,
        '.json': CodeLanguage.JSON
    }
    
    # Get file extension
    ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    return extension_map.get(ext, CodeLanguage.JAVASCRIPT)