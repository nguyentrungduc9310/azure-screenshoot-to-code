"""
Advanced Conversation Manager
Sophisticated conversation management with multi-turn context awareness and user preference learning
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        """Mock correlation ID function"""
        return str(uuid.uuid4())[:8]


class ConversationState(Enum):
    """Conversation state enumeration"""
    INITIAL = "initial"
    GREETING = "greeting"
    AWAITING_SCREENSHOT = "awaiting_screenshot"
    FRAMEWORK_SELECTION = "framework_selection"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REFINEMENT = "refinement"
    COMPLETED = "completed"
    ERROR = "error"


class MessageType(Enum):
    """Message type enumeration"""
    TEXT = "text"
    IMAGE = "image"
    ACTION = "action"
    SYSTEM = "system"
    FEEDBACK = "feedback"


class UserIntent(Enum):
    """User intent classification"""
    UPLOAD_SCREENSHOT = "upload_screenshot"
    GENERATE_CODE = "generate_code"
    MODIFY_CODE = "modify_code"
    REQUEST_HELP = "request_help"
    PROVIDE_FEEDBACK = "provide_feedback"
    START_OVER = "start_over"
    UNKNOWN = "unknown"


@dataclass
class ConversationMessage:
    """Individual conversation message"""
    id: str
    timestamp: datetime
    user_id: str
    conversation_id: str
    message_type: MessageType
    content: str
    intent: Optional[UserIntent] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "message_type": self.message_type.value,
            "content": self.content,
            "intent": self.intent.value if self.intent else None,
            "entities": self.entities,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


@dataclass
class ConversationContext:
    """Conversation context and state"""
    conversation_id: str
    user_id: str
    state: ConversationState
    started_at: datetime
    last_activity: datetime
    messages: List[ConversationMessage] = field(default_factory=list)
    
    # Context variables
    current_framework: Optional[str] = None
    uploaded_images: List[str] = field(default_factory=list)
    generated_code: Dict[str, str] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    session_data: Dict[str, Any] = field(default_factory=dict)
    
    # Analytics
    message_count: int = 0
    error_count: int = 0
    successful_generations: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "messages": [msg.to_dict() for msg in self.messages],
            "current_framework": self.current_framework,
            "uploaded_images": self.uploaded_images,
            "generated_code": self.generated_code,
            "user_preferences": self.user_preferences,
            "session_data": self.session_data,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "successful_generations": self.successful_generations
        }


@dataclass
class UserProfile:
    """User profile with learning capabilities"""
    user_id: str
    created_at: datetime
    last_seen: datetime
    
    # Preferences learned from interactions
    preferred_frameworks: Dict[str, int] = field(default_factory=dict)  # framework -> usage_count
    preferred_styles: Dict[str, int] = field(default_factory=dict)      # style -> usage_count
    common_requirements: List[str] = field(default_factory=list)
    
    # Interaction patterns
    conversation_count: int = 0
    average_session_duration: float = 0.0
    preferred_communication_style: str = "detailed"  # detailed, concise, interactive
    
    # Learning metrics
    success_rate: float = 0.0
    satisfaction_score: float = 0.0
    
    def update_framework_preference(self, framework: str):
        """Update framework preference based on usage"""
        if framework in self.preferred_frameworks:
            self.preferred_frameworks[framework] += 1
        else:
            self.preferred_frameworks[framework] = 1
    
    def get_recommended_framework(self) -> Optional[str]:
        """Get most preferred framework"""
        if not self.preferred_frameworks:
            return None
        return max(self.preferred_frameworks.items(), key=lambda x: x[1])[0]


class IntentClassifier:
    """Intent classification engine"""
    
    def __init__(self):
        self.intent_patterns = {
            UserIntent.UPLOAD_SCREENSHOT: [
                "upload", "screenshot", "image", "picture", "photo", "convert", "generate code from"
            ],
            UserIntent.GENERATE_CODE: [
                "generate", "create code", "convert to", "make component", "build"
            ],
            UserIntent.MODIFY_CODE: [
                "change", "modify", "update", "edit", "fix", "improve", "refactor"
            ],
            UserIntent.REQUEST_HELP: [
                "help", "how to", "what can you", "explain", "guide", "instructions"
            ],
            UserIntent.PROVIDE_FEEDBACK: [
                "feedback", "good", "bad", "works", "doesn't work", "thank you", "thanks"
            ],
            UserIntent.START_OVER: [
                "start over", "reset", "begin again", "new conversation", "restart"
            ]
        }
    
    def classify_intent(self, message: str) -> Tuple[UserIntent, float]:
        """Classify user intent from message"""
        message_lower = message.lower().strip()
        
        if not message_lower:
            return UserIntent.UNKNOWN, 0.0
        
        best_intent = UserIntent.UNKNOWN
        best_score = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                if pattern in message_lower:
                    score += 1.0 / len(patterns)  # Normalize by pattern count
            
            if score > best_score:
                best_score = score
                best_intent = intent
        
        # Apply confidence threshold
        confidence = min(best_score * 2.0, 1.0)  # Scale to 0-1
        
        return best_intent, confidence
    
    def extract_entities(self, message: str, detected_intent: UserIntent) -> Dict[str, Any]:
        """Extract entities based on intent"""
        entities = {}
        message_lower = message.lower()
        
        # Framework extraction
        frameworks = ["react", "vue", "angular", "html", "css", "svelte"]
        for framework in frameworks:
            if framework in message_lower:
                entities["framework"] = framework
                break
        
        # Style preferences
        styles = ["responsive", "mobile", "desktop", "modern", "minimal", "dark", "light"]
        found_styles = [style for style in styles if style in message_lower]
        if found_styles:
            entities["styles"] = found_styles
        
        # Requirements keywords
        requirements = ["accessibility", "responsive", "mobile-first", "animation", "interactive"]
        found_requirements = [req for req in requirements if req in message_lower]
        if found_requirements:
            entities["requirements"] = found_requirements
        
        # Intent-specific entity extraction
        if detected_intent == UserIntent.MODIFY_CODE:
            modify_keywords = ["change", "update", "fix", "improve", "modify"]
            found_modifications = [kw for kw in modify_keywords if kw in message_lower]
            if found_modifications:
                entities["modifications"] = found_modifications
        
        return entities


class ConversationAnalytics:
    """Conversation analytics and insights"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def analyze_conversation_quality(self, context: ConversationContext) -> Dict[str, Any]:
        """Analyze conversation quality metrics"""
        if not context.messages:
            return {"quality_score": 0.0, "insights": []}
        
        duration = (context.last_activity - context.started_at).total_seconds()
        
        # Calculate metrics
        avg_response_confidence = sum(msg.confidence for msg in context.messages) / len(context.messages)
        error_rate = context.error_count / context.message_count if context.message_count > 0 else 0
        success_rate = context.successful_generations / max(1, context.message_count)
        
        # Quality scoring
        quality_score = (
            avg_response_confidence * 0.4 +
            (1 - error_rate) * 0.3 +
            success_rate * 0.3
        )
        
        insights = []
        
        if avg_response_confidence < 0.7:
            insights.append("Low confidence in intent classification - consider improving NLP")
        
        if error_rate > 0.1:
            insights.append("High error rate - review error handling")
        
        if duration > 300:  # 5 minutes
            insights.append("Long conversation duration - consider workflow optimization")
        
        if context.successful_generations == 0:
            insights.append("No successful code generations - review user journey")
        
        return {
            "quality_score": quality_score,
            "avg_confidence": avg_response_confidence,
            "error_rate": error_rate,
            "success_rate": success_rate,
            "duration_seconds": duration,
            "insights": insights
        }
    
    def generate_user_insights(self, profile: UserProfile) -> Dict[str, Any]:
        """Generate insights about user behavior"""
        insights = {
            "experience_level": "beginner",
            "communication_preference": profile.preferred_communication_style,
            "framework_expertise": {},
            "recommendations": []
        }
        
        # Determine experience level
        if profile.conversation_count > 10 and profile.success_rate > 0.8:
            insights["experience_level"] = "advanced"
        elif profile.conversation_count > 3 and profile.success_rate > 0.6:
            insights["experience_level"] = "intermediate"
        
        # Framework expertise
        total_usage = sum(profile.preferred_frameworks.values())
        if total_usage > 0:
            for framework, count in profile.preferred_frameworks.items():
                insights["framework_expertise"][framework] = count / total_usage
        
        # Recommendations
        if profile.success_rate < 0.5:
            insights["recommendations"].append("Provide more detailed guidance and examples")
        
        if len(profile.preferred_frameworks) == 1:
            insights["recommendations"].append("Introduce other frameworks to expand skills")
        
        if profile.average_session_duration < 60:
            insights["recommendations"].append("User prefers quick interactions - optimize for speed")
        
        return insights


class AdvancedConversationManager:
    """Advanced conversation manager with context awareness and learning"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        self.intent_classifier = IntentClassifier()
        self.analytics = ConversationAnalytics(self.logger)
        
        # In-memory storage (would be replaced with persistent storage)
        self.conversations: Dict[str, ConversationContext] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        
        # Configuration
        self.session_timeout_minutes = 30
        self.max_context_messages = 50
        
    async def start_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> ConversationContext:
        """Start a new conversation or resume existing one"""
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
        
        # Check if conversation exists and is not expired
        if conversation_id in self.conversations:
            context = self.conversations[conversation_id]
            time_since_last = datetime.now(timezone.utc) - context.last_activity
            
            if time_since_last.total_seconds() < self.session_timeout_minutes * 60:
                # Resume existing conversation
                context.last_activity = datetime.now(timezone.utc)
                self.logger.info("Resuming conversation", 
                               conversation_id=conversation_id, 
                               user_id=user_id)
                return context
        
        # Create new conversation
        now = datetime.now(timezone.utc)
        context = ConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            state=ConversationState.INITIAL,
            started_at=now,
            last_activity=now
        )
        
        self.conversations[conversation_id] = context
        
        # Update or create user profile
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(
                user_id=user_id,
                created_at=now,
                last_seen=now
            )
        else:
            self.user_profiles[user_id].last_seen = now
            self.user_profiles[user_id].conversation_count += 1
        
        self.logger.info("Started new conversation", 
                        conversation_id=conversation_id, 
                        user_id=user_id)
        
        return context
    
    async def process_message(self, conversation_id: str, user_id: str, 
                            message_content: str, message_type: MessageType = MessageType.TEXT,
                            metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """Process incoming message and update conversation context"""
        correlation_id = get_correlation_id()
        
        # Get or create conversation
        context = await self.start_conversation(user_id, conversation_id)
        
        # Classify intent and extract entities
        intent, confidence = self.intent_classifier.classify_intent(message_content)
        entities = self.intent_classifier.extract_entities(message_content, intent)
        
        # Create message
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            conversation_id=conversation_id,
            message_type=message_type,
            content=message_content,
            intent=intent,
            entities=entities,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        # Add to conversation
        context.messages.append(message)
        context.message_count += 1
        context.last_activity = datetime.now(timezone.utc)
        
        # Update conversation state based on intent
        await self._update_conversation_state(context, message)
        
        # Learn from user interaction
        await self._learn_from_interaction(context, message)
        
        # Trim context if too long
        if len(context.messages) > self.max_context_messages:
            context.messages = context.messages[-self.max_context_messages:]
        
        self.logger.info("Processed message", 
                        conversation_id=conversation_id,
                        intent=intent.value,
                        confidence=confidence,
                        correlation_id=correlation_id)
        
        return message
    
    async def _update_conversation_state(self, context: ConversationContext, message: ConversationMessage):
        """Update conversation state based on message intent"""
        current_state = context.state
        intent = message.intent
        
        # State transition logic
        if intent == UserIntent.UPLOAD_SCREENSHOT and current_state in [ConversationState.INITIAL, ConversationState.GREETING]:
            context.state = ConversationState.FRAMEWORK_SELECTION
            if message.message_type == MessageType.IMAGE:
                context.uploaded_images.append(message.content)
        
        elif intent == UserIntent.GENERATE_CODE and current_state == ConversationState.FRAMEWORK_SELECTION:
            context.state = ConversationState.CODE_GENERATION
            if "framework" in message.entities:
                context.current_framework = message.entities["framework"]
        
        elif intent == UserIntent.MODIFY_CODE and current_state in [ConversationState.CODE_REVIEW, ConversationState.COMPLETED]:
            context.state = ConversationState.REFINEMENT
        
        elif intent == UserIntent.START_OVER:
            context.state = ConversationState.INITIAL
            context.current_framework = None
            context.uploaded_images = []
            context.generated_code = {}
        
        elif intent == UserIntent.REQUEST_HELP:
            # Help doesn't change state, just provides assistance
            pass
        
        # Log state transitions
        if current_state != context.state:
            self.logger.info("Conversation state transition",
                           conversation_id=context.conversation_id,
                           from_state=current_state.value,
                           to_state=context.state.value,
                           intent=intent.value)
    
    async def _learn_from_interaction(self, context: ConversationContext, message: ConversationMessage):
        """Learn from user interactions to improve future responses"""
        user_profile = self.user_profiles[context.user_id]
        
        # Learn framework preferences
        if "framework" in message.entities:
            framework = message.entities["framework"]
            user_profile.update_framework_preference(framework)
        
        # Learn style preferences
        if "styles" in message.entities:
            for style in message.entities["styles"]:
                if style in user_profile.preferred_styles:
                    user_profile.preferred_styles[style] += 1
                else:
                    user_profile.preferred_styles[style] = 1
        
        # Learn common requirements
        if "requirements" in message.entities:
            for req in message.entities["requirements"]:
                if req not in user_profile.common_requirements:
                    user_profile.common_requirements.append(req)
        
        # Update communication style based on message length and complexity
        if len(message.content) > 100:
            user_profile.preferred_communication_style = "detailed"
        elif len(message.content) < 20:
            user_profile.preferred_communication_style = "concise"
    
    async def get_conversation_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context"""
        return self.conversations.get(conversation_id)
    
    async def get_context_for_response(self, conversation_id: str, max_messages: int = 10) -> Dict[str, Any]:
        """Get conversation context optimized for response generation"""
        context = self.conversations.get(conversation_id)
        if not context:
            return {}
        
        # Get recent messages
        recent_messages = context.messages[-max_messages:] if context.messages else []
        
        # Get user preferences
        user_profile = self.user_profiles.get(context.user_id)
        preferences = {}
        if user_profile:
            preferences = {
                "preferred_framework": user_profile.get_recommended_framework(),
                "preferred_styles": user_profile.preferred_styles,
                "communication_style": user_profile.preferred_communication_style,
                "experience_level": "advanced" if user_profile.success_rate > 0.8 else "beginner"
            }
        
        return {
            "conversation_id": conversation_id,
            "user_id": context.user_id,
            "current_state": context.state.value,
            "current_framework": context.current_framework,
            "uploaded_images": context.uploaded_images,
            "generated_code": context.generated_code,
            "recent_messages": [msg.to_dict() for msg in recent_messages],
            "user_preferences": preferences,
            "session_data": context.session_data
        }
    
    async def record_successful_generation(self, conversation_id: str, framework: str, code: Dict[str, str]):
        """Record successful code generation"""
        context = self.conversations.get(conversation_id)
        if context:
            context.successful_generations += 1
            context.generated_code.update(code)
            context.state = ConversationState.CODE_REVIEW
            
            # Update user profile
            user_profile = self.user_profiles.get(context.user_id)
            if user_profile:
                user_profile.update_framework_preference(framework)
                # Update success rate
                total_attempts = context.message_count
                user_profile.success_rate = context.successful_generations / max(1, total_attempts)
    
    async def record_error(self, conversation_id: str, error_type: str, error_message: str):
        """Record conversation error"""
        context = self.conversations.get(conversation_id)
        if context:
            context.error_count += 1
            context.state = ConversationState.ERROR
            
            # Add error to session data for context
            if "errors" not in context.session_data:
                context.session_data["errors"] = []
            
            context.session_data["errors"].append({
                "type": error_type,
                "message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def end_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """End conversation and return analytics"""
        context = self.conversations.get(conversation_id)
        if not context:
            return None
        
        # Calculate session duration
        duration = (context.last_activity - context.started_at).total_seconds()
        
        # Update user profile with session data
        user_profile = self.user_profiles.get(context.user_id)
        if user_profile:
            # Update average session duration
            total_sessions = user_profile.conversation_count
            user_profile.average_session_duration = (
                (user_profile.average_session_duration * (total_sessions - 1) + duration) / total_sessions
            )
        
        # Generate analytics
        analytics = self.analytics.analyze_conversation_quality(context)
        
        # Mark conversation as completed
        context.state = ConversationState.COMPLETED
        
        self.logger.info("Conversation ended", 
                        conversation_id=conversation_id,
                        duration_seconds=duration,
                        message_count=context.message_count,
                        successful_generations=context.successful_generations)
        
        return {
            "conversation_summary": context.to_dict(),
            "analytics": analytics,
            "user_insights": self.analytics.generate_user_insights(user_profile) if user_profile else {}
        }
    
    async def cleanup_expired_conversations(self):
        """Clean up expired conversations"""
        now = datetime.now(timezone.utc)
        expired_conversations = []
        
        for conv_id, context in self.conversations.items():
            time_since_last = now - context.last_activity
            if time_since_last.total_seconds() > self.session_timeout_minutes * 60:
                expired_conversations.append(conv_id)
        
        for conv_id in expired_conversations:
            await self.end_conversation(conv_id)
            del self.conversations[conv_id]
        
        if expired_conversations:
            self.logger.info("Cleaned up expired conversations", count=len(expired_conversations))
    
    async def get_conversation_analytics(self) -> Dict[str, Any]:
        """Get overall conversation analytics"""
        total_conversations = len(self.conversations)
        total_users = len(self.user_profiles)
        
        if total_conversations == 0:
            return {
                "total_conversations": 0,
                "total_users": 0,
                "average_quality_score": 0.0
            }
        
        # Calculate averages
        total_messages = sum(ctx.message_count for ctx in self.conversations.values())
        total_successes = sum(ctx.successful_generations for ctx in self.conversations.values())
        total_errors = sum(ctx.error_count for ctx in self.conversations.values())
        
        quality_scores = []
        for context in self.conversations.values():
            analytics = self.analytics.analyze_conversation_quality(context)
            quality_scores.append(analytics["quality_score"])
        
        return {
            "total_conversations": total_conversations,
            "total_users": total_users,
            "total_messages": total_messages,
            "total_successes": total_successes,
            "total_errors": total_errors,
            "average_quality_score": sum(quality_scores) / len(quality_scores),
            "success_rate": total_successes / max(1, total_messages),
            "error_rate": total_errors / max(1, total_messages)
        }


# Global conversation manager instance
_conversation_manager: Optional[AdvancedConversationManager] = None


async def get_conversation_manager() -> AdvancedConversationManager:
    """Get conversation manager instance"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = AdvancedConversationManager()
    return _conversation_manager