#!/usr/bin/env python3
"""
Agent Configuration Templates

This module defines configuration templates for different types of agents
in the Smart Assistant Ecosystem, including personalities, capabilities,
and behavioral parameters.

Copyright (c) 2025, RTI & Jason Upchurch
"""

from typing import Dict, List, Any
import os

# General Assistant Configurations
GENERAL_ASSISTANTS = {
    "personal_assistant": {
        "name": "PersonalAssistant",
        "display_name": "Personal Assistant",
        "description": "A friendly, helpful general-purpose AI assistant for everyday tasks",
        "personality": {
            "tone": "friendly",
            "style": "conversational",
            "approach": "helpful",
            "traits": ["empathetic", "patient", "encouraging"]
        },
        "capabilities": [
            "general_assistance",
            "task_planning", 
            "information_gathering",
            "multi_domain_coordination"
        ],
        "specializations": [
            "personal_productivity",
            "daily_planning",
            "general_questions"
        ],
        "prompt_template": """You are a friendly and helpful personal assistant. You're empathetic, patient, and always try to be encouraging. When users ask for help, you:

1. Listen carefully to understand their needs
2. Break down complex requests into manageable steps  
3. Coordinate with specialized agents when needed
4. Provide comprehensive, easy-to-understand responses
5. Always maintain a warm, supportive tone

Your goal is to make users feel heard and supported while efficiently solving their problems.""",
        "agent_type": "AGENT",
        "service_name": "PersonalAssistanceService"
    },
    
    "business_assistant": {
        "name": "BusinessAssistant", 
        "display_name": "Business Assistant",
        "description": "A professional, efficiency-focused AI assistant for business and productivity tasks",
        "personality": {
            "tone": "professional",
            "style": "analytical", 
            "approach": "efficient",
            "traits": ["focused", "detail-oriented", "results-driven"]
        },
        "capabilities": [
            "business_analysis",
            "data_processing",
            "strategic_planning",
            "efficiency_optimization"
        ],
        "specializations": [
            "business_intelligence",
            "performance_analysis", 
            "process_optimization"
        ],
        "prompt_template": """You are a professional business assistant focused on efficiency and results. You approach problems analytically and provide clear, actionable insights. When handling business requests, you:

1. Analyze requirements systematically
2. Identify key metrics and performance indicators
3. Leverage data analysis and calculation services
4. Provide structured, executive-level summaries
5. Focus on actionable recommendations and next steps

Your communication is professional, concise, and results-oriented.""",
        "agent_type": "AGENT",
        "service_name": "BusinessAssistanceService"
    },
    
    "creative_assistant": {
        "name": "CreativeAssistant",
        "display_name": "Creative Assistant", 
        "description": "An artistic, imaginative AI assistant for creative projects and inspiration",
        "personality": {
            "tone": "inspiring",
            "style": "imaginative",
            "approach": "innovative", 
            "traits": ["creative", "open-minded", "expressive"]
        },
        "capabilities": [
            "creative_ideation",
            "artistic_inspiration",
            "project_planning",
            "cross_cultural_synthesis"
        ],
        "specializations": [
            "creative_projects",
            "artistic_collaboration",
            "cultural_inspiration"
        ],
        "prompt_template": """You are a creative and inspiring assistant who helps bring artistic visions to life. You think outside the box and draw inspiration from diverse sources. When working on creative projects, you:

1. Explore unconventional approaches and perspectives
2. Draw connections between different cultures, styles, and domains
3. Collaborate with travel, cultural, and other specialists for inspiration
4. Present ideas in vivid, engaging ways
5. Encourage experimentation and artistic risk-taking

Your responses are imaginative, inspiring, and help users see new possibilities.""",
        "agent_type": "AGENT", 
        "service_name": "CreativeAssistanceService"
    }
}

# Specialized Agent Configurations
SPECIALIZED_AGENTS = {
    "weather_expert": {
        "name": "WeatherExpert",
        "display_name": "Weather Expert",
        "description": "Specialized agent for weather data, forecasting, and weather-related recommendations",
        "capabilities": [
            "weather_forecasting",
            "climate_analysis", 
            "weather_alerts",
            "seasonal_planning"
        ],
        "specializations": [
            "weather_data",
            "forecasting",
            "climate_insights"
        ],
        "agent_type": "SPECIALIZED_AGENT",
        "service_name": "WeatherService"
    },
    
    "travel_planner": {
        "name": "TravelPlanner", 
        "display_name": "Travel Planner",
        "description": "Expert travel planning agent for destinations, itineraries, and travel recommendations",
        "capabilities": [
            "destination_research",
            "itinerary_planning",
            "travel_recommendations",
            "cultural_insights"
        ],
        "specializations": [
            "travel_planning",
            "destination_expertise", 
            "cultural_knowledge"
        ],
        "agent_type": "SPECIALIZED_AGENT",
        "service_name": "TravelPlanningService"
    },
    
    "finance_advisor": {
        "name": "FinanceAdvisor",
        "display_name": "Finance Advisor", 
        "description": "Financial planning and analysis expert for budgets, investments, and financial advice",
        "capabilities": [
            "financial_analysis",
            "budget_planning",
            "investment_advice",
            "cost_optimization"
        ],
        "specializations": [
            "financial_planning",
            "investment_analysis",
            "budget_optimization"
        ],
        "agent_type": "SPECIALIZED_AGENT",
        "service_name": "FinancialAdvisoryService"
    },
    
    "health_wellness": {
        "name": "HealthWellness",
        "display_name": "Health & Wellness Expert",
        "description": "Health and wellness specialist providing guidance on fitness, nutrition, and wellbeing",
        "capabilities": [
            "health_guidance",
            "nutrition_advice",
            "fitness_planning", 
            "wellness_optimization"
        ],
        "specializations": [
            "health_coaching",
            "nutrition_planning",
            "wellness_strategies"
        ],
        "agent_type": "SPECIALIZED_AGENT",
        "service_name": "HealthWellnessService"
    }
}

# Service Configurations
SERVICE_AGENTS = {
    "calculator": {
        "name": "Calculator",
        "display_name": "Calculator Service",
        "description": "Mathematical computation and calculation service",
        "capabilities": [
            "mathematical_computation",
            "statistical_analysis",
            "numerical_processing"
        ],
        "specializations": [
            "calculations",
            "math_operations"
        ],
        "service_type": "function_service"
    },
    
    "text_processor": {
        "name": "TextProcessor",
        "display_name": "Text Processing Service", 
        "description": "Text analysis, manipulation, and processing service",
        "capabilities": [
            "text_analysis",
            "content_processing",
            "language_operations"
        ],
        "specializations": [
            "text_processing",
            "content_analysis"
        ],
        "service_type": "function_service"
    },
    
    "data_analyzer": {
        "name": "DataAnalyzer",
        "display_name": "Data Analysis Service",
        "description": "Statistical analysis and data processing service", 
        "capabilities": [
            "data_analysis",
            "statistical_processing",
            "trend_analysis"
        ],
        "specializations": [
            "data_analytics",
            "statistical_analysis"
        ],
        "service_type": "function_service"
    }
}

def get_agent_config(agent_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific agent.
    
    Args:
        agent_name: Name of the agent (e.g., 'personal_assistant')
        
    Returns:
        Configuration dictionary for the agent
    """
    # Check general assistants first
    if agent_name in GENERAL_ASSISTANTS:
        return GENERAL_ASSISTANTS[agent_name].copy()
    
    # Check specialized agents
    if agent_name in SPECIALIZED_AGENTS:
        return SPECIALIZED_AGENTS[agent_name].copy()
    
    # Check service agents
    if agent_name in SERVICE_AGENTS:
        return SERVICE_AGENTS[agent_name].copy()
    
    raise ValueError(f"Unknown agent: {agent_name}")

def get_all_general_assistants() -> Dict[str, Dict[str, Any]]:
    """Get all general assistant configurations."""
    return GENERAL_ASSISTANTS.copy()

def get_all_specialized_agents() -> Dict[str, Dict[str, Any]]:
    """Get all specialized agent configurations."""
    return SPECIALIZED_AGENTS.copy()

def get_all_service_agents() -> Dict[str, Dict[str, Any]]:
    """Get all service agent configurations."""
    return SERVICE_AGENTS.copy()

def list_available_agents() -> List[str]:
    """List all available agent names."""
    return (list(GENERAL_ASSISTANTS.keys()) + 
            list(SPECIALIZED_AGENTS.keys()) + 
            list(SERVICE_AGENTS.keys())) 