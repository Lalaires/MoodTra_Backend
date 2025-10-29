# MoodTra Backend

This reopsitory contains comprehensive mental wellbeing support API for Australian teens (ages 13-15), providing AI wellbeing companion, mood tracking, coping strategies, and guardian-child linking capabilities.

## Table of Contents

- [Overview](#overview)
- [Links for MoodTra](#links-for-moodtra)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [License](#license)

## Overview

MoodTra is a mental wellbeing platform designed to support teenagers through:

- **AI wellbeing companion**: Empathetic conversations using Google Gemini with emotion detection, slang interpretation, personalized coping strategies suggestions and context awareness.
- **Mood Tracking**: Daily mood logging with emoji-based entries and calendar views
- **Coping Strategies**: Evidence-based strategies mapped to specific emotions
- **Guardian Linking**: Secure invite system connecting guardians with teens
- **Crisis Detection**: Automatic detection and intervention suggestions for crisis situations, see [MoodTra_Crisis_Detection](https://github.com/Lalaires/MoodTra_Crisis_Detection) for further implemenation details
- **Activity Tracking**: Monitor strategy usage and effectiveness

## Links for MoodTra
- Website: [MoodTra](https://moodtra.tech/)
- GitHub Repositories:
    - [MoodTra_Frontend](https://github.com/yihui1306/mindPal-frontend)
    - MoodTra_Backend - Current Repo
    - [MoodTra_Crisis_Detection](https://github.com/Lalaires/MoodTra_Crisis_Detection)

## Features

### Core Capabilities

- 🤖 **Intelligent Chat Assistant**: Age-appropriate, empathetic AI responses using Gemini 2.5 Flash
- 🌐 **Multi-Emotion Detection**: Advanced sentiment analysis using DistilRoBERTa
- 🎯 **Personalized Strategies**: Emotion-specific coping strategies with instructions
- 🚨 **Crisis Support**: Automatic detection with severity-based intervention strategies
- 👨‍👩‍👧 **Guardian Portal**: Secure linking system for parent/guardian oversight
- 📊 **Mood Analytics**: Track moods with weekly/monthly summaries and trend analysis
- 📝 **Activity Logging**: Track strategy usage and outcomes

### AI/ML Features

- End-to-end NLP pipeline including:
    - Emotion classification (7 emotions: joy, sadness, anger, fear, surprise, disgust, neutral)
    - Gen-Z slang detection and interpretation
    - Context-aware conversation history
    - Coping stretegy retrival and suggestion based on deteacted emotion
    - Crisis signal detection in chat patterns, see [MoodTra_Crisis_Detection](https://github.com/Lalaires/MoodTra_Crisis_Detection) for further implemenation details

## Tech Stack

### Backend Framework
- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **SQLAlchemy** - ORM and database toolkit
- **Pydantic** - Data validation

### Database
- **PostgreSQL 16** - Primary data store
- **asyncpg** - Async PostgreSQL driver

### AI/ML
- **Google Gemini 2.5 Flash** - Conversational AI
- **Transformers** (Emotion English DistilRoBERTa-base) - Emotion detection model
- **PyTorch** - ML framework (CPU optimized)

### Authentication
- **AWS Cognito** - User authentication
- **python-jose** - JWT token handling
- **OAuth 2.0** (Authorization Code + PKCE)

### Cloud & Infrastructure
- **Docker** - Containerization
- **AWS Lambda** - Serverless deployment (with Lambda Web Adapter)
- **AWS ECR** - Container registry
- **boto3** - AWS SDK

## Project Structure

```
MoodTra_Backend/
├── AI/
│   ├── __init__.py
│   └── pipeline.py              # AI/ML pipeline (emotion detection, chat)
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app initialization
│   ├── bootstrap.py             # Runtime setup
│   ├── db.py                    # Database connection
│   ├── deps.py                  # FastAPI dependencies
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic schemas
│   ├── utils.py                 # Utility functions
│   ├── auth/                    # Authentication utilities
│   └── routers/                 # API endpoints
│       ├── accounts.py          # Account management
│       ├── activity.py          # Activity tracking
│       ├── auth_session.py      # Cognito authentication
│       ├── chat.py               # AI chat endpoint
│       ├── chat_session.py      # Chat session management
│       ├── crisis.py            # Crisis alerts
│       ├── invites.py           # Guardian invitations
│       ├── links.py             # Guardian-child linking
│       ├── mood.py              # Mood logging
│       ├── strategy_emotion.py  # Coping strategies
│       └── wellbeing.py         # Parent communication tips
├── sql/
│   ├── schema.sql               # Database schema
│   ├── seed.sql                 # Seed data
│   ├── strategy.csv             # Coping strategies data
│   ├── strategy_emotion.csv     # Strategy-emotion mappings
│   ├── strategy_parent_conv_tip.csv
│   └── wellbeing_conv_tip.csv
├── config/                      # Configuration files
├── docker_scripts/              # Docker helper scripts
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
└── README.md
```

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Docker Desktop** or Docker CLI
- **PostgreSQL 16** (via Docker or local)
- **Git**
- **AWS Account** (for Cognito and deployment)
- **Google AI API Key** (for Gemini)

## Support

For issues, questions, or collaboration requests:
- Contact the development team - 📧 Email: claireaus066@gmail.com
- Check existing documentation in `/README_*.txt` files

## License

See `LICENSE` file for details.

---

**Built with ❤️ for Australian teens' mental wellbeing**

