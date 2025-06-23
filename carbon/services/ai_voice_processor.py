"""
Real AI Voice Processing Service for Agricultural Events
========================================================

This service uses OpenAI's GPT models to intelligently parse voice inputs
and extract structured agricultural event data with high accuracy.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize global OpenAI clients
openai_client = None
async_openai_client = None
try:
    OPENAI_AVAILABLE =  getattr(settings, 'OPENAI_AVAILABLE', False)
    if OPENAI_AVAILABLE and hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        async_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI clients initialized successfully")
    else:
        logger.warning("OpenAI clients not available - missing API key or library")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI clients: {e}")
    openai_client = None
    async_openai_client = None


class AIVoiceProcessor:
    """
    AI-powered voice processing for agricultural events using OpenAI GPT models.
    
    This replaces the mock pattern matching with real AI that understands
    natural language and can extract complex agricultural event information.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4')
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 500)
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.3)
        
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not installed. Voice processing will use fallback methods.")
            return
            
        if not self.api_key:
            logger.warning("OpenAI API key not configured. Voice processing will use fallback methods.")
            return
            
        # Initialize OpenAI client
        self.openai = OpenAI(api_key=self.api_key)
        
    def process_voice_input(self, 
                          transcript: str, 
                          crop_type: str, 
                          language: str = 'en-US') -> Dict[str, Any]:
        """
        Process voice input using AI to extract structured agricultural event data.
        
        Args:
            transcript: The voice transcript to process
            crop_type: The crop type context (e.g., "strawberries", "corn")
            language: Language code (e.g., 'en-US', 'es-ES', 'pt-BR')
            
        Returns:
            Structured event data with confidence scores and extracted information
        """
        start_time = time.time()
        
        try:
            if not OPENAI_AVAILABLE or not self.api_key:
                return self._fallback_processing(transcript, crop_type, language)
                
            # Create AI prompt for agricultural event extraction
            prompt = self._create_extraction_prompt(transcript, crop_type, language)
            
            # Call OpenAI API
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(language)
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse AI response
            ai_response = json.loads(response.choices[0].message.content)
            processing_time = (time.time() - start_time) * 1000
            
            # Structure the response
            result = self._structure_ai_response(ai_response, transcript, processing_time)
            
            logger.info(f"AI voice processing completed in {processing_time:.0f}ms with {result['confidence']}% confidence")
            return result
            
        except Exception as e:
            logger.error(f"AI voice processing failed: {e}")
            return self._fallback_processing(transcript, crop_type, language)
    
    def _get_system_prompt(self, language: str) -> str:
        """Get the system prompt for the AI model based on language."""
        
        prompts = {
            'en-US': """You are an expert agricultural assistant specializing in carbon footprint tracking for farms. 
            Your job is to parse voice inputs from farmers and extract structured information about farm activities.
            
            You must respond with valid JSON containing these fields:
            - event_type: One of [fertilization, irrigation, pesticide, equipment, harvest, planting, soil_management, general]
            - confidence: Integer 0-100 representing your confidence in the classification
            - detected_amounts: Array of amounts with units (e.g., ["50 pounds", "2 hours", "1.5 acres"])
            - detected_products: Array of products mentioned (e.g., ["NPK fertilizer", "glyphosate", "diesel"])
            - detected_systems: Array of systems/methods (e.g., ["drip irrigation", "broadcast", "tractor"])
            - area_covered: Estimated area if mentioned or can be inferred
            - duration: Time duration if mentioned
            - carbon_impact_estimate: Estimated CO2e impact in kg (be conservative)
            - description: Clean, professional description of the activity
            - recommendations: Array of efficiency or carbon reduction suggestions
            
            Focus on accuracy and be conservative with estimates. If unsure, indicate lower confidence.""",
            
            'es-ES': """Eres un asistente agrícola experto especializado en seguimiento de huella de carbono para granjas.
            Tu trabajo es analizar entradas de voz de agricultores y extraer información estructurada sobre actividades agrícolas.
            
            Debes responder con JSON válido conteniendo estos campos:
            - event_type: Uno de [fertilization, irrigation, pesticide, equipment, harvest, planting, soil_management, general]
            - confidence: Entero 0-100 representando tu confianza en la clasificación
            - detected_amounts: Array de cantidades con unidades
            - detected_products: Array de productos mencionados
            - detected_systems: Array de sistemas/métodos
            - area_covered: Área estimada si se menciona
            - duration: Duración si se menciona
            - carbon_impact_estimate: Impacto estimado de CO2e en kg
            - description: Descripción limpia y profesional de la actividad
            - recommendations: Array de sugerencias de eficiencia o reducción de carbono""",
            
            'pt-BR': """Você é um assistente agrícola especialista em rastreamento de pegada de carbono para fazendas.
            Seu trabalho é analisar entradas de voz de agricultores e extrair informações estruturadas sobre atividades agrícolas.
            
            Você deve responder com JSON válido contendo estes campos:
            - event_type: Um de [fertilization, irrigation, pesticide, equipment, harvest, planting, soil_management, general]
            - confidence: Inteiro 0-100 representando sua confiança na classificação
            - detected_amounts: Array de quantidades com unidades
            - detected_products: Array de produtos mencionados
            - detected_systems: Array de sistemas/métodos
            - area_covered: Área estimada se mencionada
            - duration: Duração se mencionada
            - carbon_impact_estimate: Impacto estimado de CO2e em kg
            - description: Descrição limpa e profissional da atividade
            - recommendations: Array de sugestões de eficiência ou redução de carbono"""
        }
        
        return prompts.get(language, prompts['en-US'])
    
    def _create_extraction_prompt(self, transcript: str, crop_type: str, language: str) -> str:
        """Create the extraction prompt for the AI model."""
        
        prompts = {
            'en-US': f"""Parse this farmer's voice input and extract agricultural event information:

Voice Input: "{transcript}"
Crop Type: {crop_type}
Date: Today

Extract and structure the agricultural activity information. Consider:
- What type of farm activity was performed?
- What amounts, products, or equipment were mentioned?
- What area was covered or time duration?
- Estimate the carbon impact based on the activity type and scale

Respond with JSON only.""",

            'es-ES': f"""Analiza esta entrada de voz del agricultor y extrae información del evento agrícola:

Entrada de Voz: "{transcript}"
Tipo de Cultivo: {crop_type}
Fecha: Hoy

Extrae y estructura la información de la actividad agrícola. Considera:
- ¿Qué tipo de actividad agrícola se realizó?
- ¿Qué cantidades, productos o equipos se mencionaron?
- ¿Qué área se cubrió o duración de tiempo?
- Estima el impacto de carbono basado en el tipo y escala de actividad

Responde solo con JSON.""",

            'pt-BR': f"""Analise esta entrada de voz do agricultor e extraia informações do evento agrícola:

Entrada de Voz: "{transcript}"
Tipo de Cultura: {crop_type}
Data: Hoje

Extraia e estruture as informações da atividade agrícola. Considere:
- Que tipo de atividade agrícola foi realizada?
- Que quantidades, produtos ou equipamentos foram mencionados?
- Que área foi coberta ou duração de tempo?
- Estime o impacto de carbono baseado no tipo e escala da atividade

Responda apenas com JSON."""
        }
        
        return prompts.get(language, prompts['en-US'])
    
    def _structure_ai_response(self, ai_response: Dict[str, Any], original_transcript: str, processing_time: float) -> Dict[str, Any]:
        """Structure the AI response into the expected format."""
        
        return {
            'type': ai_response.get('event_type', 'general'),
            'description': ai_response.get('description', original_transcript),
            'date': time.strftime('%Y-%m-%d'),
            'detected_amounts': ai_response.get('detected_amounts', []),
            'detected_products': ai_response.get('detected_products', []),
            'detected_systems': ai_response.get('detected_systems', []),
            'confidence': min(max(ai_response.get('confidence', 0), 0), 100),
            'suggested_carbon_impact': ai_response.get('carbon_impact_estimate', 0),
            'area_covered': ai_response.get('area_covered', ''),
            'duration': ai_response.get('duration', ''),
            'recommendations': ai_response.get('recommendations', []),
            'processing_time': processing_time,
            'source': 'openai_gpt',
            'model_used': self.model,
            'raw_ai_response': ai_response,
            'original_transcript': original_transcript
        }
    
    def _fallback_processing(self, transcript: str, crop_type: str, language: str) -> Dict[str, Any]:
        """
        Fallback processing when AI is not available.
        Uses improved pattern matching as backup.
        """
        logger.info("Using fallback pattern matching for voice processing")
        
        # Enhanced pattern matching (better than current mock)
        patterns = {
            'fertilization': {
                'keywords': ['fertilizer', 'fertilize', 'applied', 'spread', 'npk', 'nitrogen', 'phosphorus', 'potassium'],
                'es': ['fertilizante', 'fertilizar', 'aplicar', 'esparcir', 'npk', 'nitrógeno'],
                'pt': ['fertilizante', 'fertilizar', 'aplicar', 'espalhar', 'npk', 'nitrogênio']
            },
            'irrigation': {
                'keywords': ['irrigate', 'irrigation', 'water', 'watered', 'sprinkler', 'drip', 'flood'],
                'es': ['irrigar', 'irrigación', 'regar', 'agua', 'aspersores', 'goteo'],
                'pt': ['irrigar', 'irrigação', 'regar', 'água', 'aspersores', 'gotejamento']
            },
            'pesticide': {
                'keywords': ['spray', 'sprayed', 'pesticide', 'herbicide', 'insecticide', 'fungicide'],
                'es': ['rociar', 'pesticida', 'herbicida', 'insecticida', 'fungicida'],
                'pt': ['pulverizar', 'pesticida', 'herbicida', 'inseticida', 'fungicida']
            },
            'equipment': {
                'keywords': ['tractor', 'equipment', 'machine', 'fuel', 'diesel', 'mowed', 'plowed'],
                'es': ['tractor', 'equipo', 'máquina', 'combustible', 'diésel', 'cortado', 'arado'],
                'pt': ['trator', 'equipamento', 'máquina', 'combustível', 'diesel', 'cortado', 'arado']
            },
            'harvest': {
                'keywords': ['harvest', 'harvested', 'picked', 'collected', 'yield'],
                'es': ['cosechar', 'cosechado', 'recoger', 'recolectar', 'rendimiento'],
                'pt': ['colher', 'colhido', 'colher', 'coletar', 'rendimento']
            }
        }
        
        text_lower = transcript.lower()
        detected_type = 'general'
        confidence = 30  # Lower confidence for fallback
        
        # Detect event type
        lang_suffix = 'es' if language == 'es-ES' else 'pt' if language == 'pt-BR' else 'keywords'
        
        for event_type, pattern_data in patterns.items():
            keywords = pattern_data.get(lang_suffix, pattern_data['keywords'])
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > 0:
                detected_type = event_type
                confidence = min(30 + matches * 15, 75)  # Max 75% for fallback
                break
        
        # Extract amounts using regex
        import re
        amount_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:pounds?|lbs?|kg|kilograms?|tons?|libras?|quilos?)',
            r'(\d+(?:\.\d+)?)\s*(?:gallons?|liters?|litros?)',
            r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|horas?)',
            r'(\d+(?:\.\d+)?)\s*(?:acres?|hectares?|hectáreas?)'
        ]
        
        detected_amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            detected_amounts.extend(matches)
        
        return {
            'type': detected_type,
            'description': transcript,
            'date': time.strftime('%Y-%m-%d'),
            'detected_amounts': detected_amounts,
            'detected_products': [],
            'detected_systems': [],
            'confidence': confidence,
            'suggested_carbon_impact': self._estimate_carbon_fallback(detected_type, detected_amounts),
            'processing_time': 50,  # Simulated fast processing
            'source': 'pattern_matching_fallback',
            'original_transcript': transcript
        }
    
    def _estimate_carbon_fallback(self, event_type: str, amounts: List[str]) -> float:
        """Estimate carbon impact for fallback processing."""
        
        base_impacts = {
            'fertilization': 2.5,
            'irrigation': 1.5,
            'pesticide': 3.0,
            'equipment': 8.0,
            'harvest': 1.0,
            'general': 1.0
        }
        
        base = base_impacts.get(event_type, 1.0)
        
        # Scale based on detected amounts
        if amounts:
            try:
                first_amount = float(amounts[0])
                return round(base * (first_amount / 10), 2)
            except (ValueError, IndexError):
                pass
                
        return base


def process_voice_with_ai(transcript: str, crop_type: str, language: str = 'en-US') -> Dict[str, Any]:
    """
    Synchronous wrapper for async AI processing
    """
    import asyncio
    
    try:
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(AIVoiceProcessor().process_voice_input_async(transcript, crop_type, language))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error in async voice processing: {e}")
        # Fallback to synchronous processing
        processor = AIVoiceProcessor()
        return processor.process_voice_input(transcript, crop_type, language)


async def _fetch_recent_events_from_db(establishment_id: str, parcel_id: str) -> list:
    """
    Fetch recent events from the database for AI context.
    Returns a list of recent event descriptions for the last 30 days.
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    from history.models import History
    from django.db.models import Q
    import asyncio
    from asgiref.sync import sync_to_async
    
    try:
        # Calculate 30 days ago
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Query recent histories for this parcel
        @sync_to_async
        def get_recent_histories():
            return list(History.objects.filter(
                parcel_id=parcel_id,
                parcel__establishment_id=establishment_id,
                start_date__gte=thirty_days_ago
            ).prefetch_related(
                'history_weatherevent_events',
                'history_chemicalevent_events', 
                'history_productionevent_events',
                'history_generalevent_events',
                'history_equipmentevent_events',
                'history_soilmanagementevent_events',
                'history_pestmanagementevent_events'
            ))
        
        histories = await get_recent_histories()
        recent_events = []
        
        for history in histories:
            # Get all events from this history
            all_events = []
            
            # Weather events
            for event in history.history_weatherevent_events.all():
                event_type = 'weather'
                if hasattr(event, 'type'):
                    event_type = f"weather:{event.type}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
            
            # Chemical events
            for event in history.history_chemicalevent_events.all():
                event_type = 'chemical'
                if hasattr(event, 'commercial_name') and event.commercial_name:
                    event_type = f"chemical:{event.commercial_name}"
                elif hasattr(event, 'type'):
                    event_type = f"chemical:{event.type}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
            
            # Production events
            for event in history.history_productionevent_events.all():
                event_type = 'production'
                if hasattr(event, 'type'):
                    if event.type == 'IR':
                        event_type = 'irrigation'
                    elif event.type == 'HA':
                        event_type = 'harvest'
                    elif event.type == 'PR':
                        event_type = 'pruning'
                    else:
                        event_type = f"production:{event.type}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
            
            # Equipment events
            for event in history.history_equipmentevent_events.all():
                event_type = 'equipment'
                if hasattr(event, 'equipment_name') and event.equipment_name:
                    event_type = f"equipment:{event.equipment_name}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
            
            # General events
            for event in history.history_generalevent_events.all():
                event_type = 'general'
                if hasattr(event, 'name') and event.name:
                    event_type = f"general:{event.name}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
            
            # Soil management events
            for event in history.history_soilmanagementevent_events.all():
                event_type = 'soil_management'
                if hasattr(event, 'type'):
                    event_type = f"soil_management:{event.type}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
            
            # Pest management events
            for event in history.history_pestmanagementevent_events.all():
                event_type = 'pest_management'
                if hasattr(event, 'type'):
                    event_type = f"pest_management:{event.type}"
                all_events.append((event.date, event_type, getattr(event, 'observation', '')))
        
        # Sort all events by date (most recent first) and format for AI
        all_events.sort(key=lambda x: x[0], reverse=True)
        
        for event_date, event_type, observation in all_events[:10]:  # Limit to 10 most recent
            days_ago = (timezone.now() - event_date).days
            event_description = f"{event_type}:{days_ago}d_ago"
            if observation and len(observation) < 50:  # Add brief observation if available
                event_description += f"({observation[:30]}...)"
            recent_events.append(event_description)
        
        logger.info(f"Fetched {len(recent_events)} recent events for establishment {establishment_id}, parcel {parcel_id}")
        return recent_events
        
    except Exception as e:
        logger.error(f"Error fetching recent events from database: {e}")
        return []


async def generate_ai_event_suggestions(
    crop_type: str,
    location: str = None,
    season: str = None,
    recent_events: list = None,  # Keep for backward compatibility but will be ignored
    farm_context: dict = None
) -> dict:
    """
    Generate AI-powered event suggestions for agricultural activities.
    Now fetches recent events directly from the database for better context.
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    import json
    
    try:
        # Extract establishment and parcel info from farm_context
        establishment_id = farm_context.get('establishment_id') if farm_context else None
        parcel_id = farm_context.get('parcel_id') if farm_context else None
        
        # Check if OpenAI is available
        if not async_openai_client:
            logger.warning("OpenAI client not available, using fallback suggestions")
            return _generate_fallback_suggestions(crop_type, season, location)
        
        # 🆕 Fetch recent events directly from database
        recent_events_context = []
        if establishment_id and parcel_id:
            recent_events_context = await _fetch_recent_events_from_db(establishment_id, parcel_id)
        
        # Determine season if not provided
        if not season:
            season = _get_season_from_month(datetime.now().month)
        
        # Build context information for AI
        context_info = f"Crop Type: {crop_type}\nSeason: {season.title()}"
        
        if location:
            context_info += f"\nLocation: {location}"
        
        if recent_events_context:
            context_info += f"\nRecent Events (last 30 days): {', '.join(recent_events_context)}"
        
        if farm_context:
            context_info += f"\nFarm Context: {json.dumps(farm_context, indent=2)}"
        
        # Create AI prompt for smart suggestions
        system_prompt = """You are an expert agricultural advisor specializing in carbon-smart farming practices. 
        Generate 3 intelligent, context-aware event suggestions for farmers based on their crop type, season, location, and recent activities.
        
        Focus on:
        1. Seasonal timing and relevance
        2. Carbon impact optimization (both reduction and sequestration opportunities)
        3. Practical implementation
        4. Cost-effectiveness
        5. Consumer visibility for QR code transparency
        
        Provide suggestions that are:
        - Timely for the current season
        - Carbon-focused (emphasize carbon benefits)
        - Practical and implementable
        - Varying in priority (high/medium/low)
        - Include efficiency tips and best practices
        
        Return ONLY a valid JSON object with this exact structure:
        {
            "suggestions": [
                {
                    "id": "unique_id",
                    "name": "Event Name",
                    "description": "Brief description",
                    "reasoning": "Why this suggestion is relevant now",
                    "carbon_impact": 25.5,
                    "priority": "high|medium|low",
                    "confidence": 85,
                    "timing_relevance": "Perfect timing for current season",
                    "efficiency_tips": ["tip1", "tip2"],
                    "estimated_duration": "2-3 hours",
                    "category": "fertilization|irrigation|pest_control|harvest|equipment|soil_management",
                    "seasonal_relevance": 90,
                    "best_practices": ["practice1", "practice2"]
                }
            ],
            "reasoning": "Overall reasoning for these suggestions",
            "ai_confidence": 85
        }"""
        
        user_prompt = f"""
        Generate smart agricultural event suggestions for:
        {context_info}
        
        Current month: {datetime.now().strftime('%B')}
        
        Consider typical {crop_type} farming calendar for {season} season.
        Focus on carbon transparency and consumer-visible sustainability practices.
        """
        
        # Call OpenAI API
        response = await async_openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,  # Allow some creativity while maintaining consistency
            max_tokens=1500,
            timeout=15.0
        )
        
        # Parse AI response
        ai_content = response.choices[0].message.content.strip()
        
        # Clean up the response (remove any markdown formatting)
        if ai_content.startswith('```json'):
            ai_content = ai_content[7:]
        if ai_content.endswith('```'):
            ai_content = ai_content[:-3]
        
        try:
            ai_suggestions = json.loads(ai_content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI suggestions JSON: {e}")
            return _generate_fallback_suggestions(crop_type, season, location)
        
        # Validate and enhance the AI response
        if not ai_suggestions.get('suggestions'):
            return _generate_fallback_suggestions(crop_type, season, location)
        
        # Add metadata
        result = {
            **ai_suggestions,
            "context": {
                "season": season,
                "crop_type": crop_type,
                "location": location,
                "current_month": datetime.now().month
            },
            "generated_at": datetime.now().isoformat(),
            "ai_powered": True,
            "processing_time": 0.8  # Approximate
        }
        
        logger.info(f"Generated AI event suggestions for {crop_type} in {season}")
        return result
        
    except Exception as e:
        logger.error(f"Error generating AI event suggestions: {e}")
        return _generate_fallback_suggestions(crop_type, season, location)


def _generate_fallback_suggestions(crop_type: str, season: str = None, location: str = None) -> dict:
    """
    Generate fallback suggestions when AI is unavailable.
    """
    current_month = datetime.now().month
    season = season or _get_season_from_month(current_month)
    
    # Season-based suggestions
    seasonal_suggestions = {
        'spring': [
            {
                "id": f"spring_soil_prep_{crop_type}",
                "name": "Soil Preparation & Testing",
                "description": "Prepare soil and conduct nutrient analysis for optimal growing conditions",
                "reasoning": "Spring is ideal for soil preparation and testing before planting season",
                "carbon_impact": 15.0,
                "priority": "high",
                "confidence": 75,
                "timing_relevance": "Perfect timing for spring soil preparation",
                "efficiency_tips": ["Test soil pH and nutrients", "Add organic matter to improve soil health"],
                "estimated_duration": "3-4 hours",
                "category": "soil_management",
                "seasonal_relevance": 95,
                "best_practices": ["Use organic amendments", "Test before applying fertilizers"]
            },
            {
                "id": f"spring_planting_{crop_type}",
                "name": "Precision Planting",
                "description": "Plant crops using precision agriculture techniques for optimal yield",
                "reasoning": "Spring planting season with focus on precision for carbon efficiency",
                "carbon_impact": -5.0,  # Negative = carbon sequestration
                "priority": "high",
                "confidence": 80,
                "timing_relevance": "Optimal spring planting window",
                "efficiency_tips": ["Use GPS guidance", "Optimize plant spacing"],
                "estimated_duration": "6-8 hours",
                "category": "equipment",
                "seasonal_relevance": 90,
                "best_practices": ["Precision seed placement", "Soil moisture monitoring"]
            }
        ],
        'summer': [
            {
                "id": f"summer_irrigation_{crop_type}",
                "name": "Smart Irrigation Management",
                "description": "Implement efficient irrigation systems to optimize water use",
                "reasoning": "Summer heat requires efficient water management for crop health and carbon efficiency",
                "carbon_impact": 20.0,
                "priority": "high",
                "confidence": 85,
                "timing_relevance": "Critical for summer crop management",
                "efficiency_tips": ["Use soil moisture sensors", "Schedule irrigation during cooler hours"],
                "estimated_duration": "2-3 hours setup",
                "category": "irrigation",
                "seasonal_relevance": 95,
                "best_practices": ["Drip irrigation systems", "Smart controllers"]
            },
            {
                "id": f"summer_pest_monitoring_{crop_type}",
                "name": "Integrated Pest Monitoring",
                "description": "Monitor and manage pests using sustainable IPM practices",
                "reasoning": "Summer pest pressure requires proactive, sustainable management",
                "carbon_impact": 12.0,
                "priority": "medium",
                "confidence": 75,
                "timing_relevance": "Peak pest activity season",
                "efficiency_tips": ["Regular scouting", "Use beneficial insects"],
                "estimated_duration": "1-2 hours weekly",
                "category": "pest_control",
                "seasonal_relevance": 85,
                "best_practices": ["IPM protocols", "Biological controls"]
            }
        ],
        'fall': [
            {
                "id": f"fall_harvest_{crop_type}",
                "name": "Efficient Harvest Operations",
                "description": "Harvest crops using fuel-efficient equipment and timing",
                "reasoning": "Fall harvest season with focus on efficiency and carbon optimization",
                "carbon_impact": 35.0,
                "priority": "high",
                "confidence": 90,
                "timing_relevance": "Peak harvest season",
                "efficiency_tips": ["Optimize equipment routes", "Monitor fuel consumption"],
                "estimated_duration": "8-12 hours",
                "category": "harvest",
                "seasonal_relevance": 95,
                "best_practices": ["Equipment maintenance", "Fuel efficiency monitoring"]
            },
            {
                "id": f"fall_cover_crops_{crop_type}",
                "name": "Cover Crop Establishment",
                "description": "Plant cover crops for soil health and carbon sequestration",
                "reasoning": "Fall is ideal for establishing cover crops for winter soil protection",
                "carbon_impact": -25.0,  # Negative = carbon sequestration
                "priority": "medium",
                "confidence": 80,
                "timing_relevance": "Optimal cover crop planting window",
                "efficiency_tips": ["Choose appropriate species", "Consider nitrogen fixers"],
                "estimated_duration": "4-6 hours",
                "category": "soil_management",
                "seasonal_relevance": 90,
                "best_practices": ["Diverse species mix", "No-till establishment"]
            }
        ],
        'winter': [
            {
                "id": f"winter_equipment_maintenance_{crop_type}",
                "name": "Equipment Winterization",
                "description": "Maintain and prepare equipment for next season efficiency",
                "reasoning": "Winter downtime is perfect for equipment maintenance and efficiency upgrades",
                "carbon_impact": 8.0,
                "priority": "medium",
                "confidence": 70,
                "timing_relevance": "Ideal maintenance window",
                "efficiency_tips": ["Service engines", "Check fuel systems"],
                "estimated_duration": "4-8 hours",
                "category": "equipment",
                "seasonal_relevance": 80,
                "best_practices": ["Preventive maintenance", "Fuel efficiency upgrades"]
            },
            {
                "id": f"winter_planning_{crop_type}",
                "name": "Carbon Planning & Analysis",
                "description": "Plan next season's carbon optimization strategies",
                "reasoning": "Winter planning time for analyzing carbon performance and planning improvements",
                "carbon_impact": 0.0,
                "priority": "low",
                "confidence": 65,
                "timing_relevance": "Good time for planning and analysis",
                "efficiency_tips": ["Review carbon data", "Plan efficiency improvements"],
                "estimated_duration": "2-4 hours",
                "category": "soil_management",
                "seasonal_relevance": 70,
                "best_practices": ["Data analysis", "Efficiency planning"]
            }
        ]
    }
    
    suggestions = seasonal_suggestions.get(season, seasonal_suggestions['summer'])[:3]
    
    return {
        "suggestions": suggestions,
        "reasoning": f"Fallback suggestions for {crop_type} during {season} season based on typical farming calendar and carbon best practices",
        "context": {
            "season": season,
            "crop_type": crop_type,
            "location": location,
            "current_month": current_month
        },
        "ai_confidence": 65,
        "generated_at": datetime.now().isoformat(),
        "ai_powered": False,
        "fallback_mode": True
    }


def _get_season_from_month(month: int) -> str:
    """Get season from month number."""
    if 3 <= month <= 5:
        return 'spring'
    elif 6 <= month <= 8:
        return 'summer'
    elif 9 <= month <= 11:
        return 'fall'
    else:
        return 'winter' 