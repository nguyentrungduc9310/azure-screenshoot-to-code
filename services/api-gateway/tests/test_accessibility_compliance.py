"""
Accessibility and Cross-Platform Compliance Testing
Testing adaptive card accessibility and cross-platform compatibility
"""
import pytest
import json
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch
from dataclasses import dataclass

from app.response.rich_formatter import (
    RichResponseFormatter, CodeBlock, InteractiveAction, ProgressIndicator,
    ResponseTheme, CodeLanguage, detect_code_language, get_rich_formatter
)


@dataclass
class AccessibilityViolation:
    """Accessibility violation details"""
    element_type: str
    violation_type: str
    severity: str  # low, medium, high, critical
    description: str
    suggestion: str
    

class AccessibilityTester:
    """Accessibility compliance testing framework"""
    
    def __init__(self):
        self.violations: List[AccessibilityViolation] = []
    
    def validate_adaptive_card_accessibility(self, card: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Validate adaptive card for accessibility compliance"""
        violations = []
        
        # Validate card structure
        violations.extend(self._validate_card_structure(card))
        
        # Validate text elements
        violations.extend(self._validate_text_elements(card))
        
        # Validate interactive elements
        violations.extend(self._validate_interactive_elements(card))
        
        # Validate images and media
        violations.extend(self._validate_media_elements(card))
        
        # Validate color and contrast
        violations.extend(self._validate_color_contrast(card))
        
        self.violations.extend(violations)
        return violations
    
    def _validate_card_structure(self, card: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Validate card structure accessibility"""
        violations = []
        
        # Check for proper schema and version
        if "$schema" not in card:
            violations.append(AccessibilityViolation(
                element_type="card",
                violation_type="missing_schema",
                severity="medium",
                description="Adaptive card missing schema declaration",
                suggestion="Add $schema property for proper screen reader interpretation"
            ))
        
        if "version" not in card or card.get("version") != "1.5":
            violations.append(AccessibilityViolation(
                element_type="card",
                violation_type="outdated_version",
                severity="low",
                description="Using older adaptive card version",
                suggestion="Use Adaptive Cards 1.5 for latest accessibility features"
            ))
        
        # Check for semantic structure
        if "body" not in card or not isinstance(card["body"], list):
            violations.append(AccessibilityViolation(
                element_type="card",
                violation_type="invalid_structure",
                severity="critical",
                description="Card missing proper body structure",
                suggestion="Ensure card has valid body array"
            ))
        
        return violations
    
    def _validate_text_elements(self, card: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Validate text elements for accessibility"""
        violations = []
        
        body_elements = card.get("body", [])
        
        for i, element in enumerate(body_elements):
            if element.get("type") == "TextBlock":
                # Check for empty text
                text_content = element.get("text", "").strip()
                if not text_content:
                    violations.append(AccessibilityViolation(
                        element_type="TextBlock",
                        violation_type="empty_text",
                        severity="medium",
                        description=f"TextBlock at index {i} has empty or missing text",
                        suggestion="Provide meaningful text content for screen readers"
                    ))
                
                # Check for proper semantic markup
                if element.get("weight") == "Bolder" and not any(
                    marker in text_content for marker in ["**", "✨", "🎯", "⚡"]
                ):
                    # Bold text without visual indicators might need semantic meaning
                    if len(text_content) > 50:  # Long bold text might be misused
                        violations.append(AccessibilityViolation(
                            element_type="TextBlock",
                            violation_type="semantic_markup",
                            severity="low",
                            description=f"Long bold text may need better semantic structure",
                            suggestion="Consider using headings or structured elements for long bold text"
                        ))
                
                # Check for color-only information
                if element.get("color") and element.get("color") != "Default":
                    if not any(indicator in text_content for indicator in ["⚠️", "❌", "✅", "ℹ️"]):
                        violations.append(AccessibilityViolation(
                            element_type="TextBlock",
                            violation_type="color_only_information",
                            severity="medium",
                            description=f"Text relies on color alone for meaning",
                            suggestion="Add visual indicators or text cues alongside color"
                        ))
        
        return violations
    
    def _validate_interactive_elements(self, card: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Validate interactive elements accessibility"""
        violations = []
        
        actions = card.get("actions", [])
        
        for i, action in enumerate(actions):
            # Check for accessible action titles
            title = action.get("title", "").strip()
            if not title:
                violations.append(AccessibilityViolation(
                    element_type="Action",
                    violation_type="missing_title",
                    severity="critical",
                    description=f"Action at index {i} missing accessible title",
                    suggestion="Provide descriptive title for screen reader users"
                ))
            
            # Check for descriptive action titles
            if title and len(title.split()) < 2:
                # Single word titles might not be descriptive enough
                violations.append(AccessibilityViolation(
                    element_type="Action",
                    violation_type="non_descriptive_title",
                    severity="medium",
                    description=f"Action title '{title}' may not be descriptive enough",
                    suggestion="Use descriptive action titles like 'Generate Code' instead of 'Generate'"
                ))
            
            # Check for keyboard accessibility
            action_type = action.get("type", "")
            if action_type == "Action.OpenUrl":
                url = action.get("url", "")
                if not url:
                    violations.append(AccessibilityViolation(
                        element_type="Action",
                        violation_type="missing_url",
                        severity="high",
                        description=f"OpenUrl action missing URL",
                        suggestion="Provide valid URL for OpenUrl actions"
                    ))
                elif not url.startswith(("http://", "https://")):
                    violations.append(AccessibilityViolation(
                        element_type="Action",
                        violation_type="invalid_url",
                        severity="medium",
                        description=f"Action URL may not be valid: {url}",
                        suggestion="Use absolute URLs starting with http:// or https://"
                    ))
        
        # Check for body interactive elements
        body_elements = card.get("body", [])
        for element in body_elements:
            if element.get("type") == "Container" and "selectAction" in element:
                select_action = element["selectAction"]
                if not select_action.get("data"):
                    violations.append(AccessibilityViolation(
                        element_type="Container",
                        violation_type="missing_action_data",
                        severity="medium",
                        description="Interactive container missing action data",
                        suggestion="Provide action data for interactive containers"
                    ))
        
        return violations
    
    def _validate_media_elements(self, card: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Validate media elements accessibility"""
        violations = []
        
        body_elements = card.get("body", [])
        
        for i, element in enumerate(body_elements):
            if element.get("type") == "Image":
                # Check for alt text
                alt_text = element.get("altText", "").strip()
                if not alt_text:
                    violations.append(AccessibilityViolation(
                        element_type="Image",
                        violation_type="missing_alt_text",
                        severity="high",
                        description=f"Image at index {i} missing alt text",
                        suggestion="Provide descriptive alt text for all images"
                    ))
                elif len(alt_text) < 5:
                    violations.append(AccessibilityViolation(
                        element_type="Image",
                        violation_type="insufficient_alt_text",
                        severity="medium",
                        description=f"Image alt text too brief: '{alt_text}'",
                        suggestion="Provide more descriptive alt text"
                    ))
                
                # Check for valid image URL
                image_url = element.get("url", "")
                if not image_url or not image_url.startswith(("http://", "https://", "data:")):
                    violations.append(AccessibilityViolation(
                        element_type="Image",
                        violation_type="invalid_image_url",
                        severity="medium",
                        description=f"Image has invalid or missing URL",
                        suggestion="Provide valid image URL"
                    ))
        
        return violations
    
    def _validate_color_contrast(self, card: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Validate color contrast and visual accessibility"""
        violations = []
        
        body_elements = card.get("body", [])
        
        # Check for theme consistency
        theme = card.get("metadata", {}).get("theme", "default")
        
        # Count elements using color
        colored_elements = 0
        total_text_elements = 0
        
        for element in body_elements:
            if element.get("type") == "TextBlock":
                total_text_elements += 1
                if element.get("color") and element.get("color") != "Default":
                    colored_elements += 1
        
        # If too many elements rely on color, it might be problematic
        if total_text_elements > 0:
            color_ratio = colored_elements / total_text_elements
            if color_ratio > 0.5:  # More than half of text uses color
                violations.append(AccessibilityViolation(
                    element_type="card",
                    violation_type="excessive_color_dependency",
                    severity="medium",
                    description=f"Too many elements rely on color ({color_ratio:.1%})",
                    suggestion="Use icons, text indicators, or structure in addition to color"
                ))
        
        # Check for container styles that might affect contrast
        for element in body_elements:
            if element.get("type") == "Container" and element.get("style") == "emphasis":
                # Emphasis containers should have sufficient content to justify styling
                items = element.get("items", [])
                if len(items) < 2:
                    violations.append(AccessibilityViolation(
                        element_type="Container",
                        violation_type="unnecessary_emphasis",
                        severity="low",
                        description="Emphasis container with minimal content",
                        suggestion="Use emphasis styling only for important content groups"
                    ))
        
        return violations
    
    def generate_accessibility_report(self) -> Dict[str, Any]:
        """Generate accessibility compliance report"""
        violations_by_severity = {
            "critical": [v for v in self.violations if v.severity == "critical"],
            "high": [v for v in self.violations if v.severity == "high"],
            "medium": [v for v in self.violations if v.severity == "medium"],
            "low": [v for v in self.violations if v.severity == "low"]
        }
        
        total_violations = len(self.violations)
        critical_count = len(violations_by_severity["critical"])
        high_count = len(violations_by_severity["high"])
        
        # Calculate compliance score
        compliance_score = max(0, 100 - (critical_count * 25 + high_count * 10 + 
                                        len(violations_by_severity["medium"]) * 5 + 
                                        len(violations_by_severity["low"]) * 2))
        
        return {
            "compliance_score": compliance_score,
            "total_violations": total_violations,
            "violations_by_severity": {
                severity: [
                    {
                        "element_type": v.element_type,
                        "violation_type": v.violation_type,
                        "description": v.description,
                        "suggestion": v.suggestion
                    }
                    for v in violations
                ]
                for severity, violations in violations_by_severity.items()
            },
            "recommendations": self._generate_recommendations(violations_by_severity)
        }
    
    def _generate_recommendations(self, violations_by_severity: Dict[str, List]) -> List[str]:
        """Generate accessibility improvement recommendations"""
        recommendations = []
        
        if violations_by_severity["critical"]:
            recommendations.append("Address critical accessibility issues immediately for basic screen reader compatibility")
        
        if violations_by_severity["high"]:
            recommendations.append("Fix high-priority issues to improve user experience for assistive technology users")
        
        if len(violations_by_severity["medium"]) > 5:
            recommendations.append("Consider addressing medium-priority issues to enhance overall accessibility")
        
        # Specific recommendations based on violation patterns
        violation_types = [v.violation_type for violations in violations_by_severity.values() for v in violations]
        
        if violation_types.count("missing_alt_text") > 0:
            recommendations.append("Implement comprehensive alt text for all images")
        
        if violation_types.count("color_only_information") > 2:
            recommendations.append("Reduce reliance on color-only information by adding text indicators and icons")
        
        if violation_types.count("non_descriptive_title") > 2:
            recommendations.append("Improve action button descriptions for better screen reader experience")
        
        return recommendations


# Test fixtures
@pytest.fixture
def accessibility_tester():
    """Create accessibility tester instance"""
    return AccessibilityTester()


@pytest.fixture
def formatter():
    """Create rich formatter instance"""
    return RichResponseFormatter()


@pytest.fixture
def sample_code_blocks():
    """Sample code blocks for testing"""
    return [
        CodeBlock(
            filename="App.jsx",
            content="const App = () => {\n  return <div>Hello World</div>;\n};",
            language=CodeLanguage.JSX
        ),
        CodeBlock(
            filename="styles.css",
            content=".app {\n  color: blue;\n  font-size: 16px;\n}",
            language=CodeLanguage.CSS
        )
    ]


class TestAdaptiveCardAccessibility:
    """Test adaptive card accessibility compliance"""
    
    def test_code_generation_response_accessibility(self, accessibility_tester, formatter, sample_code_blocks):
        """Test code generation response accessibility"""
        
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="react",
            processing_time_ms=1500.0,
            theme=ResponseTheme.SUCCESS
        )
        
        violations = accessibility_tester.validate_adaptive_card_accessibility(response)
        
        # Check for critical accessibility violations
        critical_violations = [v for v in violations if v.severity == "critical"]
        assert len(critical_violations) == 0, f"Critical accessibility violations found: {[v.description for v in critical_violations]}"
        
        # Check for high-priority violations
        high_violations = [v for v in violations if v.severity == "high"]
        assert len(high_violations) <= 1, f"Too many high-priority accessibility violations: {[v.description for v in high_violations]}"
        
        # Generate report
        report = accessibility_tester.generate_accessibility_report()
        assert report["compliance_score"] >= 85, f"Accessibility compliance score too low: {report['compliance_score']}"
    
    def test_framework_selection_response_accessibility(self, accessibility_tester, formatter):
        """Test framework selection response accessibility"""
        
        user_preferences = {
            "preferred_framework": "react",
            "communication_style": "detailed",
            "experience_level": "intermediate"
        }
        
        response = formatter.create_framework_selection_response(
            image_url="https://example.com/screenshot.png",
            user_preferences=user_preferences,
            theme=ResponseTheme.DEFAULT
        )
        
        violations = accessibility_tester.validate_adaptive_card_accessibility(response)
        
        # Framework selection should be highly accessible
        critical_violations = [v for v in violations if v.severity == "critical"]
        assert len(critical_violations) == 0, "Framework selection must not have critical accessibility issues"
        
        # Check that image has alt text
        image_violations = [v for v in violations if v.element_type == "Image" and v.violation_type == "missing_alt_text"]
        assert len(image_violations) == 0, "Screenshot image must have alt text"
        
        # Check that actions are accessible
        action_violations = [v for v in violations if v.element_type == "Action" and v.severity in ["critical", "high"]]
        assert len(action_violations) == 0, "Framework selection actions must be accessible"
    
    def test_progress_response_accessibility(self, accessibility_tester, formatter):
        """Test progress response accessibility"""
        
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
        
        violations = accessibility_tester.validate_adaptive_card_accessibility(response)
        
        # Progress indicators should be accessible to screen readers
        critical_violations = [v for v in violations if v.severity == "critical"]
        assert len(critical_violations) == 0, "Progress indicators must be accessible"
        
        # Check that progress information is conveyed accessibly
        text_content = str(response.get("body", []))
        assert "Step 3 of 5" in text_content, "Progress step information must be accessible"
        assert "45" in text_content, "Time remaining information must be accessible"
    
    def test_error_response_accessibility(self, accessibility_tester, formatter):
        """Test error response accessibility"""
        
        recovery_actions = [
            InteractiveAction(
                id="custom_retry",
                title="🔧 Try Different Approach",
                action_type="Action.Submit",
                data={"action": "customRetry"}
            )
        ]
        
        response = formatter.create_error_response(
            error_message="Failed to process image due to invalid format",
            error_code="IMG_001",
            recovery_actions=recovery_actions,
            theme=ResponseTheme.ERROR
        )
        
        violations = accessibility_tester.validate_adaptive_card_accessibility(response)
        
        # Error responses must be highly accessible
        critical_violations = [v for v in violations if v.severity == "critical"]
        assert len(critical_violations) == 0, "Error responses must be fully accessible"
        
        # Check that error information is properly conveyed
        high_violations = [v for v in violations if v.severity == "high"]
        assert len(high_violations) <= 1, "Error responses should minimize high-priority accessibility issues"
        
        # Error recovery actions should be accessible
        action_violations = [v for v in violations if v.element_type == "Action"]
        action_critical = [v for v in action_violations if v.severity == "critical"]
        assert len(action_critical) == 0, "Error recovery actions must be accessible"
    
    def test_welcome_response_accessibility(self, accessibility_tester, formatter):
        """Test welcome response accessibility"""
        
        user_preferences = {
            "communication_style": "detailed",
            "experience_level": "beginner"
        }
        
        response = formatter.create_welcome_response(
            user_name="Accessibility Test User",
            user_preferences=user_preferences,
            theme=ResponseTheme.DEFAULT,
            show_features=True
        )
        
        violations = accessibility_tester.validate_adaptive_card_accessibility(response)
        
        # Welcome responses should be very accessible for new users
        critical_violations = [v for v in violations if v.severity == "critical"]
        assert len(critical_violations) == 0, "Welcome responses must be fully accessible"
        
        # Check for beginner-friendly accessibility
        high_violations = [v for v in violations if v.severity == "high"]
        assert len(high_violations) == 0, "Welcome responses for beginners must have no high-priority accessibility issues"
        
        # Generate detailed accessibility report
        report = accessibility_tester.generate_accessibility_report()
        assert report["compliance_score"] >= 90, "Welcome responses should have high accessibility compliance"


class TestCrossPlatformCompatibility:
    """Test cross-platform adaptive card compatibility"""
    
    def test_adaptive_card_schema_compliance(self, formatter, sample_code_blocks):
        """Test adaptive card schema compliance across platforms"""
        
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="react",
            processing_time_ms=1000.0
        )
        
        # Check schema compliance
        assert response.get("$schema") == "http://adaptivecards.io/schemas/adaptive-card.json"
        assert response.get("version") == "1.5"
        assert response.get("type") == "AdaptiveCard"
        
        # Validate body structure
        body = response.get("body", [])
        assert isinstance(body, list), "Body must be an array"
        assert len(body) > 0, "Body must contain elements"
        
        # Validate all body elements have required type
        for element in body:
            assert "type" in element, "All body elements must have type"
            assert element["type"].startswith(("TextBlock", "ColumnSet", "Container", "Image", "FactSet"))
        
        # Validate actions structure
        actions = response.get("actions", [])
        for action in actions:
            assert "type" in action, "All actions must have type"
            assert "title" in action, "All actions must have title"
            assert action["type"].startswith("Action.")
    
    def test_microsoft_teams_compatibility(self, formatter):
        """Test Microsoft Teams specific compatibility"""
        
        # Teams has specific requirements for adaptive cards
        response = formatter.create_framework_selection_response(
            image_url="https://example.com/screenshot.png"
        )
        
        # Check Teams-compatible features
        assert response.get("version") == "1.5", "Teams supports Adaptive Cards 1.5"
        
        # Check for Teams-compatible action types
        actions = response.get("actions", [])
        for action in actions:
            action_type = action.get("type")
            assert action_type in [
                "Action.Submit", "Action.OpenUrl", "Action.ShowCard", "Action.ToggleVisibility"
            ], f"Action type {action_type} may not be compatible with Teams"
        
        # Check for Teams-compatible elements
        body = response.get("body", [])
        for element in body:
            element_type = element.get("type")
            # Teams supports most standard elements, check for unsupported ones
            unsupported_elements = ["Media", "ActionSet"]  # Example unsupported elements
            assert element_type not in unsupported_elements, f"Element {element_type} not supported in Teams"
    
    def test_web_chat_compatibility(self, formatter, sample_code_blocks):
        """Test web chat client compatibility"""
        
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="vue",
            processing_time_ms=800.0
        )
        
        # Web chat has broader support but some limitations
        body = response.get("body", [])
        
        # Check for web-compatible styling
        for element in body:
            if element.get("type") == "TextBlock":
                # Check font type compatibility
                font_type = element.get("fontType")
                if font_type:
                    assert font_type in ["Default", "Monospace"], f"FontType {font_type} may not render consistently in web"
                
                # Check size compatibility
                size = element.get("size")
                if size:
                    assert size in ["Small", "Default", "Medium", "Large", "ExtraLarge"], f"Size {size} may not be supported"
    
    def test_bot_framework_composer_compatibility(self, formatter):
        """Test Bot Framework Composer compatibility"""
        
        progress = ProgressIndicator(
            current_step=2,
            total_steps=4,
            step_title="Processing",
            step_description="Analyzing image content"
        )
        
        response = formatter.create_progress_response(
            progress=progress,
            message="Working on your request"
        )
        
        # Bot Framework Composer specific requirements
        assert "metadata" in response, "Metadata helpful for Bot Framework tracking"
        
        metadata = response["metadata"]
        assert "correlation_id" in metadata, "Correlation ID important for Bot Framework flow tracking"
        
        # Check for Composer-friendly structure
        body = response.get("body", [])
        text_blocks = [e for e in body if e.get("type") == "TextBlock"]
        assert len(text_blocks) > 0, "At least one text block needed for Composer compatibility"
    
    def test_mobile_platform_compatibility(self, formatter):
        """Test mobile platform rendering compatibility"""
        
        user_preferences = {"communication_style": "concise"}  # Mobile-friendly
        
        response = formatter.create_framework_selection_response(
            image_url="https://example.com/mobile-screenshot.png",
            user_preferences=user_preferences
        )
        
        # Mobile-specific compatibility checks
        body = response.get("body", [])
        
        # Check for mobile-friendly image sizing
        images = [e for e in body if e.get("type") == "Image"]
        for image in images:
            size = image.get("size", "Auto")
            assert size in ["Auto", "Small", "Medium", "Large"], f"Image size {size} should be mobile-compatible"
        
        # Check for mobile-friendly text
        text_blocks = [e for e in body if e.get("type") == "TextBlock"]
        for text_block in text_blocks:
            text = text_block.get("text", "")
            # Very long text blocks might not render well on mobile
            assert len(text) <= 500, f"Text block too long for mobile: {len(text)} characters"
        
        # Check for mobile-friendly actions
        actions = response.get("actions", [])
        assert len(actions) <= 4, f"Too many actions for mobile interface: {len(actions)}"


class TestScreenReaderCompatibility:
    """Test screen reader specific compatibility"""
    
    def test_screen_reader_text_flow(self, formatter, sample_code_blocks):
        """Test that content flows logically for screen readers"""
        
        response = formatter.create_code_generation_response(
            code_blocks=sample_code_blocks,
            framework="react",
            processing_time_ms=1200.0
        )
        
        # Extract text content in screen reader order
        body = response.get("body", [])
        text_content = []
        
        for element in body:
            if element.get("type") == "TextBlock":
                text_content.append(element.get("text", ""))
            elif element.get("type") == "ColumnSet":
                # Extract text from columns in order
                columns = element.get("columns", [])
                for column in columns:
                    items = column.get("items", [])
                    for item in items:
                        if item.get("type") == "TextBlock":
                            text_content.append(item.get("text", ""))
        
        # Join all text content
        full_text = " ".join(text_content)
        
        # Check for logical flow
        assert "generated" in full_text.lower(), "Should mention code generation"
        assert any(filename in full_text for filename in ["App.jsx", "styles.css"]), "Should mention generated files"
        
        # Check for announcement patterns that work well with screen readers
        assert any(indicator in full_text for indicator in ["✨", "⚡", "📄"]), "Should have audio-friendly indicators"
    
    def test_screen_reader_action_descriptions(self, formatter):
        """Test that actions are properly described for screen readers"""
        
        recovery_actions = [
            InteractiveAction(
                id="detailed_retry",
                title="🔄 Try Again with Different Settings",
                action_type="Action.Submit",
                data={"action": "retryWithSettings"}
            )
        ]
        
        response = formatter.create_error_response(
            error_message="The image format is not supported. Please use PNG, JPG, or GIF format.",
            error_code="UNSUPPORTED_FORMAT",
            recovery_actions=recovery_actions
        )
        
        actions = response.get("actions", [])
        
        for action in actions:
            title = action.get("title", "")
            
            # Check that action titles are descriptive enough for screen readers
            assert len(title.split()) >= 2, f"Action title should be descriptive: '{title}'"
            
            # Check that emoji doesn't interfere with screen reader comprehension
            if any(emoji in title for emoji in ["🔄", "❓", "💾", "👀"]):
                # Should have text after emoji
                text_after_emoji = title.split()[-1] if title.split() else ""
                assert len(text_after_emoji) >= 3, f"Should have descriptive text after emoji: '{title}'"
    
    def test_progress_announcement_compatibility(self, formatter):
        """Test progress announcements for screen readers"""
        
        progress = ProgressIndicator(
            current_step=3,
            total_steps=5,
            step_title="Optimizing code",
            step_description="Applying best practices and performance optimizations",
            estimated_time_remaining=30
        )
        
        response = formatter.create_progress_response(
            progress=progress,
            message="Finalizing your code generation"
        )
        
        # Extract progress information for screen reader
        body = response.get("body", [])
        progress_text = []
        
        for element in body:
            if element.get("type") == "TextBlock":
                text = element.get("text", "")
                progress_text.append(text)
        
        full_progress_text = " ".join(progress_text)
        
        # Check for screen reader friendly progress information
        assert "Step 3 of 5" in full_progress_text, "Step information should be clearly announced"
        assert "Optimizing code" in full_progress_text, "Current step should be announced"
        assert "30" in full_progress_text, "Time remaining should be available to screen reader"
        
        # Check that progress bar is supplemented with text
        has_progress_bar = any("█" in text or "░" in text for text in progress_text)
        has_percentage = any("%" in text for text in progress_text)
        
        if has_progress_bar:
            assert has_percentage, "Visual progress bar should be supplemented with percentage text"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])