# AI Interactive Quiz Generator

A streamlined Streamlit application that generates interactive quizzes from uploaded documents using **Local AI (Ollama)**, **Google AI**, or **OpenAI**.

## ✨ Features

- **🏠 Local AI Support**: Run completely locally with Ollama - FREE & PRIVATE!
- **🆕 Google AI Integration**: Powered by Google's Gemma models
- **⚡ OpenAI Support**: Traditional GPT models
- **📁 Multi-format Support**: PDF, Word (DOCX), and PowerPoint (PPTX) files
- **🎯 Interactive Quizzes**: Question-by-question navigation with progress tracking
- **📝 Multiple Question Types**: Multiple choice, True/False, and AI-scored open-ended questions
- **🎚️ Difficulty Levels**: Standard, Advanced, and Extreme challenge modes
- **🔒 Privacy First**: Local AI keeps your data completely private

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure AI Provider

**Option A: Local AI (Recommended - Free & Private)**
```bash
# Install Ollama from https://ollama.ai
ollama serve
ollama pull gemma2:2b  # or gemma2:9b for better quality
```

**Option B: Google AI**
- Get API key from [Google AI Studio](https://ai.google.dev/)
- Enter in the app sidebar

**Option C: OpenAI**
- Get API key from [OpenAI](https://platform.openai.com/)
- Enter in the app sidebar

### 3. Run Application
```bash
streamlit run app.py
```

## 📋 Usage

1. **Select AI Provider** in the sidebar and enter API key if needed
2. **Upload Document** (PDF, DOCX, or PPTX)
3. **Configure Quiz** (type, difficulty, number of questions)  
4. **Generate Quiz** and take it interactively
5. **Review Results** with detailed AI-powered feedback

## 📁 Project Structure

```
├── app.py                    # Main Streamlit application
├── ai_client_factory.py      # AI client factory pattern
├── config.py                 # Configuration management
├── exceptions.py             # Custom exception classes
├── google_ai_client.py       # Google AI client implementation
├── local_ai_client.py        # Local AI (Ollama) client
├── logger.py                 # Logging utilities
├── open_ended_processor.py   # Open-ended question processing
├── session_manager.py        # Session state management
├── requirements.txt          # Python dependencies
├── run.bat                  # Windows startup script
└── .env.example             # Environment variables template
```

## � Configuration

Create a `.env` file (optional - you can also configure in the app):
```env
# Google AI
GOOGLE_AI_API_KEY=your_google_ai_key_here

# OpenAI (optional)
OPENAI_API_KEY=your_openai_key_here

# Local AI (Ollama) - automatically detected
OLLAMA_BASE_URL=http://localhost:11434/v1
```

## 🏠 Local AI Setup

For the best experience (free, private, no API costs):

1. **Install Ollama**: Download from [ollama.ai](https://ollama.ai)
2. **Start Server**: `ollama serve`
3. **Install Model**: `ollama pull gemma2:2b` (2GB RAM) or `gemma2:9b` (6GB RAM)
4. **Use in App**: Select "Local AI (Ollama)" in the sidebar

## 🎯 Question Types

- **Multiple Choice**: Traditional 4-option questions
- **True/False**: Binary choice questions
- **Open-ended**: Write detailed answers scored by AI with rubric-based feedback
- **Mixed**: Combination of all types

## 🎚️ Difficulty Levels

- **Standard**: University-level comprehension questions
- **Advanced**: Graduate-level analysis and synthesis
- **Extreme**: Expert-level with tricky, nuanced questions

## 📊 AI Scoring

Open-ended questions are scored using advanced AI with:
- **Rubric-based evaluation** with multiple criteria
- **Detailed feedback** on strengths and improvements
- **Model answers** for comparison
- **Percentage scores** with comprehensive breakdown

## 🔒 Privacy & Security

- **Local AI**: Your documents never leave your computer
- **Secure API Keys**: Entered directly in app, optionally saved locally
- **No Data Collection**: No analytics or tracking

## 🤝 Support

For issues or questions:
1. Check that your AI provider is properly configured
2. Verify your API keys are correct
3. Ensure Ollama is running if using Local AI
4. Check the console for error messages

---

**Made with ❤️ for educational excellence**
cd ai-quiz-generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Copy the example environment file
cp .env.example .env

# Choose ONE of the following options:

# Option A: Local AI (RECOMMENDED - FREE & PRIVATE)
USE_LOCAL_AI=true
USE_GOOGLE_AI=false
# Follow LOCAL_AI_SETUP.md for Ollama installation

# Option B: Google AI (Gemma 3)
USE_LOCAL_AI=false
USE_GOOGLE_AI=true
GOOGLE_AI_API_KEY=your_google_ai_api_key_here

# Option C: OpenAI (fallback)
USE_LOCAL_AI=false
USE_GOOGLE_AI=false  
OPENAI_API_KEY=your_openai_api_key_here
```

4. **For Local AI Setup** (see [LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md) for detailed guide):
```bash
# Install Ollama from https://ollama.ai
# Start Ollama server
ollama serve

# Download Gemma model (in a new terminal)
ollama pull gemma2:2b
```

5. Run the application:
```bash
streamlit run app.py
```

## 🏠 Local AI Setup (Recommended)

**Why Local AI?**
- ✅ **Completely FREE** - No API costs
- 🔒 **100% Private** - Data never leaves your computer
- 🚀 **Fast & Offline** - Works without internet
- 📱 **Always Available** - No rate limits

**Quick Local Setup:**
```bash
# 1. Install Ollama (visit ollama.ai)
# 2. Start server
ollama serve

# 3. Download model
ollama pull gemma2:2b

# 4. Update .env
USE_LOCAL_AI=true
```

For detailed setup instructions, see **[LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md)**

## 🤖 AI Provider Comparison

| Feature | Local AI | Google AI | OpenAI |
|---------|----------|-----------|--------|
| Cost | 🆓 FREE | 💰 Paid | 💰 Paid |
| Privacy | 🔒 100% Private | ⚠️ Shared | ⚠️ Shared |
| Speed | 🚀 Fast | 🌐 Network dependent | 🌐 Network dependent |
| Setup | 📦 One-time | 🔑 API key | 🔑 API key |
| Quality | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 🤖 AI Provider Configuration

### Google AI (Gemma 3) - **Default & Recommended**

- **Models Used**: `gemma-3-27b-it` for both generation and scoring
- **Benefits**: Superior performance, multimodal capabilities, 128K context window
- **Setup**: Get your API key from [Google AI Studio](https://aistudio.google.com/apikey)

### OpenAI - **Fallback Option**  

- **Models Used**: `gpt-3.5-turbo` for generation, `gpt-4` for scoring
- **Setup**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)

## 📁 Project Structure

```
├── app.py                 # Main Streamlit application  
├── config.py             # Configuration settings
├── google_ai_client.py   # Google AI (Gemma 3) client wrapper
├── document_processor.py # Document text extraction
├── open_ended_processor.py # Open-ended question handling
├── exceptions.py         # Custom exception classes
├── logger.py             # Logging configuration
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── tests/               # Test suite
└── logs/                # Application logs
```

## 🎯 Usage

1. **Upload Document**: Select a PDF, Word, or PowerPoint file
2. **Configure Quiz**: Choose question type, difficulty, and number of questions
3. **Generate Quiz**: Click "Generate Interactive Quiz"
4. **Take Quiz**: Navigate through questions at your own pace
5. **Review Results**: Get detailed feedback and performance analysis

## 🔧 Configuration

The application supports various configuration options through `config.py`:

- **Quiz Settings**: Question limits, supported formats, text processing thresholds
- **Difficulty Levels**: Customizable difficulty configurations with scoring criteria
- **API Settings**: OpenAI model selection and temperature settings
- **UI Settings**: Application title, icons, and layout options

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_quiz_generator.py
```

## 🚀 Deployment

### Streamlit Cloud

1. Fork this repository
2. Connect your GitHub account to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy your app
4. Add your OpenAI API key in the app secrets

### Docker

```bash
# Build image
docker build -t quiz-generator .

# Run container
docker run -p 8501:8501 -e OPENAI_API_KEY=your_key quiz-generator
```

### Local Production

```bash
# Install production dependencies only
pip install -r requirements-prod.txt

# Run with production settings
streamlit run app.py --server.port=8501
```

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes |
| `DEBUG` | Enable debug mode (true/false) | No |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | No |

## 📊 Performance Metrics

- **File Processing**: Supports documents up to 10MB
- **Text Extraction**: Handles complex document layouts
- **Quiz Generation**: Typically completes in 3-10 seconds
- **Scalability**: Optimized for concurrent users

## 🛠️ Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Run code formatting
black .
isort .

# Run linting
flake8 .
mypy .
```

### Adding New Features

1. Follow the existing modular architecture
2. Add appropriate tests in the `tests/` directory
3. Update documentation
4. Ensure all quality checks pass

## 📈 Roadmap

- [ ] **Analytics Dashboard**: User engagement metrics
- [ ] **Export Options**: PDF/Word quiz exports
- [ ] **Multi-language Support**: Internationalization
- [ ] **Advanced Question Types**: Image-based questions, drag-and-drop
- [ ] **Team Features**: Shared quizzes and leaderboards
- [ ] **API Integration**: RESTful API for external applications

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for providing the GPT API
- Streamlit team for the amazing framework
- Contributors and users who help improve this project

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/ai-quiz-generator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ai-quiz-generator/discussions)
- **Email**: your.email@example.com

---

Made with ❤️ by [Your Name](https://github.com/yourusername)
