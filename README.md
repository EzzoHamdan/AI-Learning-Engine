# 📚 AI Learning Engine

Transform your documents into **interactive quizzes** and **comprehensive study materials** using cutting-edge AI. Supports **Local AI (Ollama)**, **Google AI**, and **OpenAI** with complete privacy and flexibility.

## ✨ Key Features

### 🤖 **Multiple AI Provider Support**
- **🏠 Local AI (Ollama)**: Run completely locally - **FREE & 100% PRIVATE**
- **🆕 Google AI**: Latest Gemini models with excellent performance  
- **⚡ OpenAI**: Industry-standard GPT models
- **🔄 Dynamic Switching**: Change providers instantly without restart
- **🛡️ Graceful Fallbacks**: App works even if AI providers have issues

### 📚 **Comprehensive Study Materials**
- **📖 Complete Study Guides**: All-in-one packages with study plans
- **📝 Smart Summaries**: Detailed, concise, or bullet-point formats
- **📋 Reference Cheat Sheets**: Quick access to key concepts and formulas
- **🔄 Interactive Flashcards**: Self-paced learning with difficulty tracking
- **📊 Structured Outlines**: Hierarchical organization with time estimates
- **🔖 Key Terms & Definitions**: Essential vocabulary with context

### 🎯 **Advanced Quiz Generation**
- **🔘 Multiple Choice**: Traditional 4-option questions with smart distractors
- **✅ True/False**: Binary choice questions with detailed explanations
- **📝 Open-Ended Questions**: AI-scored written responses with rubric feedback
- **🎚️ Difficulty Scaling**: Standard, Advanced, and Extreme challenge levels
- **📊 Progress Tracking**: Real-time navigation and performance analytics

### 🔧 **User Experience**
- **📁 Multi-Format Support**: PDF, Word (DOCX), and PowerPoint (PPTX) files
- **⚙️ Runtime Configuration**: Enter API keys directly in the app
- **💾 Session Persistence**: Save settings and continue where you left off
- **🎨 Intuitive Interface**: Clean, responsive Streamlit-based UI
- **📱 Smart Responsive**: Works on desktop and mobile devices

## 🚀 Quick Start

### Option 1: Easy Setup Wizard (Recommended)
```bash
# Clone or download the repository
git clone <repository-url>
cd AI-Learning-Engine

# Run the setup wizard
python setup_easy.py
```

### Option 2: Manual Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
streamlit run app.py

# 3. Configure your AI provider in the sidebar
```

### Option 3: Local AI Setup (Best for Cost)
```bash
# 1. Install Ollama from https://ollama.ai
# 2. Start Ollama server
ollama serve

# 3. Pull a model, examples:
ollama pull gemma2:2b    
ollama pull gemma2:9b    
ollama pull gemma2:27b   

# 4. Run the app
streamlit run app.py
```

## 📖 How to Use

### For Interactive Quizzes:
1. **Upload Document**: Choose PDF, Word, or PowerPoint file
2. **Select "Interactive Quiz"** from generation type dropdown
3. **Configure Settings**: Question type, count, and difficulty
4. **Generate**: Click to create your personalized quiz
5. **Take Quiz**: Navigate through questions at your own pace
6. **Review Results**: Get detailed AI feedback and scoring

### For Study Materials:
1. **Upload Document**: Any supported format
2. **Select "Study Materials"** from generation type dropdown  
3. **Choose Material Type**: Summary, cheat sheet, flashcards, etc.
4. **Generate**: Create comprehensive study resources
5. **Study**: Use interactive features like flashcard self-testing
6. **Track Progress**: Monitor your learning with built-in analytics

### 🏠 Why Choose Local AI?

**Perfect for:**
- 🔒 **Privacy-conscious users**
- 💰 **Budget-conscious learners**  
- 🚀 **Frequent users** (no API costs)
- 🌐 **Offline environments**
- 🎓 **Educational institutions**

## 📁 Project Architecture

```
AI-Learning-Engine/
├── 📄 Core Application
│   ├── app.py                          # Main Streamlit application
│   ├── study_materials_generator.py    # Study materials engine
│   ├── open_ended_processor.py         # Quiz processing & AI scoring
│   └── session_manager.py              # Session state management
│
├── 🤖 AI Integration  
│   ├── ai_client_factory.py           # Multi-provider client factory
│   ├── google_ai_client.py            # Google AI wrapper
│   └── local_ai_client.py             # Local AI (Ollama) client
│
├── ⚙️ Configuration
│   ├── config.py                      # Application configuration
│   ├── auto_config.py                 # Auto-configuration utilities
│   └── setup_easy.py                  # Setup wizard
│
├── 🔧 Utilities
│   └── logger.py                      # Logging system
│
└── 📚 Documentation
    ├── README.md                      # This file
    └── requirements.txt               # Dependencies
```

## 🎓 Study Material Types

### 📖 Complete Study Guide
**Best for**: Comprehensive exam preparation
- ✅ Summary + Outline + Key Terms + Cheat Sheet + Flashcards
- ⏰ Suggested study plan with time estimates
- 🎯 Multiple complexity levels (comprehensive/exam_prep/quick_review)
- 📊 Progress tracking and session organization

### 📝 Smart Summaries  
**Best for**: Quick content review
- **Detailed**: Comprehensive overview with analysis
- **Concise**: Key points in paragraph form
- **Bullet Points**: Scannable list format
- 📊 Word count optimization and topic extraction

### 📋 Reference Cheat Sheets
**Best for**: Quick lookup during study
- **Comprehensive**: Full coverage with examples
- **Formulas**: Math and science equation focus
- **Definitions**: Terminology and concept focus
- **Quick Reference**: Ultra-concise essentials

### 🔄 Interactive Flashcards
**Best for**: Active recall practice
- 🎯 Self-assessment (correct/incorrect tracking)
- 🔀 Shuffle and replay functionality
- 📈 Difficulty distribution analysis
- 💡 Hint system for challenging concepts
- 📊 Progress statistics and performance metrics

### 📊 Structured Outlines
**Best for**: Organized learning paths
- 🏗️ Hierarchical organization (I, II, III... → A, B, C... → 1, 2, 3...)
- ⏱️ Time estimates for each section
- 🔗 Cross-references and connections
- 📚 Multiple depth levels (overview/detailed/comprehensive)

### 🔖 Key Terms & Definitions
**Best for**: Vocabulary building
- 📝 Essential terminology with clear definitions
- 🎯 Context and usage examples
- 🔗 Related concept connections
- 📊 Importance level categorization

## 🎚️ Difficulty Levels

### 📚 **Standard** 
University-level comprehension questions testing understanding of key concepts, definitions, and logical connections.

### 🎓 **Advanced**
Graduate-level questions requiring synthesis, evaluation, and critical thinking with scenario-based problems.

### 🔥 **Extreme**
Expert-level questions with manipulative elements, edge cases, and sophisticated analysis requiring doctoral-level expertise.

## 🔧 Configuration & Setup

### Environment Variables (.env file - optional)
```env
# Local AI (automatically detected)
LOCAL_AI_MODELL=""

# Google AI
GOOGLE_AI_API_KEY=your_google_ai_key_here

# OpenAI (optional)  
OPENAI_API_KEY=your_openai_key_here

# Debug mode
DEBUG=false
```

### Runtime Configuration
- 🔑 **API Keys**: Enter directly in the app sidebar
- 💾 **Save Settings**: Option to persist keys locally
- 🔄 **Provider Switching**: Change AI providers instantly
- ⚙️ **Model Selection**: Choose specific models for each provider 

## 📊 Performance & Scalability

### Document Processing
- **File Size**: Up to 50MB supported
- **Formats**: PDF, DOCX, PPTX with advanced text extraction

### Generation Speed
- **Quiz Generation**: 10-30 seconds (varies by complexity and amount of questions)
- **Study Materials**: 10-30 seconds (varies by material type and demanded task)
- **Local AI**: Hardware dependent
- **Cloud AI**: Network dependent

### Resource Usage Regarding Local AI
- **RAM**: 2-16GB (depends on Local AI model size)
- **Storage**: 500MB app + 1-30GB models (Local AI only)
- **CPU**: Modern processor recommended for Local AI

## 🔒 Privacy & Security

### Data Handling
- **Local AI**: ✅ **Zero data sharing** - everything stays on your device
- **Cloud AI**: ⚠️ Data sent to provider APIs (encrypted in transit)
- **No Analytics**: No usage tracking or data collection
- **Secure Storage**: API keys encrypted locally (optional)

### Best Practices
- 🏠 Use **Local AI** for cost-effectiveness
- 🔐 Never share API keys publicly
- 🔄 Rotate API keys regularly
- 💾 Use secure backup for important study materials

## 🛠️ Troubleshooting

### Common Issues
- **"No AI provider available"**: Configure API keys in sidebar or create a .env
- **Slow generation**: Try smaller Local AI models or check network
- **Upload errors**: Ensure file is under 50MB and valid format
- **Memory issues**: Use smaller models or close other applications

### Getting Help
1. 🔍 Check **Provider Status** in the app sidebar
2. 📊 Enable **Debug Mode** in configuration
3. 📝 Check terminal/console for error messages
4. 🔄 Try switching to different AI provider
5. 🌐 Verify internet connection for cloud providers

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd AI-Learning-Engine

# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Format code  
black .
isort .
flake8 .
```

## 🙏 Acknowledgments

- 🤖 **OpenAI** for GPT API and pioneering conversational AI
- 🆕 **Google AI** for Gemini models and accessible AI platform
- 🏠 **Ollama Team** for making local AI accessible to everyone
- 🎨 **Streamlit** for the amazing web app framework

**🎓 Built for learners, by a learner. Transform any document into an interactive learning experience today!**

*Made with ❤️ for educational excellence*
