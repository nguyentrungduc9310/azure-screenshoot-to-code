"""
Copilot Studio Integration Routes
FastAPI endpoints for Microsoft Copilot Studio webhook integration
"""
import json
import hmac
import hashlib
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import structlog

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import set_correlation_id, get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger

from app.services.copilot_integration_service import (
    CopilotIntegrationService, get_copilot_service, Framework
)
from app.conversation.conversation_manager import (
    get_conversation_manager, ConversationState, MessageType, UserIntent
)
from app.response.rich_formatter import (
    get_rich_formatter, CodeBlock, detect_code_language, InteractiveAction,
    ResponseTheme, ProgressIndicator
)


# Request/Response Models for Copilot Studio
class CopilotStudioActivity(BaseModel):
    """Activity model from Copilot Studio"""
    type: str = Field(..., description="Activity type (message, invoke, etc.)")
    id: str = Field(..., description="Unique activity ID")
    timestamp: str = Field(..., description="Activity timestamp")
    from_property: Dict[str, Any] = Field(alias="from", default_factory=dict)
    recipient: Dict[str, Any] = Field(default_factory=dict)
    conversation: Dict[str, Any] = Field(default_factory=dict)
    text: Optional[str] = Field(None, description="Message text content")
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    channel_data: Optional[Dict[str, Any]] = Field(None, alias="channelData")
    value: Optional[Dict[str, Any]] = Field(None, description="Action payload")
    

class CopilotStudioRequest(BaseModel):
    """Main request from Copilot Studio"""
    activities: List[CopilotStudioActivity] = Field(..., description="List of activities")
    watermark: Optional[str] = Field(None, description="Conversation watermark")
    

class CopilotStudioResponse(BaseModel):
    """Response to Copilot Studio"""
    type: str = Field(..., description="Response type")
    text: Optional[str] = Field(None, description="Response text")
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_actions: Optional[Dict[str, Any]] = Field(None, alias="suggestedActions")
    input_hint: str = Field("acceptingInput", alias="inputHint")
    

class AttachmentContent(BaseModel):
    """Attachment content for rich responses"""
    type: str = Field(..., description="Content type")
    body: List[Dict[str, Any]] = Field(..., description="Content body")
    

class AdaptiveCard(BaseModel):
    """Adaptive Card for rich responses"""
    type: str = Field("AdaptiveCard", description="Card type")
    schema: str = Field("http://adaptivecards.io/schemas/adaptive-card.json", alias="$schema")
    version: str = Field("1.3", description="Card version")
    body: List[Dict[str, Any]] = Field(..., description="Card body elements")
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    

class CodeGenerationRequest(BaseModel):
    """Internal request for code generation"""
    image_url: Optional[str] = Field(None, description="Image URL for processing")
    image_data: Optional[str] = Field(None, description="Base64 image data")
    framework: str = Field("react", description="Target framework")
    requirements: Optional[str] = Field(None, description="Additional requirements")
    user_id: str = Field(..., description="User identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    

# Create router
router = APIRouter(prefix="/copilot-studio", tags=["copilot-studio"])

# Initialize logger
logger = StructuredLogger(service_name="copilot-studio-connector")


class CopilotStudioWebhookHandler:
    """Handler for Copilot Studio webhook operations with advanced conversation management"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.conversation_manager = None  # Will be initialized async
        self.supported_activities = {
            "message": self._handle_message_activity,
            "invoke": self._handle_invoke_activity,
            "event": self._handle_event_activity
        }
    
    async def _ensure_conversation_manager(self):
        """Ensure conversation manager is initialized"""
        if self.conversation_manager is None:
            self.conversation_manager = await get_conversation_manager()
        return self.conversation_manager
        
    async def process_webhook(self, request: CopilotStudioRequest, 
                            user_info: Dict[str, Any]) -> List[CopilotStudioResponse]:
        """Process incoming webhook from Copilot Studio"""
        correlation_id = get_correlation_id()
        responses = []
        
        self.logger.info("Processing Copilot Studio webhook",
                        activities_count=len(request.activities),
                        watermark=request.watermark,
                        correlation_id=correlation_id)
        
        for activity in request.activities:
            try:
                response = await self._process_activity(activity, user_info)
                if response:
                    responses.append(response)
                    
            except Exception as e:
                self.logger.error("Failed to process activity",
                                activity_id=activity.id,
                                activity_type=activity.type,
                                error=str(e),
                                correlation_id=correlation_id)
                
                # Send error response
                error_response = CopilotStudioResponse(
                    type="message",
                    text=f"Sorry, I encountered an error processing your request. Please try again. (ID: {correlation_id})"
                )
                responses.append(error_response)
        
        return responses
    
    async def _process_activity(self, activity: CopilotStudioActivity,
                              user_info: Dict[str, Any]) -> Optional[CopilotStudioResponse]:
        """Process a single activity"""
        activity_type = activity.type.lower()
        
        if activity_type in self.supported_activities:
            handler = self.supported_activities[activity_type]
            return await handler(activity, user_info)
        else:
            self.logger.warning("Unsupported activity type",
                              activity_type=activity_type,
                              activity_id=activity.id)
            return None
    
    async def _handle_message_activity(self, activity: CopilotStudioActivity,
                                     user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle message activity (user sends message) with conversation context"""
        user_id = user_info.get("id", "anonymous")
        conversation_id = activity.conversation.get("id", "unknown")
        
        # Get conversation manager
        conv_manager = await self._ensure_conversation_manager()
        
        self.logger.info("Processing message activity with conversation context",
                        user_id=user_id,
                        conversation_id=conversation_id,
                        has_text=bool(activity.text),
                        attachments_count=len(activity.attachments))
        
        # Process message through conversation manager
        message_content = activity.text or ""
        message_type = MessageType.TEXT
        metadata = {
            "activity_id": activity.id,
            "timestamp": activity.timestamp,
            "channel_data": activity.channel_data
        }
        
        # Check for image attachments and update message type
        image_attachment = None
        for attachment in activity.attachments:
            if attachment.get("contentType", "").startswith("image/"):
                image_attachment = attachment
                message_type = MessageType.IMAGE
                message_content = attachment.get("contentUrl", "")
                metadata["image_attachment"] = attachment
                break
        
        # Process message through conversation manager
        try:
            processed_message = await conv_manager.process_message(
                conversation_id=conversation_id,
                user_id=user_id,
                message_content=message_content,
                message_type=message_type,
                metadata=metadata
            )
            
            # Get conversation context for response generation
            context = await conv_manager.get_context_for_response(conversation_id)
            
            # Handle based on conversation state and intent
            if image_attachment:
                return await self._handle_image_processing_with_context(
                    activity, user_info, image_attachment, context, processed_message
                )
            elif activity.text:
                return await self._handle_text_message_with_context(
                    activity, user_info, context, processed_message
                )
            else:
                # No processable content - provide context-aware response
                return await self._create_context_aware_prompt(context)
                
        except Exception as e:
            self.logger.error("Failed to process message through conversation manager",
                            error=str(e),
                            user_id=user_id,
                            conversation_id=conversation_id)
            
            # Fallback to basic processing
            if image_attachment:
                return await self._handle_image_processing(activity, user_info, image_attachment)
            elif activity.text:
                return await self._handle_text_message(activity, user_info)
            else:
                return CopilotStudioResponse(
                    type="message",
                    text="Please share a screenshot or describe what you'd like me to help you with."
                )
    
    async def _handle_invoke_activity(self, activity: CopilotStudioActivity,
                                    user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle invoke activity (action invocation)"""
        action_name = activity.value.get("action") if activity.value else None
        
        self.logger.info("Processing invoke activity",
                        action_name=action_name,
                        user_id=user_info.get("id"),
                        value=activity.value)
        
        if action_name == "generateCode":
            return await self._handle_code_generation_action(activity, user_info)
        elif action_name == "regenerateCode":
            return await self._handle_code_regeneration_action(activity, user_info)
        elif action_name == "downloadCode":
            return await self._handle_code_download_action(activity, user_info)
        else:
            return CopilotStudioResponse(
                type="message",
                text=f"Unknown action: {action_name}"
            )
    
    async def _handle_event_activity(self, activity: CopilotStudioActivity,
                                   user_info: Dict[str, Any]) -> Optional[CopilotStudioResponse]:
        """Handle event activity (system events)"""
        event_type = activity.value.get("type") if activity.value else None
        
        self.logger.info("Processing event activity",
                        event_type=event_type,
                        user_id=user_info.get("id"))
        
        if event_type == "conversationStart":
            return await self._handle_conversation_start(activity, user_info)
        elif event_type == "conversationEnd":
            return await self._handle_conversation_end(activity, user_info)
        
        return None
    
    async def _handle_image_processing(self, activity: CopilotStudioActivity,
                                     user_info: Dict[str, Any],
                                     image_attachment: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle image processing for code generation"""
        try:
            # Extract image data
            content_url = image_attachment.get("contentUrl")
            
            # Create adaptive card response with framework selection
            adaptive_card = AdaptiveCard(
                body=[
                    {
                        "type": "TextBlock",
                        "text": "🎨 Screenshot Received!",
                        "weight": "Bolder",
                        "size": "Medium"
                    },
                    {
                        "type": "TextBlock",
                        "text": "I can see your screenshot. Please choose which framework you'd like me to use for code generation:",
                        "wrap": True
                    },
                    {
                        "type": "Image",
                        "url": content_url,
                        "size": "Medium",
                        "altText": "User uploaded screenshot"
                    }
                ],
                actions=[
                    {
                        "type": "Action.Submit",
                        "title": "⚛️ React",
                        "data": {
                            "action": "generateCode",
                            "framework": "react",
                            "imageUrl": content_url,
                            "requirements": activity.text
                        }
                    },
                    {
                        "type": "Action.Submit", 
                        "title": "🌐 HTML/CSS",
                        "data": {
                            "action": "generateCode",
                            "framework": "html",
                            "imageUrl": content_url,
                            "requirements": activity.text
                        }
                    },
                    {
                        "type": "Action.Submit",
                        "title": "💚 Vue.js",
                        "data": {
                            "action": "generateCode",
                            "framework": "vue",
                            "imageUrl": content_url,
                            "requirements": activity.text
                        }
                    }
                ]
            )
            
            return CopilotStudioResponse(
                type="message",
                attachments=[
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": adaptive_card.dict(by_alias=True)
                    }
                ]
            )
            
        except Exception as e:
            self.logger.error("Failed to process image",
                            error=str(e),
                            image_url=image_attachment.get("contentUrl"))
            
            return CopilotStudioResponse(
                type="message",
                text="Sorry, I couldn't process your image. Please try uploading again."
            )
    
    async def _handle_text_message(self, activity: CopilotStudioActivity,
                                 user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle text-only message"""
        text = activity.text.lower().strip()
        
        # Simple intent detection
        if any(keyword in text for keyword in ["help", "what can you do", "commands"]):
            return await self._create_help_response()
        elif any(keyword in text for keyword in ["screenshot", "image", "upload"]):
            return await self._create_upload_prompt_response()
        else:
            return CopilotStudioResponse(
                type="message",
                text="I can help you convert screenshots to code! Please upload an image and I'll generate the corresponding HTML, CSS, or React code for you."
            )
    
    async def _handle_image_processing_with_context(self, activity: CopilotStudioActivity,
                                                  user_info: Dict[str, Any],
                                                  image_attachment: Dict[str, Any],
                                                  context: Dict[str, Any],
                                                  processed_message) -> CopilotStudioResponse:
        """Handle image processing with conversation context using rich formatter"""
        try:
            # Extract image data
            content_url = image_attachment.get("contentUrl")
            
            # Use user preferences from context
            user_preferences = context.get("user_preferences", {})
            
            # Get rich formatter
            formatter = get_rich_formatter()
            
            # Create enhanced framework selection response
            adaptive_card = formatter.create_framework_selection_response(
                image_url=content_url,
                user_preferences=user_preferences,
                theme=ResponseTheme.DEFAULT
            )
            
            return CopilotStudioResponse(
                type="message",
                attachments=[
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": adaptive_card
                    }
                ]
            )
            
        except Exception as e:
            self.logger.error("Failed to process image with context",
                            error=str(e),
                            image_url=image_attachment.get("contentUrl"))
            
            # Create error response using rich formatter
            formatter = get_rich_formatter()
            error_card = formatter.create_error_response(
                error_message="Failed to process your screenshot. Please try uploading again.",
                error_code="IMG_PROCESS_001",
                recovery_actions=[
                    InteractiveAction(
                        id="upload_again",
                        title="📸 Upload Again",
                        action_type="Action.Submit",
                        data={"action": "promptUpload"}
                    )
                ]
            )
            
            return CopilotStudioResponse(
                type="message",
                attachments=[
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": error_card
                    }
                ]
            )
    
    async def _handle_text_message_with_context(self, activity: CopilotStudioActivity,
                                              user_info: Dict[str, Any],
                                              context: Dict[str, Any],
                                              processed_message) -> CopilotStudioResponse:
        """Handle text message with conversation context"""
        intent = processed_message.intent
        confidence = processed_message.confidence
        entities = processed_message.entities
        
        user_preferences = context.get("user_preferences", {})
        communication_style = user_preferences.get("communication_style", "detailed")
        current_state = context.get("current_state", "initial")
        
        self.logger.info("Processing text with context",
                        intent=intent.value if intent else None,
                        confidence=confidence,
                        current_state=current_state,
                        communication_style=communication_style)
        
        # Handle based on detected intent
        if intent == UserIntent.REQUEST_HELP:
            return await self._create_contextual_help_response(context, communication_style)
        elif intent == UserIntent.UPLOAD_SCREENSHOT:
            return await self._create_contextual_upload_prompt(context, communication_style)
        elif intent == UserIntent.MODIFY_CODE:
            return await self._handle_code_modification_request(context, activity.text)
        elif intent == UserIntent.PROVIDE_FEEDBACK:
            return await self._handle_feedback_with_context(context, activity.text, entities)
        elif intent == UserIntent.START_OVER:
            return await self._handle_conversation_reset(context)
        else:
            # Unknown intent - provide contextual guidance
            return await self._create_contextual_guidance(context, activity.text, communication_style)
    
    async def _create_context_aware_prompt(self, context: Dict[str, Any]) -> CopilotStudioResponse:
        """Create context-aware prompt when no specific content is provided"""
        current_state = context.get("current_state", "initial")
        user_preferences = context.get("user_preferences", {})
        communication_style = user_preferences.get("communication_style", "detailed")
        
        if current_state == ConversationState.AWAITING_SCREENSHOT.value:
            message = "I'm ready for your screenshot!" if communication_style == "concise" else "I'm waiting for you to share a screenshot. Please upload an image of the UI you'd like me to convert to code."
        elif current_state == ConversationState.FRAMEWORK_SELECTION.value:
            message = "Please choose a framework for your code." if communication_style == "concise" else "I see you've uploaded a screenshot. Please select which framework you'd like me to use for code generation."
        else:
            message = "How can I help you today?" if communication_style == "concise" else "Please share a screenshot or describe what you'd like me to help you with."
        
        return CopilotStudioResponse(type="message", text=message)
    
    def _create_framework_actions(self, content_url: str, requirements: Optional[str], preferred_framework: str) -> List[Dict[str, Any]]:
        """Create framework selection actions with preference highlighting"""
        frameworks = [
            {"key": "react", "title": "⚛️ React", "emoji": "⚛️"},
            {"key": "html", "title": "🌐 HTML/CSS", "emoji": "🌐"},
            {"key": "vue", "title": "💚 Vue.js", "emoji": "💚"},
            {"key": "angular", "title": "🅰️ Angular", "emoji": "🅰️"},
            {"key": "svelte", "title": "🧡 Svelte", "emoji": "🧡"}
        ]
        
        actions = []
        for fw in frameworks:
            title = fw["title"]
            if fw["key"] == preferred_framework:
                title += " (Recommended)"
            
            actions.append({
                "type": "Action.Submit",
                "title": title,
                "data": {
                    "action": "generateCode",
                    "framework": fw["key"],
                    "imageUrl": content_url,
                    "requirements": requirements
                }
            })
        
        return actions
    
    async def _create_contextual_help_response(self, context: Dict[str, Any], communication_style: str) -> CopilotStudioResponse:
        """Create help response based on conversation context"""
        current_state = context.get("current_state", "initial")
        
        if communication_style == "concise":
            if current_state == ConversationState.CODE_REVIEW.value:
                text = "You can ask me to modify the code, regenerate it, or start over with a new screenshot."
            else:
                text = "Upload a screenshot → Choose framework → Get code. That's it!"
        else:
            if current_state == ConversationState.CODE_REVIEW.value:
                text = "You can ask me to modify the generated code, regenerate it with different parameters, or start over with a new screenshot. I can also explain specific parts of the code."
            else:
                text = "I can help you convert screenshots to code! Just upload an image and I'll generate clean, working code in your preferred framework."
        
        return CopilotStudioResponse(type="message", text=text)
    
    async def _create_contextual_upload_prompt(self, context: Dict[str, Any], communication_style: str) -> CopilotStudioResponse:
        """Create upload prompt based on context"""
        message = "📸 Please upload your screenshot!" if communication_style == "concise" else "📸 Great! Please upload a screenshot of the UI you'd like me to convert to code. I support JPG, PNG, and GIF formats."
        
        return CopilotStudioResponse(type="message", text=message)
    
    async def _handle_code_modification_request(self, context: Dict[str, Any], request_text: str) -> CopilotStudioResponse:
        """Handle code modification requests"""
        current_code = context.get("generated_code", {})
        
        if not current_code:
            return CopilotStudioResponse(
                type="message",
                text="I don't see any generated code to modify. Please upload a screenshot first to generate code."
            )
        
        # TODO: Implement code modification logic
        return CopilotStudioResponse(
            type="message",
            text=f"I understand you want to modify the code: '{request_text}'. Code modification feature is coming soon!"
        )
    
    async def _handle_feedback_with_context(self, context: Dict[str, Any], feedback_text: str, entities: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle user feedback with context"""
        # Determine if feedback is positive or negative
        positive_words = ["good", "great", "excellent", "perfect", "works", "thank", "thanks"]
        negative_words = ["bad", "wrong", "doesn't work", "error", "broken", "fix"]
        
        feedback_lower = feedback_text.lower()
        is_positive = any(word in feedback_lower for word in positive_words)
        is_negative = any(word in feedback_lower for word in negative_words)
        
        if is_positive:
            return CopilotStudioResponse(
                type="message",
                text="🎉 Wonderful! I'm glad the code worked well for you. Feel free to upload another screenshot if you need more help!"
            )
        elif is_negative:
            return CopilotStudioResponse(
                type="message",
                text="I'm sorry the code didn't work as expected. Can you tell me what specific issues you encountered? I'd be happy to help fix them."
            )
        else:
            return CopilotStudioResponse(
                type="message",
                text="Thank you for your feedback! It helps me improve. Is there anything specific I can help you with?"
            )
    
    async def _handle_conversation_reset(self, context: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle conversation reset request"""
        return CopilotStudioResponse(
            type="message",
            text="🔄 Starting fresh! Please upload a screenshot to begin code generation."
        )
    
    async def _create_contextual_guidance(self, context: Dict[str, Any], message_text: str, communication_style: str) -> CopilotStudioResponse:
        """Create contextual guidance for unclear messages"""
        current_state = context.get("current_state", "initial")
        
        if communication_style == "concise":
            if current_state == ConversationState.INITIAL.value:
                guidance = "Upload a screenshot to start."
            elif current_state == ConversationState.FRAMEWORK_SELECTION.value:
                guidance = "Choose a framework from the options above."
            else:
                guidance = "Not sure what you mean. Try: 'help', 'start over', or upload a screenshot."
        else:
            if current_state == ConversationState.INITIAL.value:
                guidance = "I'd be happy to help! Please upload a screenshot of the UI you'd like me to convert to code."
            elif current_state == ConversationState.FRAMEWORK_SELECTION.value:
                guidance = "Please choose a framework from the options I provided above to generate your code."
            else:
                guidance = f"I'm not sure how to help with '{message_text}'. You can ask for help, start over, or upload a new screenshot."
        
        return CopilotStudioResponse(type="message", text=guidance)

    async def _handle_code_generation_action(self, activity: CopilotStudioActivity,
                                           user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle code generation action"""
        action_data = activity.value
        framework_str = action_data.get("framework", "react")
        image_url = action_data.get("imageUrl")
        requirements = action_data.get("requirements", "")
        
        self.logger.info("Processing code generation action",
                        framework=framework_str,
                        has_image_url=bool(image_url),
                        user_id=user_info.get("id"),
                        requirements=requirements)
        
        # Convert framework string to enum
        try:
            framework = Framework(framework_str)
        except ValueError:
            framework = Framework.REACT
        
        # Get copilot service
        copilot_service = await get_copilot_service()
        
        try:
            # Process screenshot to code
            result = await copilot_service.process_screenshot_to_code(
                image_url=image_url,
                framework=framework,
                requirements=requirements if requirements else None,
                user_id=user_info.get("id", "anonymous"),
                conversation_id=activity.conversation.get("id", "unknown"),
                async_processing=False
            )
            
            if result.success and result.generated_code:
                # Record successful generation in conversation manager
                conv_manager = await self._ensure_conversation_manager()
                await conv_manager.record_successful_generation(
                    conversation_id=activity.conversation.get("id", "unknown"),
                    framework=framework_str,
                    code=result.generated_code
                )
                
                # Get conversation context for user preferences
                context = await conv_manager.get_context_for_response(
                    activity.conversation.get("id", "unknown")
                )
                user_preferences = context.get("user_preferences", {})
                
                # Create code blocks for rich formatter
                code_blocks = []
                for filename, content in result.generated_code.items():
                    code_language = detect_code_language(filename)
                    code_blocks.append(CodeBlock(
                        filename=filename,
                        content=content,
                        language=code_language,
                        line_numbers=True,
                        max_lines=20 if user_preferences.get("communication_style") == "concise" else 30
                    ))
                
                # Create custom actions
                custom_actions = [
                    InteractiveAction(
                        id="regenerate",
                        title="🔄 Regenerate",
                        action_type="Action.Submit",
                        data={
                            "action": "regenerateCode",
                            "framework": framework_str,
                            "imageUrl": image_url,
                            "requirements": requirements
                        }
                    ),
                    InteractiveAction(
                        id="modify",
                        title="✏️ Modify Code",
                        action_type="Action.Submit",
                        data={
                            "action": "modifyCode",
                            "framework": framework_str,
                            "code": result.generated_code
                        }
                    )
                ]
                
                # Get rich formatter and create response
                formatter = get_rich_formatter()
                adaptive_card = formatter.create_code_generation_response(
                    code_blocks=code_blocks,
                    framework=framework_str,
                    processing_time_ms=result.processing_time_ms,
                    theme=ResponseTheme.SUCCESS,
                    user_preferences=user_preferences,
                    preview_url=getattr(result, 'preview_url', None),
                    actions=custom_actions
                )
                
                return CopilotStudioResponse(
                    type="message",
                    attachments=[
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": adaptive_card
                        }
                    ]
                )
            
            else:
                # Generation failed
                error_msg = result.error or "Unknown error occurred"
                
                adaptive_card = AdaptiveCard(
                    body=[
                        {
                            "type": "TextBlock",
                            "text": "❌ Code Generation Failed",
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Attention"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Error: {error_msg}",
                            "wrap": True,
                            "color": "Attention"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Please try again or contact support if the issue persists.",
                            "wrap": True
                        }
                    ],
                    actions=[
                        {
                            "type": "Action.Submit",
                            "title": "🔄 Try Again",
                            "data": {
                                "action": "generateCode",
                                "framework": framework_str,
                                "imageUrl": image_url,
                                "requirements": requirements
                            }
                        }
                    ]
                )
                
                return CopilotStudioResponse(
                    type="message",
                    attachments=[
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": adaptive_card.dict(by_alias=True)
                        }
                    ]
                )
        
        except Exception as e:
            # Record error in conversation manager
            conv_manager = await self._ensure_conversation_manager()
            await conv_manager.record_error(
                conversation_id=activity.conversation.get("id", "unknown"),
                error_type="code_generation_error",
                error_message=str(e)
            )
            
            self.logger.error("Code generation action failed",
                            error=str(e),
                            framework=framework_str,
                            user_id=user_info.get("id"))
            
            return CopilotStudioResponse(
                type="message",
                text=f"❌ Sorry, code generation failed: {str(e)}. Please try again."
            )
    
    async def _handle_code_regeneration_action(self, activity: CopilotStudioActivity,
                                             user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle code regeneration action"""
        return CopilotStudioResponse(
            type="message",
            text="🔄 Regenerating code with different settings..."
        )
    
    async def _handle_code_download_action(self, activity: CopilotStudioActivity,
                                         user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle code download action"""
        return CopilotStudioResponse(
            type="message",
            text="📁 Your code is ready for download! Check your OneDrive for the generated files."
        )
    
    async def _handle_conversation_start(self, activity: CopilotStudioActivity,
                                       user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Handle conversation start event with context initialization"""
        # Initialize conversation in conversation manager
        conv_manager = await self._ensure_conversation_manager()
        context = await conv_manager.start_conversation(
            user_id=user_info.get("id", "anonymous"),
            conversation_id=activity.conversation.get("id", "unknown")
        )
        
        self.logger.info("Conversation started with context management",
                        user_id=user_info.get("id"),
                        conversation_id=context.conversation_id)
        
        return await self._create_welcome_response(user_info)
    
    async def _handle_conversation_end(self, activity: CopilotStudioActivity,
                                     user_info: Dict[str, Any]) -> Optional[CopilotStudioResponse]:
        """Handle conversation end event with analytics"""
        conversation_id = activity.conversation.get("id", "unknown")
        
        # End conversation and get analytics
        conv_manager = await self._ensure_conversation_manager()
        analytics = await conv_manager.end_conversation(conversation_id)
        
        if analytics:
            # Log conversation analytics
            self.logger.info("Conversation ended with analytics",
                           user_id=user_info.get("id"),
                           conversation_id=conversation_id,
                           duration_seconds=analytics["conversation_summary"]["last_activity"],
                           message_count=analytics["conversation_summary"]["message_count"],
                           successful_generations=analytics["conversation_summary"]["successful_generations"],
                           quality_score=analytics["analytics"]["quality_score"])
        else:
            self.logger.info("Conversation ended",
                           user_id=user_info.get("id"),
                           conversation_id=conversation_id)
        
        return None
    
    async def _create_welcome_response(self, user_info: Dict[str, Any]) -> CopilotStudioResponse:
        """Create personalized welcome message using rich formatter"""
        user_name = user_info.get("name", "there")
        
        # Get conversation manager to check for user preferences
        try:
            conv_manager = await self._ensure_conversation_manager()
            user_id = user_info.get("id", "anonymous")
            user_profile = conv_manager.user_profiles.get(user_id)
            
            user_preferences = {}
            if user_profile:
                user_preferences = {
                    "preferred_framework": user_profile.get_recommended_framework() or "react",
                    "communication_style": user_profile.preferred_communication_style,
                    "experience_level": "advanced" if user_profile.success_rate > 0.8 else "beginner"
                }
        except Exception:
            user_preferences = {}
        
        # Get rich formatter and create welcome response
        formatter = get_rich_formatter()
        adaptive_card = formatter.create_welcome_response(
            user_name=user_name,
            user_preferences=user_preferences,
            theme=ResponseTheme.DEFAULT,
            show_features=True
        )
        
        return CopilotStudioResponse(
            type="message",
            attachments=[
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": adaptive_card
                }
            ]
        )
    
    async def _create_help_response(self) -> CopilotStudioResponse:
        """Create help response"""
        adaptive_card = AdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🤖 Screenshot-to-Code Assistant",
                    "weight": "Bolder",
                    "size": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "Here's how to use me:",
                    "wrap": True
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "📸 Upload Image", "value": "Share a screenshot of any UI"},
                        {"title": "⚙️ Choose Framework", "value": "Select React, HTML/CSS, or Vue.js"},
                        {"title": "✨ Get Code", "value": "Receive clean, working code"},
                        {"title": "💾 Download", "value": "Save files to your OneDrive"}
                    ]
                }
            ]
        )
        
        return CopilotStudioResponse(
            type="message",
            attachments=[
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": adaptive_card.dict(by_alias=True)
                }
            ]
        )
    
    async def _create_upload_prompt_response(self) -> CopilotStudioResponse:
        """Create upload prompt response"""
        return CopilotStudioResponse(
            type="message",
            text="📸 Great! Please upload a screenshot of the UI you'd like me to convert to code. I support JPG, PNG, and GIF formats."
        )


# Initialize webhook handler
webhook_handler = CopilotStudioWebhookHandler(logger)


def verify_webhook_signature(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature for security"""
    if not signature:
        return False
    
    try:
        # Remove 'sha256=' prefix if present
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception:
        return False


async def get_user_info(request: Request) -> Dict[str, Any]:
    """Extract user information from request"""
    # TODO: Implement proper user extraction from Copilot Studio request
    # This would typically come from authentication headers or request body
    return {
        "id": "user123",
        "name": "Test User",
        "email": "test@example.com"
    }


# Webhook Endpoints
@router.post("/webhook")
async def copilot_studio_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
):
    """Main webhook endpoint for Copilot Studio integration"""
    correlation_id = set_correlation_id()
    
    try:
        # Get request body
        request_body = await request.body()
        
        # Verify webhook signature if configured
        webhook_secret = "your-webhook-secret"  # TODO: Get from config
        if webhook_secret and not verify_webhook_signature(
            request_body, x_hub_signature_256 or "", webhook_secret
        ):
            logger.warning("Invalid webhook signature",
                          correlation_id=correlation_id)
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse request
        try:
            request_data = json.loads(request_body.decode('utf-8'))
            copilot_request = CopilotStudioRequest(**request_data)
        except Exception as e:
            logger.error("Failed to parse webhook request",
                        error=str(e),
                        correlation_id=correlation_id)
            raise HTTPException(status_code=400, detail="Invalid request format")
        
        # Get user information
        user_info = await get_user_info(request)
        
        # Process webhook
        responses = await webhook_handler.process_webhook(copilot_request, user_info)
        
        logger.info("Webhook processed successfully",
                   responses_count=len(responses),
                   correlation_id=correlation_id)
        
        # Return responses
        if len(responses) == 1:
            return responses[0].dict(by_alias=True)
        else:
            return {
                "type": "message",
                "text": f"Processed {len(responses)} activities successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Webhook processing failed",
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/webhook/health")
async def webhook_health():
    """Health check endpoint for webhook"""
    return {
        "status": "healthy",
        "service": "copilot-studio-webhook",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "supported_activities": list(webhook_handler.supported_activities.keys())
    }


@router.get("/webhook/schema")
async def webhook_schema():
    """Get webhook schema information"""
    return {
        "webhook_url": "/api/v1/copilot-studio/webhook",  
        "method": "POST",
        "content_type": "application/json",
        "authentication": "signature_verification",
        "supported_activities": [
            "message",
            "invoke", 
            "event"
        ],
        "response_format": "adaptive_cards_supported",
        "schema_version": "1.0"
    }


@router.get("/analytics")
async def get_conversation_analytics():
    """Get conversation analytics"""
    correlation_id = set_correlation_id()
    
    try:
        conv_manager = await get_conversation_manager()
        analytics = await conv_manager.get_conversation_analytics()
        
        logger.info("Retrieved conversation analytics",
                   total_conversations=analytics["total_conversations"],
                   correlation_id=correlation_id)
        
        return {
            "success": True,
            "analytics": analytics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id
        }
        
    except Exception as e:
        logger.error("Failed to retrieve conversation analytics",
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")


@router.get("/conversations/{conversation_id}/context")
async def get_conversation_context(conversation_id: str):
    """Get conversation context for debugging"""
    correlation_id = set_correlation_id()
    
    try:
        conv_manager = await get_conversation_manager()
        context = await conv_manager.get_conversation_context(conversation_id)
        
        if not context:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        logger.info("Retrieved conversation context",
                   conversation_id=conversation_id,
                   correlation_id=correlation_id)
        
        return {
            "success": True,
            "context": context.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve conversation context",
                    conversation_id=conversation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve context")


@router.post("/conversations/{conversation_id}/end")
async def end_conversation_manually(conversation_id: str):
    """Manually end a conversation and get analytics"""
    correlation_id = set_correlation_id()
    
    try:
        conv_manager = await get_conversation_manager()
        analytics = await conv_manager.end_conversation(conversation_id)
        
        if not analytics:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        logger.info("Manually ended conversation",
                   conversation_id=conversation_id,
                   correlation_id=correlation_id)
        
        return {
            "success": True,
            "analytics": analytics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to end conversation",
                    conversation_id=conversation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail="Failed to end conversation")