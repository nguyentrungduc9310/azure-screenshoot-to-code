"""
Test cases for Rich Response Formatter
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.response.rich_formatter import (
    RichResponseFormatter, CodeBlock, InteractiveAction, ProgressIndicator,
    ResponseTheme, CodeLanguage, detect_code_language, get_rich_formatter
)


# Test fixtures
@pytest.fixture
def formatter():
    """Create formatter instance"""
    return RichResponseFormatter()


@pytest.fixture
def sample_code_blocks():
    """Sample code blocks for testing"""
    return [
        CodeBlock(
            filename="App.jsx",
            content="const App = () => {\n  return <div>Hello World</div>;\n};",
            language=CodeLanguage.JSX,
            line_numbers=True
        ),
        CodeBlock(
            filename="App.css",
            content=".app {\n  color: blue;\n  font-size: 16px;\n}",
            language=CodeLanguage.CSS,
            line_numbers=True
        )
    ]


@pytest.fixture
def sample_user_preferences():
    """Sample user preferences"""
    return {
        "preferred_framework": "react",
        "communication_style": "detailed",
        "experience_level": "intermediate"
    }


class TestCodeBlock:
    """Test CodeBlock functionality"""
    
    def test_code_block_creation(self):
        """Test creating code block"""
        code_block = CodeBlock(
            filename="test.js",
            content="console.log('hello');",
            language=CodeLanguage.JAVASCRIPT
        )
        
        assert code_block.filename == "test.js"
        assert code_block.language == CodeLanguage.JAVASCRIPT
        assert code_block.line_numbers is True
        assert code_block.collapsible is False
    
    def test_truncate_for_display(self):
        """Test code truncation"""
        long_content = "\n".join([f"line {i}" for i in range(30)])
        code_block = CodeBlock(
            filename="long.js",
            content=long_content,
            language=CodeLanguage.JAVASCRIPT
        )
        
        truncated = code_block.truncate_for_display(max_lines=10)
        lines = truncated.split('\n')
        
        assert len(lines) <= 11  # 10 lines + truncation message
        assert "more lines" in truncated
    
    def test_get_language_icon(self):
        """Test language icon mapping"""
        react_block = CodeBlock("App.jsx", "content", CodeLanguage.JSX)
        assert react_block.get_language_icon() == "⚛️"
        
        css_block = CodeBlock("style.css", "content", CodeLanguage.CSS)
        assert css_block.get_language_icon() == "🎨"
        
        python_block = CodeBlock("main.py", "content", CodeLanguage.PYTHON)
        assert python_block.get_language_icon() == "🐍"


class TestLanguageDetection:
    """Test code language detection"""
    
    def test_detect_javascript(self):
        """Test JavaScript detection"""
        assert detect_code_language("app.js") == CodeLanguage.JAVASCRIPT
        assert detect_code_language("script.jsx") == CodeLanguage.JSX
        assert detect_code_language("main.ts") == CodeLanguage.TYPESCRIPT
        assert detect_code_language("component.tsx") == CodeLanguage.TSX
    
    def test_detect_web_languages(self):
        """Test web language detection"""
        assert detect_code_language("index.html") == CodeLanguage.HTML
        assert detect_code_language("style.css") == CodeLanguage.CSS
        assert detect_code_language("main.scss") == CodeLanguage.SCSS
        assert detect_code_language("theme.less") == CodeLanguage.LESS
    
    def test_detect_other_languages(self):
        """Test other language detection"""
        assert detect_code_language("App.vue") == CodeLanguage.VUE
        assert detect_code_language("main.py") == CodeLanguage.PYTHON
        assert detect_code_language("config.json") == CodeLanguage.JSON
    
    def test_unknown_extension_fallback(self):
        """Test fallback for unknown extensions"""
        assert detect_code_language("unknown.xyz") == CodeLanguage.JAVASCRIPT
        assert detect_code_language("no_extension") == CodeLanguage.JAVASCRIPT


class TestInteractiveAction:
    """Test InteractiveAction functionality"""
    
    def test_action_creation(self):
        """Test creating interactive action"""
        action = InteractiveAction(
            id="test_action",
            title="Test Action",
            action_type="Action.Submit",
            data={"key": "value"},
            style="positive",
            is_primary=True
        )
        
        assert action.id == "test_action"
        assert action.title == "Test Action"
        assert action.action_type == "Action.Submit"
        assert action.data == {"key": "value"}
        assert action.style == "positive"
        assert action.is_primary is True


class TestProgressIndicator:
    """Test ProgressIndicator functionality"""
    
    def test_progress_creation(self):
        """Test creating progress indicator"""
        progress = ProgressIndicator(
            current_step=2,
            total_steps=5,
            step_title="Processing image",
            step_description="Analyzing screenshot content",
            estimated_time_remaining=30
        )
        
        assert progress.current_step == 2
        assert progress.total_steps == 5
        assert progress.step_title == "Processing image"
        assert progress.estimated_time_remaining == 30


class TestRichResponseFormatter:
    """Test RichResponseFormatter functionality"""
    
    def test_formatter_initialization(self, formatter):
        """Test formatter initialization"""
        assert formatter is not None
        assert ResponseTheme.DEFAULT in formatter.theme_colors
        assert ResponseTheme.SUCCESS in formatter.theme_colors
        assert ResponseTheme.ERROR in formatter.theme_colors
    
    def test_code_generation_response(self, formatter, sample_code_blocks, sample_user_preferences):
        """Test code generation response creation"""
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="react",
            processing_time_ms=1500.0,
            theme=ResponseTheme.SUCCESS,
            user_preferences=sample_user_preferences
        )
        
        assert response["type"] == "AdaptiveCard"
        assert response["version"] == "1.5"
        assert "body" in response
        assert "actions" in response
        assert "metadata" in response
        
        # Check metadata
        metadata = response["metadata"]
        assert metadata["framework"] == "react"
        assert metadata["theme"] == "success"
        assert metadata["code_blocks_count"] == 2
        
        # Check body contains code information
        body_text = str(response["body"])
        assert "REACT Code Generated!" in body_text or "Code Generated!" in body_text
        assert "App.jsx" in body_text
        assert "App.css" in body_text
    
    def test_code_generation_response_concise_style(self, formatter, sample_code_blocks):
        """Test code generation response with concise communication style"""
        user_prefs = {"communication_style": "concise"}
        
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="vue",
            processing_time_ms=800.0,
            user_preferences=user_prefs
        )
        
        # Should be more concise - check that detailed performance info is limited
        body_text = str(response["body"])
        assert "VUE" in body_text or "Ready!" in body_text
    
    def test_framework_selection_response(self, formatter, sample_user_preferences):
        """Test framework selection response creation"""
        response = formatter.create_framework_selection_response(
            image_url="https://example.com/screenshot.png",
            user_preferences=sample_user_preferences,
            theme=ResponseTheme.DEFAULT
        )
        
        assert response["type"] == "AdaptiveCard"
        assert "body" in response
        assert "actions" in response
        
        # Check metadata
        metadata = response["metadata"]
        assert metadata["preferred_framework"] == "react"
        assert metadata["communication_style"] == "detailed"
        assert metadata["experience_level"] == "intermediate"
        
        # Check actions contain framework options
        actions = response["actions"]
        framework_actions = [action for action in actions if action.get("data", {}).get("framework")]
        assert len(framework_actions) > 0
        
        # React should be marked as recommended
        react_action = next((a for a in actions if a.get("data", {}).get("framework") == "react"), None)
        assert react_action is not None
        assert "⭐" in react_action["title"] or "Recommended" in react_action["title"]
    
    def test_framework_selection_advanced_user(self, formatter):
        """Test framework selection for advanced user"""
        user_prefs = {
            "preferred_framework": "angular",
            "communication_style": "concise",
            "experience_level": "advanced"
        }
        
        response = formatter.create_framework_selection_response(
            image_url="https://example.com/test.png",
            user_preferences=user_prefs
        )
        
        # Should be more concise for advanced users
        body_text = str(response["body"])
        greeting_found = any(greeting in body_text for greeting in ["Ready to generate", "Choose framework"])
        assert greeting_found
        
        # Angular should be recommended
        metadata = response["metadata"]
        assert metadata["preferred_framework"] == "angular"
    
    def test_progress_response(self, formatter):
        """Test progress response creation"""
        progress = ProgressIndicator(
            current_step=3,
            total_steps=5,
            step_title="Generating code",
            step_description="Creating React components",
            estimated_time_remaining=45
        )
        
        response = formatter.create_progress_response(
            progress=progress,
            message="Processing your screenshot",
            theme=ResponseTheme.INFO
        )
        
        assert response["type"] == "AdaptiveCard"
        assert "body" in response
        
        # Check metadata
        metadata = response["metadata"]
        assert metadata["progress_percent"] == 60.0
        assert metadata["current_step"] == 3
        assert metadata["total_steps"] == 5
        
        # Check progress visualization
        body_text = str(response["body"])
        assert "Step 3 of 5" in body_text
        assert "60%" in body_text or "█" in body_text  # Progress bar
        assert "45s remaining" in body_text or "~45s" in body_text
    
    def test_error_response(self, formatter):
        """Test error response creation"""
        recovery_actions = [
            InteractiveAction(
                id="custom_retry",
                title="🔧 Custom Fix",
                action_type="Action.Submit",
                data={"action": "customFix"}
            )
        ]
        
        response = formatter.create_error_response(
            error_message="Failed to process image due to invalid format",
            error_code="IMG_001",
            recovery_actions=recovery_actions,
            theme=ResponseTheme.ERROR
        )
        
        assert response["type"] == "AdaptiveCard"
        assert "body" in response
        assert "actions" in response
        
        # Check error information
        body_text = str(response["body"])
        assert "Something went wrong" in body_text
        assert "Failed to process image" in body_text
        assert "IMG_001" in body_text
        
        # Check actions include both custom and default recovery options
        actions = response["actions"]
        action_titles = [action["title"] for action in actions]
        assert any("Custom Fix" in title for title in action_titles)
        assert any("Try Again" in title for title in action_titles)
        assert any("Get Help" in title for title in action_titles)
    
    def test_welcome_response(self, formatter):
        """Test welcome response creation"""
        user_prefs = {
            "communication_style": "detailed",
            "experience_level": "beginner"
        }
        
        response = formatter.create_welcome_response(
            user_name="Alice",
            user_preferences=user_prefs,
            theme=ResponseTheme.DEFAULT,
            show_features=True
        )
        
        assert response["type"] == "AdaptiveCard"
        assert "body" in response
        assert "actions" in response
        
        # Check personalization
        body_text = str(response["body"])
        assert "Alice" in body_text
        
        # Should include features for detailed style
        assert "What I can do" in body_text or "React Components" in body_text
        
        # Check actions appropriate for beginner
        actions = response["actions"]
        action_titles = [action["title"] for action in actions]
        assert any("Upload Screenshot" in title for title in action_titles)
        assert any("How it works" in title for title in action_titles)
    
    def test_welcome_response_advanced_user(self, formatter):
        """Test welcome response for advanced user"""
        user_prefs = {
            "communication_style": "concise",
            "experience_level": "advanced"
        }
        
        response = formatter.create_welcome_response(
            user_name="Bob",
            user_preferences=user_prefs,
            show_features=False
        )
        
        # Should be more concise and have advanced options
        actions = response["actions"]
        action_titles = [action["title"] for action in actions]
        assert any("Settings" in title or "Examples" in title for title in action_titles)
    
    def test_response_themes(self, formatter, sample_code_blocks):
        """Test different response themes"""
        themes_to_test = [ResponseTheme.SUCCESS, ResponseTheme.ERROR, ResponseTheme.WARNING, ResponseTheme.PREMIUM]
        
        for theme in themes_to_test:
            response = formatter.create_code_generation_response(
                code_blocks=sample_code_blocks,
                framework="react",
                processing_time_ms=1000.0,
                theme=theme
            )
            
            assert response["metadata"]["theme"] == theme.value


class TestFormatterSingleton:
    """Test formatter singleton functionality"""
    
    def test_get_rich_formatter_singleton(self):
        """Test that get_rich_formatter returns same instance"""
        formatter1 = get_rich_formatter()
        formatter2 = get_rich_formatter()
        
        assert formatter1 is formatter2
        assert isinstance(formatter1, RichResponseFormatter)


class TestAdaptiveCardValidation:
    """Test adaptive card structure validation"""
    
    def test_adaptive_card_structure(self, formatter, sample_code_blocks):
        """Test that generated cards have valid adaptive card structure"""
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="react",
            processing_time_ms=1000.0
        )
        
        # Check required adaptive card fields
        assert response["type"] == "AdaptiveCard"
        assert "$schema" in response
        assert "version" in response
        assert "body" in response
        assert isinstance(response["body"], list)
        
        # Check actions structure
        if "actions" in response:
            for action in response["actions"]:
                assert "type" in action
                assert "title" in action
    
    def test_metadata_consistency(self, formatter):
        """Test that metadata is consistently included"""
        # Test different response types
        responses = [
            formatter.create_welcome_response("Test User"),
            formatter.create_framework_selection_response("https://example.com/test.png"),
            formatter.create_error_response("Test error"),
            formatter.create_progress_response(
                ProgressIndicator(1, 3, "Test step"),
                "Testing"
            )
        ]
        
        for response in responses:
            assert "metadata" in response
            assert "correlation_id" in response["metadata"]
            assert "theme" in response["metadata"]


if __name__ == "__main__":
    pytest.main([__file__])